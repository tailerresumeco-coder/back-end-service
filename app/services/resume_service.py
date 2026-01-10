from typing import Any, Dict
from app.db import resumes_collection
from openai import OpenAI
from app.utils.prompts import PROMPT_7, PROMPT_8, PROMPT_9
import json
import re
import os
from fastapi import HTTPException
from groq import Groq
from dotenv import load_dotenv

load_dotenv()
from fastapi.responses import StreamingResponse
from playwright.async_api import async_playwright
import io

def get_openai_client():
    api_key = os.getenv("HF_API_KEY")
    endpoint = os.getenv("HF_ENDPOINT")

    if not api_key or not endpoint:
        raise HTTPException(
            status_code=500,
            detail="Server configuration error: missing HF credentials"
        )

    return OpenAI(
        base_url=endpoint,
        api_key=api_key,
    )

def extract_json(text):
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return text  # Return the text as is if no JSON found
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return text  # Return the text as is if JSON is invalid

async def upload_resume(payload: Dict[str, Any]):
    db_response = await resumes_collection.insert_one(payload)
    return "Resume uploaded successfully"


async def download_resume(html, filename):

    html_document = f"""
    <html>
      <head>
        <meta charset="UTF-8">
        <style>
          body {{
            font-family: Arial, sans-serif;
          }}
        </style>
      </head>
      <body>
        {html}
      </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--single-process"
        ]
        )

        page = await browser.new_page()

        await page.set_content(html_document, wait_until="networkidle")

        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={
            }
        )

        await browser.close()
    response = StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf"
    )

    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Access-Control-Allow-Origin"] = "https://tailer-resume.netlify.app"
    response.headers["Access-Control-Expose-Headers"] = "Content-Disposition"

    return response

    # return StreamingResponse(
    #     io.BytesIO(pdf_bytes),
    #     media_type="application/pdf",
    #     headers={
    #         "Content-Disposition": f"attachment; filename={filename}"
    #     }
    # )

async def tailer_resume(resume_content, jd_text):
    try:
        prompt = PROMPT_9
        prompt = prompt.replace("{{RESUME_TEXT}}", resume_content)
        prompt = prompt.replace("{{JOB_DESCRIPTION}}", jd_text)

        client = get_openai_client()

        completion = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3.2-Exp:novita",
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        answer = completion.choices[0].message.content

        return {
            "prompt": prompt,
            "response": extract_json(answer)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))




def get_groq_client() -> Groq:
    """Initialize Groq client with API key from .env"""
    groq_api_key = os.getenv("GROQ_API_KEY")
    
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found in .env file")
    
    return Groq(api_key=groq_api_key)


def extract_json(text: str) -> Dict[str, Any]:
    """
    Extract and parse JSON from LLM response.
    Handles markdown formatting and cleaning.
    
    Args:
        text: Raw response from Groq API
        
    Returns:
        Parsed JSON dictionary
        
    Raises:
        ValueError: If no valid JSON found in response
    """
    try:
        # Remove markdown code blocks if present
        text = text.strip()
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


async def tailor_resume_groq(
    resume_content: str,
    jd_text: str
) -> Dict[str, Any]:
    """
    Tailor resume using Groq API with PROMPT_9.
    Simple, no retries - let it fail fast so we collect real data.
    
    Args:
        resume_content: Raw resume text
        jd_text: Job description text
    
    Returns:
        Dict with status, data, and metadata
    """
    
    # Prepare the prompt by replacing placeholders
    prompt = PROMPT_9.replace("{{RESUME_TEXT}}", resume_content)
    prompt = prompt.replace("{{JOB_DESCRIPTION}}", jd_text)
    
    # Initialize Groq client
    client = get_groq_client()

    # Get model from environment
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    try:
        # Call Groq API
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,  # Deterministic for structured data
            max_tokens=4096
        )
        
        # Extract response
        response_text = completion.choices[0].message.content
        
        # Parse JSON
        try:
            parsed_response = extract_json(response_text)
        except ValueError as json_error:
            return {
                "status": "error",
                "code": "JSON_PARSE_ERROR",
                "message": "Could not parse AI response as JSON",
                "error": str(json_error),
                "raw_response": response_text[:500]  # First 500 chars for debugging
            }
        
        # Success
        input_tokens = getattr(completion.usage, 'input_tokens', getattr(completion.usage, 'prompt_tokens', 0))
        output_tokens = getattr(completion.usage, 'output_tokens', getattr(completion.usage, 'completion_tokens', 0))
        
        return {
            "status": "success",
            "data": parsed_response,
            "model": "llama-3.1-70b-versatile",
            "tokens_used": {
                "input": input_tokens,
                "output": output_tokens,
                "total": input_tokens + output_tokens
            }
        }
    
    except Exception as e:
        error_msg = str(e).lower()
        
        # Token/context limit error
        if "token" in error_msg or "context" in error_msg:
            return {
                "status": "error",
                "code": "TOKEN_LIMIT_EXCEEDED",
                "message": "Resume + JD combination too long. Please use a shorter resume (max 2 pages) or shorter JD (max 1 page).",
                "error": str(e)
            }
        
        # Rate limit error
        if "rate" in error_msg or "quota" in error_msg:
            return {
                "status": "error",
                "code": "RATE_LIMIT",
                "message": "Too many requests. Please try again in a moment.",
                "error": str(e)
            }
        
        # API key error
        if "api" in error_msg or "auth" in error_msg or "key" in error_msg:
            return {
                "status": "error",
                "code": "API_KEY_ERROR",
                "message": "Server configuration error. Please contact support.",
                "error": str(e)
            }
        
        # Generic error
        return {
            "status": "error",
            "code": "GROQ_API_ERROR",
            "message": "Error processing resume with AI service",
            "error": str(e)
        }