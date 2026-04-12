import asyncio
import logging
import os
from typing import Optional

import httpx
from bson import ObjectId

from app.db import jobs_collection, job_fetch_logs_collection

logger = logging.getLogger(__name__)


async def _check_url(client: httpx.AsyncClient, apply_url: str) -> bool:
    """Return True if URL is reachable (HTTP 200 after redirects)."""
    try:
        # Try HEAD first — faster, avoids downloading body
        response = await client.head(apply_url, follow_redirects=True)
        if response.status_code == 200:
            return True

        # Some servers block HEAD — fall back to GET
        response = await client.get(apply_url, follow_redirects=True)
        return response.status_code == 200

    except Exception:
        return False


async def validate_jobs_batch(job_ids: list[str], log_id: Optional[ObjectId] = None) -> None:
    """
    Phase 2 of async two-phase storage.
    Validates apply_url for each job ID and updates is_valid_url in DB.
    Runs as a background fire-and-forget task.

    job_ids: IDs of newly inserted jobs to validate (scoped to this run).
    log_id:  Optional fetch log _id to update with jobs_invalid_url count on completion.
    """
    if not job_ids:
        return

    timeout = int(os.getenv("JOB_URL_VALIDATION_TIMEOUT", "10"))
    concurrency = int(os.getenv("JOB_URL_VALIDATION_CONCURRENCY", "10"))
    semaphore = asyncio.Semaphore(concurrency)

    object_ids = [ObjectId(jid) for jid in job_ids]
    cursor = jobs_collection.find(
        {"_id": {"$in": object_ids}, "is_valid_url": None},
        {"_id": 1, "apply_url": 1}
    )
    jobs = await cursor.to_list(length=None)

    if not jobs:
        return

    # One shared client for all validations — connection pooling works correctly
    async with httpx.AsyncClient(timeout=timeout) as client:

        async def validate_one(job: dict) -> tuple[str, bool]:
            async with semaphore:
                result = await _check_url(client, job["apply_url"])
            return str(job["_id"]), result

        results = await asyncio.gather(
            *[validate_one(job) for job in jobs],
            return_exceptions=True
        )

    valid_ids = []
    invalid_ids = []

    for result in results:
        if isinstance(result, Exception):
            logger.warning("URL validation task raised exception: %s", result)
            continue
        job_id, is_valid = result
        if is_valid:
            valid_ids.append(ObjectId(job_id))
        else:
            invalid_ids.append(ObjectId(job_id))

    if valid_ids:
        await jobs_collection.update_many(
            {"_id": {"$in": valid_ids}},
            {"$set": {"is_valid_url": True}}
        )

    if invalid_ids:
        await jobs_collection.update_many(
            {"_id": {"$in": invalid_ids}},
            {"$set": {"is_valid_url": False}}
        )

    logger.info(
        "URL validation complete — valid: %d, invalid: %d",
        len(valid_ids), len(invalid_ids)
    )

    # Update the fetch log with the invalid count now that validation is done
    if log_id is not None:
        try:
            await job_fetch_logs_collection.update_one(
                {"_id": log_id},
                {"$set": {"jobs_invalid_url": len(invalid_ids)}}
            )
        except Exception as e:
            logger.warning("Failed to update fetch log with invalid URL count: %s", e)
