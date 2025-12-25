from typing import Any, Dict
from app.db import resumes_collection
from openai import OpenAI
from app.config import HF_API_KEY, HF_ENDPOINT
from app.utils.prompts import PROMPT_1  
import json

client = OpenAI(
    base_url = HF_ENDPOINT,
    api_key = HF_API_KEY,
)

async def upload_resume(payload: Dict[str, Any]):
    print('Begin resume_service.py -> upload_resume()', payload)
    db_response = await resumes_collection.insert_one(payload)
    print('End resume_service.py -> upload_resume()', db_response)
    return "Resume uploaded successfully"

async def tailer_resume(resume_content, jd_text):
    print('Begin resume_service.py -> tailer_resume()')
    
    try:
        
        prompt = PROMPT_1.replace("{{RESUME_TEXT}}", resume_content)
        
        completion = client.chat.completions.create(
            model="deepseek-ai/DeepSeek-V3.2-Exp:novita",
            messages=[
                {"role": "user", "content": prompt}
            ],
        )

        answer = completion.choices[0].message.content

        return {
            "response": json.loads(answer)
        }

    except Exception as e:
        return {"error": str(e)} 

    print('End resume_service.py -> tailer_resume()', db_response)
    return "Resume uploaded successfully"
