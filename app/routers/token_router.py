from fastapi import FastAPI
from app.db import token_collection
from models import TokenRequest

app = FastAPI()

@app.post("/api/token/save")
def save_token(request: TokenRequest):
    data = {
        "apikey": request.apikey,
        "token": request.token,
        "active": request.active
    }

    token_collection.insert_one(data)

    return {
        "message": "Token saved successfully",
        "status": "SUCCESS"
    }
