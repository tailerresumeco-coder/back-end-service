from motor.motor_asyncio import AsyncIOMotorClient
import os
import certifi

MONGO_URI = os.environ["MONGO_URI"]
DB_NAME = "tailer_resume"


if MONGO_URI.startswith("mongodb+srv://"):
    client = AsyncIOMotorClient(
        MONGO_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=30000,
    )
else:
    client = AsyncIOMotorClient(
        MONGO_URI,
        serverSelectionTimeoutMS=30000,
    )

db = client[DB_NAME]

resumes_collection = db["resumes"]
groq_tokens_collection = db["groq_tokens"]
