from typing import Any, Dict
from app.db import resumes_collection, groq_tokens_collection, feedback_collection
from openai import OpenAI
from app.utils.prompts import PROMPT_9
from app.utils.prompts_v2 import RESUME_TAILOR_PROMPT, RESUME_TAILOR_PROMPT0, GET_ATS_SCORE_PROMPT
import json
import re
import os
from fastapi import HTTPException
from groq import Groq
from dotenv import load_dotenv
from app.services.mail_service import send_email_test, send_token_nearly_exhausted_email, tailored_notify_email
from app.services.token_service import get_active_apikey, update_token_obj, add_user_or_handle_existing
import io
from app.services.s3_service import upload_file_to_s3
import base64
from io import BytesIO
import pdfplumber
import re

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
    print('Begin resume_service.py -> download_resume()')
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
        extracted_text = ""
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page_number, page in enumerate(pdf.pages, start=1):
                page_text = page.extract_text()
                if page_text:
                    extracted_text += page_text

        return extracted_text
    except Exception as e:
        raise ValueError(f"Error extracting text from PDF: {str(e)}")
    
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
    
    resume_content =  await extract_text_from_resume(resume_content)

   
    prompt = RESUME_TAILOR_PROMPT0.replace("{RESUME_TEXT}", resume_content)
    prompt = prompt.replace("{JOB_DESCRIPTION}", jd_text)
    
    # Initialize Groq client
    client = await get_groq_client()

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
            max_tokens=8000
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
        
        if (token_record["tokens"] + input_tokens + output_tokens) >= 1:
            try:
                await send_token_nearly_exhausted_email()
            except Exception as e:
                print("Error sending token nearly exhausted email:", str(e))
        # await tailored_notify_email(parsed_response["basic"]["name"], parsed_response["basic"]["email"])
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
