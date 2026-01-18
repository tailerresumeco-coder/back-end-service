# app/models/token_active_request.py
from pydantic import BaseModel

class TokenActiveRequest(BaseModel):
    apikey: str
    active: bool
