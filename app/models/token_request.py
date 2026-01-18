from pydantic import BaseModel

class TokenRequest(BaseModel):
    apikey: str
    tokens: int
    requests:int
    active: bool
