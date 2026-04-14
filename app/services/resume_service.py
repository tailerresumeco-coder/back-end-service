from typing import Any, Dict
from app.db import resumes_collection, groq_tokens_collection, feedback_collection, user_resumes_collection, jobs_collection
from openai import OpenAI
from app.utils.prompts import PROMPT_9
from app.utils.prompts_v2 import RESUME_TAILOR_PROMPT0, GET_ATS_SCORE_PROMPT
import json
import re
import os
from fastapi import HTTPException
from groq import Groq
from dotenv import load_dotenv
from app.services.mail_service import send_email_test, send_token_nearly_exhausted_email, tailored_notify_email
from app.services.token_service import get_active_apikey, update_token_obj, add_user_or_handle_existing
import io
import boto3
from app.services.s3_service import upload_file_to_s3
import base64
from bson import ObjectId
from io import BytesIO
import pdfplumber
import re
from urllib.parse import unquote

load_dotenv()
from fastapi.responses import StreamingResponse
from datetime import datetime
from weasyprint import HTML

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

async def feedback(liked: bool, unLiked: bool, message: str, email: str, name: str):
    print('Begin resume_service.py -> feedback()')
    await feedback_collection.insert_one({
        "liked": liked,
        "unLiked": unLiked,
        "message": message,
        "email": email,
        "name": name,
        "createdOn": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    })
    print('End resume_service.py -> feedback()')
    return {"message": "Feedback received successfully"}

async def download_resume(html: str, filename: str, response_type: str = "pdf"):
    print('-----Begin resume_service.py -> download_resume()')
    try:
        html_document = f"""
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
    @page {{
                size: A4;
                margin: 10mm 12mm;   /* top/bottom left/right */
            }}

            /* RESET BROWSER DEFAULTS */
            html, body {{
                margin: 0;
                padding: 0;
                font-family: Calibri, Arial, sans-serif;
                font-size: 12px;
                line-height: 1.4;
                color: #000;
            }}

            /* REMOVE PREVIEW STYLES */
            .main-container {{
                min-height: auto !important;
                transform: none !important;
                margin: 0 !important;
                padding: 0 !important;
            }}

            .section {{
                page-break-inside: avoid;
            }}
            </style>
        </head>
        <body>
            {html}
        </body>
        </html>
        """

        pdf_bytes = HTML(string=html_document).write_pdf()
        
        if response_type == 'pdf':
            return pdf_bytes
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating PDF: {str(e)}")

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

# ---------------------------------------------------------------------------
# Groq model registry — ordered by quality preference (best first).
# tpm = tokens-per-minute on-demand limit.
# ---------------------------------------------------------------------------
_GROQ_MODEL_REGISTRY = [
    {"id": "llama-3.3-70b-versatile", "tpm": 12_000},
    {"id": "llama-3.1-8b-instant",    "tpm": 200_000},
]
_PROMPT_OVERHEAD_TOKENS = 1_600   # approximate token size of RESUME_TAILOR_PROMPT0
_DESIRED_OUTPUT_TOKENS  = 8_000   # ideal output budget
_MIN_OUTPUT_TOKENS      = 2_000   # minimum we'll accept before raising


