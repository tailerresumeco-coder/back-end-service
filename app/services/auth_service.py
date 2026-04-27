from google.oauth2 import id_token
from google.auth.transport import requests
from app.db import auth_collection
from app.utils.jwt import create_access_token
import os

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")

async def get_user_by_email(email):
    return await auth_collection.find_one({"email": email})

async def create_user(user):
    return await auth_collection.insert_one(user)

async def signup(email, password, confirmPassword):
    try:
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

    except Exception as e:
        return {"error": str(e)}

async def login(email, password):
    try:
        user = await get_user_by_email(email)
        if not user:
            return {"error": "User not found"}

        if user.provider == "google":
            return {
                "error": "Please login with Google"
            }

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

    except Exception as e:
        return {"error": str(e)}

async def google_signup(credential: str):
    print('Begin auth_service.py -> google_signup()')
    try:
        idinfo = id_token.verify_oauth2_token(
            credential,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )

        email = idinfo.get("email")
        name = idinfo.get("name")
        google_id = idinfo.get("sub")

        if not email:
            return {"error": "Email not found in token"}

        # 🔍 Check if user exists
        user = await get_user_by_email(email)

        if not user:
            # 🆕 Create user
            user = await create_user({
                "email": email,
                "name": name,
                "provider": "google",
                "google_id": google_id
            })
            token = create_access_token({"sub": email})

        # 🔐 Generate YOUR JWT (not Google token)
        token = create_access_token({"sub": email})

        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "email": email
            }
        }

    except ValueError:
        return {"error": "Invalid Google token"}