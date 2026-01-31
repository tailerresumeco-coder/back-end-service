"""
Resume Service V2 - Single-Step Resume Processing

One LLM call: Resume + JD → Tailored JSON
- Faster (1 call vs 2)
- Cheaper (half the tokens)
- Strong data preservation rules
"""

from typing import Any, Dict, Optional, Tuple
from app.utils.prompts_v2 import RESUME_TAILOR_PROMPT
import json
import re
import os
from datetime import datetime
from groq import Groq
from dotenv import load_dotenv
from app.services.token_service import get_active_apikey
from app.db import groq_tokens_collection

load_dotenv()


async def get_groq_client() -> Groq:
    """Initialize Groq client with API key"""
    groq_api_key = await get_active_apikey()
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found")
    return Groq(api_key=groq_api_key)


def extract_json(text: str) -> Dict[str, Any]:
    """Extract and parse JSON from LLM response."""
    try:
        text = text.strip()

        # Remove markdown code blocks if present
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\n?', '', text)
            text = re.sub(r'\n?```$', '', text)

        # Find JSON boundaries
        start_idx = text.find('{')
        end_idx = text.rfind('}')

        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON object found in response")

        json_str = text[start_idx:end_idx + 1]
        return json.loads(json_str)

    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in response: {str(e)}")


def count_bullets(data: Dict[str, Any]) -> int:
    """Count total bullet points in tailored_content."""
    total = 0

    tailored = data.get('tailored_content', {})

    # Count experience bullets
    for exp in tailored.get('experience', []):
        if 'projects' in exp and exp.get('projects'):
            for proj in exp.get('projects', []):
                total += len(proj.get('responsibilities', []))
        else:
            total += len(exp.get('responsibilities', []))

    # Count project highlights
    for proj in tailored.get('projects', []):
        total += len(proj.get('highlights', []))

    return total


async def process_resume_two_step(
    resume_content: str,
    jd_text: Optional[str] = None
) -> Dict[str, Any]:
    """
    Two-step resume processing.

    Step 1: Parse resume (always)
    Step 2: Tailor for JD (if provided)

    Args:
        resume_content: Raw resume text
        jd_text: Job description (optional)

    Returns:
        Dict with status and data
    """
    if jd_text:
        # Full tailoring mode
        return await tailor_resume_groq_v2(resume_content, jd_text)
    else:
        # Parse-only mode - not implemented yet, return error
        return {
            "status": "error",
            "code": "NOT_IMPLEMENTED",
            "message": "Parse-only mode not yet implemented"
        }


async def tailor_resume_groq_v2(
    resume_content: str,
    jd_text: str
) -> Dict[str, Any]:
    """
    Single-step resume tailoring.

    Input: Resume text + JD text
    Output: Tailored JSON with ATS score and gap analysis
    """

    # Build prompt
    prompt = RESUME_TAILOR_PROMPT.replace("{{RESUME_TEXT}}", resume_content)
    prompt = prompt.replace("{{JOB_DESCRIPTION}}", jd_text)

    # Get client
    client = await get_groq_client()
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    try:
        # Single LLM call
        completion = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=6000
        )

        response_text = completion.choices[0].message.content

        # Parse JSON
        try:
            data = extract_json(response_text)
        except ValueError as e:
            return {
                "status": "error",
                "code": "JSON_PARSE_ERROR",
                "message": str(e),
                "raw_response": response_text[:500]
            }

        # Get token usage
        input_tokens = getattr(completion.usage, 'prompt_tokens', 0)
        output_tokens = getattr(completion.usage, 'completion_tokens', 0)
        total_tokens = input_tokens + output_tokens

        # Log token usage
        try:
            await groq_tokens_collection.insert_one({
                "token": "v2_single",
                "tokens": total_tokens,
                "timestamp": datetime.now()
            })
        except Exception:
            pass

        # Count bullets for validation
        bullet_count = count_bullets(data)
        validation = data.get('_validation', {})

        if validation.get('output_bullet_count', 0) == 0:
            validation['output_bullet_count'] = bullet_count
            data['_validation'] = validation

        return {
            "status": "success",
            "data": data,
            "model": model,
            "tokens_used": {
                "input": input_tokens,
                "output": output_tokens,
                "total": total_tokens
            }
        }

    except Exception as e:
        return handle_error(e)


def handle_error(e: Exception) -> Dict[str, Any]:
    """Handle common errors."""
    error_msg = str(e).lower()

    if "token" in error_msg or "context" in error_msg:
        return {
            "status": "error",
            "code": "TOKEN_LIMIT",
            "message": "Content too long. Use shorter resume or JD."
        }

    if "rate" in error_msg or "quota" in error_msg:
        return {
            "status": "error",
            "code": "RATE_LIMIT",
            "message": "Too many requests. Try again shortly."
        }

    return {
        "status": "error",
        "code": "LLM_ERROR",
        "message": str(e)
    }
