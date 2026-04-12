from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class UserResumeModel(BaseModel):
    id: str
    email: str
    name: str
    s3_key: str
    file_type: str
    uploaded_at: datetime
    is_active: bool


class ResumeListResponse(BaseModel):
    resumes: list[UserResumeModel]


class ActiveResumeResponse(BaseModel):
    has_active: bool
    resume: Optional[UserResumeModel] = None
