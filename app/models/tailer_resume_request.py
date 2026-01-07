from pydantic import BaseModel

class TailerResumeRequestModel(BaseModel):
    resume: str
    jd: str
