import asyncio
import logging
from datetime import datetime, timezone

from pymongo import UpdateOne

from app.db import jobs_collection, job_fetch_logs_collection
from app.services.rapidapi_service import jsearch_fetch_jobs
from app.services.adzuna_service import adzuna_fetch_jobs
from app.services.job_validation_service import validate_jobs_batch

logger = logging.getLogger(__name__)


async def _upsert_jobs(normalized_jobs: list[dict]) -> tuple[int, int, list[str]]:
    """
    Bulk upsert jobs using dedup_hash as the unique key.
    Returns (stored_count, duplicate_count, upserted_ids).
    upserted_ids contains only the IDs of newly inserted documents.
    """
    if not normalized_jobs:
        return 0, 0, []

    operations = [
        UpdateOne(
            {"dedup_hash": job["dedup_hash"]},
            {"$setOnInsert": job},
            upsert=True,
        )
        for job in normalized_jobs
    ]

    result = await jobs_collection.bulk_write(operations, ordered=False)

    # upserted_ids is a dict of {operation_index: ObjectId} for newly inserted docs
    upserted_ids = [str(v) for v in result.upserted_ids.values()]
    stored = result.upserted_count
    duplicate = len(operations) - stored
    return stored, duplicate, upserted_ids


async def run_aggregation(full_refresh: bool = False) -> None:
    """
    Main orchestrator for job aggregation.
    Called by the scheduler every 6 hours (incremental) or weekly (full refresh).
    """
    run_type = "full_refresh" if full_refresh else "incremental"
    logger.info("Starting job aggregation — run_type: %s", run_type)

    # Create fetch log entry
    log_doc = {
        "source": "all",
        "run_type": run_type,
        "started_at": datetime.now(timezone.utc),
        "completed_at": None,
        "status": "running",
        "pages_fetched": 0,
        "jobs_fetched": 0,
        "jobs_stored": 0,
        "jobs_duplicate": 0,
        "jobs_invalid_url": 0,
        "error": None,
    }
    log_result = await job_fetch_logs_collection.insert_one(log_doc)
    log_id = log_result.inserted_id

    try:
        # Fetch from all sources concurrently
        # Each fetcher returns (jobs, pages_fetched)
        (jsearch_jobs, jsearch_pages), (adzuna_jobs, adzuna_pages) = await asyncio.gather(
            jsearch_fetch_jobs(full_refresh),
            adzuna_fetch_jobs(full_refresh),
        )

        total_pages = jsearch_pages + adzuna_pages
        all_jobs = jsearch_jobs + adzuna_jobs
        jobs_fetched = len(all_jobs)
        logger.info("Total jobs fetched from all sources: %d across %d pages", jobs_fetched, total_pages)

        if not all_jobs:
            await job_fetch_logs_collection.update_one(
                {"_id": log_id},
                {"$set": {
                    "status": "completed",
                    "completed_at": datetime.now(timezone.utc),
                    "jobs_fetched": 0,
                    "pages_fetched": total_pages,
                }}
            )
            return

        # Deduplicate within this batch before upserting
        seen_hashes: set[str] = set()
        unique_jobs = []
        for job in all_jobs:
            if job["dedup_hash"] not in seen_hashes:
                seen_hashes.add(job["dedup_hash"])
                unique_jobs.append(job)

        batch_duplicates = jobs_fetched - len(unique_jobs)

        # Phase 1: store all unique jobs with is_valid_url=None
        stored, db_duplicates, new_job_ids = await _upsert_jobs(unique_jobs)
        total_duplicates = batch_duplicates + db_duplicates

        logger.info(
            "Upsert complete — stored: %d, duplicates (batch): %d, duplicates (db): %d",
            stored, batch_duplicates, db_duplicates
        )

        # Mark run as completed — jobs_invalid_url will be back-filled by validator
        await job_fetch_logs_collection.update_one(
            {"_id": log_id},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
                "pages_fetched": total_pages,
                "jobs_fetched": jobs_fetched,
                "jobs_stored": stored,
                "jobs_duplicate": total_duplicates,
            }}
        )

        # Phase 2: validate URLs in background for newly inserted jobs only
        # Pass log_id so the validator can back-fill jobs_invalid_url when done
        if new_job_ids:
            asyncio.create_task(validate_jobs_batch(new_job_ids, log_id=log_id))
            logger.info("URL validation queued for %d newly inserted jobs", len(new_job_ids))
        else:
            logger.info("No new jobs inserted — skipping URL validation")

        logger.info("Job aggregation run complete — run_type: %s", run_type)

    except Exception as e:
        logger.error("Job aggregation failed: %s", e, exc_info=True)
        await job_fetch_logs_collection.update_one(
            {"_id": log_id},
            {"$set": {
                "status": "failed",
                "completed_at": datetime.now(timezone.utc),
                "error": str(e),
            }}
        )
