from pydantic import BaseModel

class DownloadResumeRequestModel(BaseModel):
    html: str
    filename: str