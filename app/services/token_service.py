from app.db import groq_tokens_collection

# app/services/token_service.py
async def get_active_apikey() -> str:
    token_doc = await groq_tokens_collection.find_one({"active": True})

    if not token_doc:
        raise ValueError("Active token not found in DB")

    return token_doc["apikey"]

