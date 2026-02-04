from fastapi import APIRouter, HTTPException
from app.models.token_request import TokenRequest
from app.models.token_active_request import TokenActiveRequest
from app.services.token_service import (
    get_all_tokens,
    set_apikey_active,
    add_apikey,
    delete_apikey,
    update_token_obj,
    make_all_tokens_count_zero,
)
from bson import ObjectId

router = APIRouter(
    prefix="/resume",
    tags=["Resume"],
)

@router.post("/token/save")
async def save_token(request: TokenRequest):
    print('Begin token_router.py -> save_token()')
    result = await add_apikey(
        apikey=request.apikey,
        name=request.name,
        tokens=request.tokens,
        requests=request.requests,
    )

    return result

@router.get("/tokens")
async def get_tokens():
    print('Begin token_router.py -> get_tokens()')
    return await get_all_tokens()

@router.patch("/token/update")
async def update_token(request: TokenRequest):
    result = await update_token_obj(
        apikey=request.apikey,
        active=request.active,
        tokens=request.tokens,
        requests=request.requests
    )

    return result

@router.patch("/token/activate")
async def activate_token(request: TokenActiveRequest):
    return await set_apikey_active(request.apikey)

@router.delete("/token/delete/{id}")
async def remove_token(id: str):
    print('Begin token_router.py -> remove_token()')
    return await delete_apikey(ObjectId(id))

@router.get("/token/reset-groq-token-counts")
async def reset_groq_token_counts():
    print('Begin token_router.py -> reset_groq_token_counts()')
    result = await make_all_tokens_count_zero()
    return {"message": f"Reset {result} user token counts to zero"}