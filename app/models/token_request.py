from pydantic import BaseModel

class TokenRequest(BaseModel):
    apikey: str
    tokens: str
    active: bool
