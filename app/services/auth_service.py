
from app.db import auth_collection
from app.utils.jwt import create_access_token

async def signup(email, password, confirmPassword):
    if password != confirmPassword:
        return {"error": "Passwords do not match"}

    is_email_exists = await auth_collection.find_one({"email": email})

    if is_email_exists:
        return {"error": "User already exists"}

    user_signup_obj = {
        "email": email,
        "password": password
    }

    await auth_collection.insert_one(user_signup_obj)

    return {"message": "User created successfully"}

async def login(email, password):
    user = await auth_collection.find_one({"email": email})

    if not user:
        return {"error": "User not found"}

    if user["password"] != password:
        return {"error": "Invalid credentials"}

    # 🔥 create JWT token
    token = create_access_token({"sub": user["email"]})

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "email": user["email"]
        }
    }