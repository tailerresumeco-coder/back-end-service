from typing import Any, Dict
from app.db import resumes_collection

async def upload_resume(payload: Dict[str, Any]):
    print('Begin resume_service.py -> upload_resume()', payload)
    db_response = await resumes_collection.insert_one(payload)
    print('End resume_service.py -> upload_resume()', db_response)
    return "Resume uploaded successfully"