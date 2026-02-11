from fastapi import APIRouter, HTTPException
from typing import Any, Dict
from app.services.resume_service import upload_resume as upload_resume_service, tailer_resume as tailer_resume_service, download_resume as download_resume_service, tailor_resume_groq, feedback as feedback_service
from app.models.tailer_resume_request import TailerResumeRequestModel, TailerResumeRequestModelV2
from app.models.download_resume_request import DownloadResumeRequestModel
from app.models.feedback_model import FeedbackModel
from app.services.resume_service import store_resumes as store_resumes_service
from app.models.store_resumes_request import StoreResumesRequest

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


@router.post("/tailer-resume-legacy")
async def tailer_resume_legacy(payload: TailerResumeRequestModel):
    print('Begin resume_router.py -> tailer_resume_legacy()')
    response = await tailor_resume_groq(payload.resume, payload.jd)
    print('End resume_router.py -> tailer_resume_legacy()')
    return response

@router.post("/download-pdf")
async def download_resume(payload: DownloadResumeRequestModel):
    print('Begin resume_router.py -> download_resume()')
    response = await download_resume_service(payload.html, payload.filename, 'stream')
    print('End resume_router.py -> download_resume()')
    return response

@router.post("/feedback")
async def feedback(payload: FeedbackModel):
    print('Begin resume_router.py -> feedback()')
    await feedback_service(payload.liked, payload.unLiked, payload.message, payload.email, payload.name)
    print('End resume_router.py -> feedback()')
    return {"message": "Feedback received successfully"}

@router.post("/store-resumes")
async def store_resumes(payload: StoreResumesRequest):
    print("Begin resume_router.py -> store_resumes()")
    try:
        if not payload.email:
            raise HTTPException(status_code=400, detail="Email is required to store resumes")
        if not payload.input_resume or not payload.output_resume:
            raise HTTPException(status_code=400, detail="Both input and output resumes are required")
        await store_resumes_service(payload.input_resume, payload.output_resume, payload.email)
        return {
            "message": "Resumes stored successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error storing resumes: {str(e)}")