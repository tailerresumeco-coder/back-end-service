from pydantic import BaseModel

class StoreResumesRequest(BaseModel):
    input_resume: str
    output_resume: str
    email: str