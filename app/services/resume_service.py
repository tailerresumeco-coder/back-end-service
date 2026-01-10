from typing import Any, Dict
from app.db import resumes_collection
from openai import OpenAI
from app.utils.prompts import PROMPT_7, PROMPT_8, PROMPT_9
import json
import re
import os
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
import pdfkit
import tempfile
from fastapi.responses import FileResponse
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
            margin: 20px;
          }}
        </style>
      </head>
      <body>
        {html}
      </body>
    </html>
    """

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page()

        await page.set_content(html_document, wait_until="networkidle")

        pdf_bytes = await page.pdf(
            format="A4",
            print_background=True,
            margin={
                "top": "15mm",
                "bottom": "15mm",
                "left": "15mm",
                "right": "15mm"
            }
        )

        await browser.close()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={filename}"
        }
    )

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
