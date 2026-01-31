from pydantic import BaseModel
from typing import Optional

class TailerResumeRequestModel(BaseModel):
    resume: str
    jd: str


class TailerResumeRequestModelV2(BaseModel):
    """
    V2 Request Model - JD is optional for parse-only mode.

    - If jd is provided: Full two-step processing (parse + tailor)
    - If jd is empty/None: Parse-only mode (extract all data)
    """
    resume: str
    jd: Optional[str] = None
    use_v2: bool = True  # Flag to use new two-step processing
