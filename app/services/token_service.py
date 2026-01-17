from app.db import token_collection

def get_active_apikey() -> str:
    token_doc = token_collection.find_one({"active": True})

    if not token_doc:
        raise ValueError("Active token not found in DB")

    return token_doc["apikey"]
