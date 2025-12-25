from typing import Any, Dict
from app.db import resumes_collection
from openai import OpenAI
from app.config import HF_API_KEY, HF_ENDPOINT
from app.utils.prompts import PROMPT_1, PROMPT_2, PROMPT_3, PROMPT_4, PROMPT_5, PROMPT_6
import json
import re

client = OpenAI(
    base_url = HF_ENDPOINT,
    api_key = HF_API_KEY,
)

def extract_json(text):
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("No JSON found in model response")
    return json.loads(match.group())

async def upload_resume(payload: Dict[str, Any]):
    print('Begin resume_service.py -> upload_resume()', payload)
    db_response = await resumes_collection.insert_one(payload)
    print('End resume_service.py -> upload_resume()', db_response)
    return "Resume uploaded successfully"

async def tailer_resume(resume_content, jd_text):
    print('Begin resume_service.py -> tailer_resume()')
    
    try:
        prompt = PROMPT_5
        prompt = prompt.replace("{{RESUME_TEXT}}", resume_content)
        prompt = prompt.replace("{{JOB_DESCRIPTION}}", jd_text)
        
        completion = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3.2-Exp:novita",
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        answer = completion.choices[0].message.content
        
        print(answer)

        return {
            "prompt": prompt,
            "response": extract_json(answer)
        }

    except Exception as e:
        return {"error": str(e)} 

    print('End resume_service.py -> tailer_resume()', db_response)
    return "Resume uploaded successfully"
