from app.db import groq_tokens_collection, users_collection
from bson import ObjectId


async def get_active_apikey() -> str:
    token_doc = await groq_tokens_collection.find_one({"active": True})
    if not token_doc:
        raise ValueError("Active token not found in DB")
    return token_doc["apikey"]


async def get_all_tokens() -> list:
    tokens = await groq_tokens_collection.find().to_list(length=100)
    for token in tokens:
        token["_id"] = str(token["_id"])
    return tokens


async def update_token_obj(apikey, active=None, tokens=None, requests=None):
    token = await groq_tokens_collection.find_one({"apikey": apikey})
    if not token:
        return {"message": "API key not found", "status": "ERROR"}

    update_fields = {}

    if active is not None:
        update_fields["active"] = active
    if tokens is not None:
        update_fields["tokens"] = tokens
    if requests is not None:
        update_fields["requests"] = requests

    if not update_fields:
        return {"message": "Nothing to update", "status": "ERROR"}

    await groq_tokens_collection.update_one({"apikey": apikey}, {"$set": update_fields})

    return await get_all_tokens()


async def set_apikey_active(apikey):
    # deactivate all
    await groq_tokens_collection.update_many({}, {"$set": {"active": False}})

    # activate one
    await groq_tokens_collection.update_one(
        {"apikey": apikey}, {"$set": {"active": True}}
    )

    return await get_all_tokens()


async def add_apikey(apikey, name, tokens=0, requests=0):
    print("Begin token_service.py -> add_apikey()")
    is_exists = await groq_tokens_collection.find_one({"apikey": apikey})
    if is_exists:
        return {"message": "API key already exists", "status": "ERROR"}

    await groq_tokens_collection.insert_one(
        {
            "apikey": apikey,
            "active": False,
            "tokens": tokens,
            "requests": requests,
            "name": name,
        }
    )
    print("End token_service.py -> add_apikey()")

    return await get_all_tokens()


async def delete_apikey(id):
    print("Begin token_service.py -> delete_apikey()", id)
    try:
        token = await groq_tokens_collection.find_one({"_id": id})
    except Exception as e:
        print(f"Error finding token: {e}")
        return {"message": "Error accessing the database", "status": "ERROR"}
    print("Deleted obj token is:", token)
    if not token:
        return {"message": "API key not found", "status": "ERROR"}
    deleted_token = await groq_tokens_collection.delete_one({"_id": id})
    print("End token_service.py -> delete_apikey()", deleted_token)
    return await get_all_tokens()


async def add_user_details(email="", name="", phone=""):
    print("Begin token_service.py -> add_user_details()", email, name, phone)
    try:
        user = await get_user_details(email)
        if not user:
            result = await users_collection.insert_one(
                {"name": name, "email": email, "phone": phone, "count": 0}
            )
            print(f"User added with id: {result.inserted_id}")
        else:
            print("User already exists.")
    except Exception as e:
        print(f"Error adding user: {e}")
        
async def add_user_or_handle_existing(email: str, name: str, phone: str):
    user = await get_user_details(email)
    if not user:
        await users_collection.insert_one(
            {"name": name, "email": email, "phone": phone, "count": 0}
        )
    else:
        await users_collection.update_one({"email": email}, {"$set": {"count": user['count'] + 1}})

async def get_user_details(email: str):
    user = await users_collection.find_one({"email": email})
    if user:
        user["_id"] = str(user["_id"])
    return user

async def make_all_tokens_count_zero():
    print('Setting all user token counts to zero.')
    result = await users_collection.update_many(
        {},  # Update all documents
        {"$set": {"tokens": 0}}
    )
    return result.modified_count