def _estimate_tokens(text: str) -> int:
    """Rough estimate: 4 chars ≈ 1 token (sufficient for routing decisions)."""
    return max(1, len(text) // 4)


def _select_model(input_token_estimate: int) -> tuple:
    """
    Pick the best Groq model whose TPM budget fits the full request.
    Returns (model_id, max_output_tokens).

    - Tries models best-first (quality order).
    - Shrinks max_output_tokens when the desired budget doesn't fit but a
      smaller output still would.
    - Raises ValueError only when no model can provide _MIN_OUTPUT_TOKENS.
    """
    SAFETY_BUFFER = 200
    for entry in _GROQ_MODEL_REGISTRY:
        headroom = entry["tpm"] - input_token_estimate - SAFETY_BUFFER
        if headroom >= _DESIRED_OUTPUT_TOKENS:
            return entry["id"], _DESIRED_OUTPUT_TOKENS
        if headroom >= _MIN_OUTPUT_TOKENS:
            return entry["id"], headroom

    # Absolute last resort — highest-TPM model with whatever fits
    best = max(_GROQ_MODEL_REGISTRY, key=lambda m: m["tpm"])
    headroom = best["tpm"] - input_token_estimate - SAFETY_BUFFER
    if headroom < _MIN_OUTPUT_TOKENS:
        raise ValueError(
            f"Resume + JD combination is too large for all available models "
            f"(estimated {input_token_estimate} input tokens). "
            "Please use a shorter resume (max 2 pages) or a shorter job description."
        )
    return best["id"], headroom


async def get_groq_client() -> Groq:
    groq_api_key = await get_active_apikey()
    if not groq_api_key:
        raise ValueError("GROQ_API_KEY not found in .env file")
    return Groq(api_key=groq_api_key)

def extract_json(text: str) -> Dict[str, Any]:
   
    try:
        text = text.strip()
        if text.startswith('```'):
            text = re.sub(r'^```(?:json)?\n?', '', text)
            text = re.sub(r'\n?```$', '', text)
        
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx == -1 or end_idx == -1:
            raise ValueError("No JSON object found in response")
        
        json_str = text[start_idx:end_idx + 1]
        return json.loads(json_str)
    
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in response: {str(e)}")
    

async def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    try:
        final_text = ""

        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                words = page.extract_words(use_text_flow=True)

                # Replace visible words with links
                if page.hyperlinks:
                    for link in page.hyperlinks:
                        uri = link.get("uri")
                        if not uri:
                            continue

                        uri = unquote(uri)


                        for word in words:
                            # check overlap between word & link rectangle
                            if (
                                word["x0"] >= link["x0"]
                                and word["x1"] <= link["x1"]
                                and word["top"] >= link["top"]
                                and word["bottom"] <= link["bottom"]
                            ):
                                page_text = page_text.replace(
                                    word["text"],
                                    uri
                                )

                final_text += page_text + "\n"
        return final_text.strip()

    except Exception as e:
        raise ValueError(f"PDF extract error: {str(e)}")
    
    
async def extract_text_from_docx(docx_bytes: bytes) -> str:
    try:
        from docx import Document
        document = Document(BytesIO(docx_bytes))
        extracted_text = "\n".join([para.text for para in document.paragraphs])
        return extracted_text
    except Exception as e:
        raise ValueError(f"Error extracting text from DOCX: {str(e)}")

def clean_cell(text: str) -> str:
    if not text:
        return ""

    # Normalize unicode bullets and dashes
    text = text.replace("•", "-")
    text = text.replace("–", "-").replace("—", "-")

    # Remove excessive spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Fix spacing around pipes
    text = re.sub(r"\s*\|\s*", " | ", text)

    # Fix spacing around hyphens (dates etc.)
    text = re.sub(r"\s*-\s*", " - ", text)

    # Remove multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Fix merged bullet issue (like "...TWDTW).• Utilized...")
    text = re.sub(r"\)\s*-\s*", ")\n- ", text)

    # Split into lines and clean each
    lines = []
    seen = set()

    for line in text.splitlines():
        line = line.strip()

        if not line:
            continue

        # Remove duplicate lines
        if line not in seen:
            seen.add(line)
            lines.append(line)

    cleaned_text = "\n".join(lines)

    # Hard safety limit (VERY important for LLM usage)
    MAX_CHARS = 12000
    return cleaned_text[:MAX_CHARS]

async def extract_text_from_resume(resume_content: str):
    if (resume_content.startswith("data:application/pdf;base64,")):
        print("Detected PDF resume format")
        resume_content = await (extract_text_from_pdf(decode_base64_pdf(resume_content)))
    else:
        print("Detected DOCX resume format")
        resume_content = await (extract_text_from_docx(decode_base64_docx(resume_content)))
    return clean_cell(resume_content)

async def tailor_resume_groq(
    resume_content: str,
    jd_text: str
) -> Dict[str, Any]:
    
    resume_content = await extract_text_from_resume(resume_content)

    prompt = RESUME_TAILOR_PROMPT0.replace("{RESUME_TEXT}", resume_content)
    prompt = prompt.replace("{JOB_DESCRIPTION}", jd_text)

    # Initialize Groq client
    client = await get_groq_client()

    try:
        # Dynamic model selection: pick best model whose TPM budget fits this request.
        # No input is truncated — larger inputs automatically route to a higher-capacity model.
        input_token_estimate = _PROMPT_OVERHEAD_TOKENS + _estimate_tokens(resume_content) + _estimate_tokens(jd_text)
        model, max_tokens = _select_model(input_token_estimate)
        print(f"[tailor_resume_groq] input_estimate={input_token_estimate} tokens → model={model}, max_tokens={max_tokens}")

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
            max_tokens=max_tokens
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
        
        active_api_key = await get_active_apikey()
        token_record = await groq_tokens_collection.find_one({"apikey": active_api_key}) #no need - directly update active token
        groq_collection = await update_token_obj(active_api_key, tokens=token_record["tokens"] + input_tokens + output_tokens, requests=token_record["requests"] + 1)
        
        # await add_user_or_handle_existing(
        #     email=parsed_response["basic"]["email"],
        #     name=parsed_response["basic"]["name"],
        #     phone=parsed_response["basic"]["phone"],
        # )
        
        DAILY_TOKEN_LIMIT = 100_000
        ALERT_THRESHOLD = 0.80  # Send alert at 80% usage
        total_tokens_used = token_record["tokens"] + input_tokens + output_tokens
        if total_tokens_used >= DAILY_TOKEN_LIMIT * ALERT_THRESHOLD:
            try:
                await send_token_nearly_exhausted_email()
            except Exception as e:
                print("Error sending token nearly exhausted email:", str(e))
        # await tailored_notify_email(parsed_response["basic"]["name"], parsed_response["basic"]["email"])
        return {
            "status": "success",
            "data": parsed_response,
            "model": model,
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
        
async def store_resumes(input_resume, output_resume, email):
    try:
        print("Begin resume_service.py -> store_resumes()")
        timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M:%S")
        input_filename = f"{email}/{email}_input_{timestamp}.pdf"
        output_filename = f"{email}/{email}_output_{timestamp}.pdf"
        input_resume = decode_base64_pdf(input_resume)
        output_resume = await download_resume(output_resume, output_filename, 'pdf')
        path = f'{email}_{timestamp}'
        upload_file_to_s3(input_resume, 'io-resumes', input_filename)
        upload_file_to_s3(output_resume, 'io-resumes', output_filename)
    except Exception as e:
        print(f"Error in store_resumes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error storing resumes: {str(e)}")
    
def decode_base64_pdf(base64_str: str) -> bytes:
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]

    pdf_bytes = base64.b64decode(base64_str, validate=True)

    if not pdf_bytes.startswith(b"%PDF"):
        raise ValueError("Invalid PDF")

    return pdf_bytes

def decode_base64_docx(base64_str: str) -> bytes:
    if "," in base64_str:
        base64_str = base64_str.split(",")[1]

    docx_bytes = base64.b64decode(base64_str, validate=True)

    # DOCX files are ZIP-based (start with PK)
    if not docx_bytes.startswith(b"PK"):
        raise ValueError("Invalid DOCX file")

    return docx_bytes

async def tailor_resume_from_job(email: str, job_id: str) -> Dict[str, Any]:
    # 1. Get user's active resume
    resume_doc = await user_resumes_collection.find_one({"email": email, "is_active": True})
    if not resume_doc:
        raise HTTPException(
            status_code=400,
            detail="No active resume found. Please upload and activate a resume from your profile first."
        )

    # 2. Get the job
    try:
        oid = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID.")

    job_doc = await jobs_collection.find_one({"_id": oid})
    if not job_doc:
        raise HTTPException(status_code=404, detail="Job not found.")

    jd_text = (job_doc.get("description") or "").strip()
    if not jd_text:
        raise HTTPException(status_code=400, detail="This job has no description to tailor against.")

    # 3. Download resume file from S3
    s3_key = resume_doc["s3_key"]
    file_type = resume_doc.get("file_type", "pdf")

    try:
        s3_client = boto3.client(
            "s3",
            region_name=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
        s3_response = s3_client.get_object(
            Bucket=os.getenv("S3_BUCKET_NAME", "io-resumes"),
            Key=s3_key
        )
        file_bytes = s3_response["Body"].read()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not fetch your resume from storage: {str(e)}")

    # 4. Encode as base64 with MIME prefix (required by extract_text_from_resume)
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    if file_type == "pdf":
        resume_b64 = f"data:application/pdf;base64,{b64}"
    else:
        resume_b64 = f"data:application/vnd.openxmlformats-officedocument.wordprocessingml.document;base64,{b64}"

    # 5. Tailor
    return await tailor_resume_groq(resume_b64, jd_text)


async def check_ats_score(resume_text: str, jd: str):
    print('Begin resume_service.py -> check_ats_score()')
    resume_content = await extract_text_from_resume(resume_text)
    prompt = GET_ATS_SCORE_PROMPT.replace("{JOB_DESCRIPTION}", jd).replace("{RESUME_TEXT}", resume_content)

    client = await get_groq_client()
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0,
            max_tokens=8000
        )
        response_text = completion.choices[0].message.content
        parsed_response = extract_json(response_text)
        return {
            "status": "success",
            "data": parsed_response,
            "model": model
        }
    except Exception as e:
        return {
            "status": "error",
            "message": "Error checking ATS score",
            "error": str(e)
        }
