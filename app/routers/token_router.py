from fastapi import APIRouter
from app.db import groq_tokens_collection
from app.models.token_request import TokenRequest
from app.models.token_active_request import TokenActiveRequest


router = APIRouter(
    prefix="/resume",
    tags=["Resume"],
)

@router.post("/token/save")
async def save_token(request: TokenRequest):
    data = {
        "apikey": request.apikey,
        "token": request.tokens,
        "requests": request.requests,
        "active": request.active
    }

    groq_tokens_collection.insert_one(data)

    return {
        "message": "Token saved successfully",
        "status": "SUCCESS"
    }


@router.get("/tokens")
async def get_tokens():
    tokens = await groq_tokens_collection.find().to_list(length=100)

    for token in tokens:
        token["_id"] = str(token["_id"])

    return tokens

@router.patch("/token/activate")
async def set_active_token(request: TokenActiveRequest):
    result = await groq_tokens_collection.update_one(
        {"apikey": request.apikey},
        {"$set": {"active": request.active}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Token not found")

    return {
        "message": "Token updated successfully",
        "status": "SUCCESS"
    }
