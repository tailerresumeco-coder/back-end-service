from pydantic import BaseModel
from typing import Optional

class TailerResumeRequestModel(BaseModel):
    resume: str
    jd: str
    resume_id: str
    email: str
    resume_name: str

class TailerResumeRequestModelV2(BaseModel):
    resume: str
    jd: Optional[str] = None
    use_v2: bool = True  # Flag to use new two-step processing
