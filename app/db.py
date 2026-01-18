# app/db.py
from motor.motor_asyncio import AsyncIOMotorClient
import os
import ssl
import certifi

ssl_context = ssl.create_default_context(cafile=certifi.where())
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = "tailer_resume"

client = AsyncIOMotorClient(
    MONGO_URI,
    tls=True,
    tlsCAFile=certifi.where(),
    ssl_context=ssl_context,
    serverSelectionTimeoutMS=30000,
)

rdb = client[DB_NAME]

# collection where you'll store resumes
resumes_collection = db["resumes"]
groq_tokens_collection = db["groq_tokens"]
