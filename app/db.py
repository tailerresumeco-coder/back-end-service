# app/db.py
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URI = os.getenv("MONGO_URI1")
DB_NAME = "tailer_resume"

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# collection where you'll store resumes
resumes_collection = db["resumes"]
groq_tokens_collection = db["groq_tokens"]
