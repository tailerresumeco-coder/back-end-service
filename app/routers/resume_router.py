from fastapi import APIRouter, HTTPException
from typing import Any, Dict
from app.services.resume_service import upload_resume as upload_resume_service, tailer_resume as tailer_resume_service, download_resume as download_resume_service, tailor_resume_groq
from app.services.resume_service_v2 import process_resume_two_step, tailor_resume_groq_v2
from app.models.tailer_resume_request import TailerResumeRequestModel, TailerResumeRequestModelV2
from app.models.download_resume_request import DownloadResumeRequestModel


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
async def tailer_resume(payload: TailerResumeRequestModel):
    """
    Legacy endpoint - uses new V2 two-step processing by default.
    """
    print('Begin resume_router.py -> tailer_resume() [V2]')
    response = await tailor_resume_groq_v2(payload.resume, payload.jd)
    print('End resume_router.py -> tailer_resume() [V2]')
    return response

@router.post("/tailer-resume-v2")
async def tailer_resume_v2(payload: TailerResumeRequestModelV2):
    """
    V2 Endpoint - Two-step resume processing with validation.

    Features:
    - Parse-only mode (no JD required)
    - Full tailoring mode (with JD)
    - Bullet count validation
    - Skills preservation check
    - Zero data loss guarantee
    """
    print('Begin resume_router.py -> tailer_resume_v2()')
    response = await process_resume_two_step(payload.resume, payload.jd)
    print('End resume_router.py -> tailer_resume_v2()')
    return response

@router.post("/tailer-resume-legacy")
async def tailer_resume_legacy(payload: TailerResumeRequestModel):
    """
    Legacy endpoint - uses original single-prompt processing.
    Kept for backward compatibility and A/B testing.
    """
    print('Begin resume_router.py -> tailer_resume_legacy()')
    response = await tailor_resume_groq(payload.resume, payload.jd)
    print('End resume_router.py -> tailer_resume_legacy()')
    return response

@router.get("/keepalive")
def keep_a_live():
    try:
        print('FROM keepalive() :: Server is Running...')
        return "Server is Running..."
    except:
        raise HTTPException(status_code=500, detail=str(e))
  
@router.post("/download-pdf")
async def download_resume(payload: DownloadResumeRequestModel):
    print('Begin resume_router.py -> download_resume()')
    response = await download_resume_service(payload.html, payload.filename)
    print('End resume_router.py -> download_resume()')
    return response