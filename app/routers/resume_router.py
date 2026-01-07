from fastapi import APIRouter
from typing import Any, Dict
from app.services.resume_service import upload_resume as upload_resume_service

router = APIRouter(
    prefix="/resume",
    tags=["Resume"],
)

@router.get("/")
async def root():
    return {"message": "Hello from FastAPI"}

@router.post("/upload-resume")
async def upload_resume(payload: Dict[str, Any]):
    print('Begin resume_router.py -> upload_resume()')
    response = await upload_resume_service(payload)
    return response

@router.post("/tailer-resume")
async def upload_resume(payload: TailerResumeRequestModel):
    print('Begin resume_router.py -> upload_resume()')
    resume = payload.resume
    jd = payload.jd
    response = await tailer_resume_service(payload.resume, payload.jd)
    print('End resume_router.py -> upload_resume()')
    return response

@router.get("/keepalive")
async def keep_a_live():
    try:
        return "Server is Running..."
    except:
        raise HTTPException(status_code=500, detail=str(e))
  