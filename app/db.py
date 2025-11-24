# app/db.py
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = "mongodb://localhost:27017"  # update if using Atlas or different host
DB_NAME = "tailer_resume"               # you can name this whatever you want

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# collection where you'll store resumes
resumes_collection = db["resumes"]
