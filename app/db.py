from motor.motor_asyncio import AsyncIOMotorClient
import logging
import os
import certifi
import pymongo.errors

logger = logging.getLogger(__name__)

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
users_collection = db["users"]
feedback_collection = db["feedback"]

# Job aggregation collections
jobs_collection = db["jobs"]
job_fetch_logs_collection = db["job_fetch_logs"]


async def setup_job_indexes():
    """Create indexes for jobs collection. Safe to call on every startup (idempotent)."""
    # Unique index for deduplication
    await jobs_collection.create_index("dedup_hash", unique=True)

    # TTL index — auto-delete jobs older than configured days (default 30)
    # Wrapped in try/except because MongoDB raises OperationFailure if the index
    # already exists with a different expireAfterSeconds value (e.g. env var changed).
    ttl_days = int(os.getenv("JOB_TTL_DAYS", "30"))
    try:
        await jobs_collection.create_index(
            "fetched_at",
            expireAfterSeconds=ttl_days * 24 * 60 * 60,
        )
    except pymongo.errors.OperationFailure:
        logger.warning(
            "TTL index on 'fetched_at' already exists with different expireAfterSeconds. "
            "To change the TTL, drop the index manually and restart. "
            "Current JOB_TTL_DAYS=%d is not applied.",
            ttl_days,
        )

    # Compound index for the primary user query: valid jobs sorted by recency
    await jobs_collection.create_index([("is_valid_url", 1), ("fetched_at", -1)])

    # Additional query performance indexes
    await jobs_collection.create_index("source")
    await jobs_collection.create_index("is_valid_url")
