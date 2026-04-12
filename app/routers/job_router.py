import asyncio
import logging
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, HTTPException, Query

from app.db import jobs_collection, job_fetch_logs_collection
from app.services.job_aggregation_service import run_aggregation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/jobs", tags=["Jobs"])


def _serialize(doc: dict) -> dict:
    return {**doc, "_id": str(doc["_id"])}


@router.get("")
async def get_jobs(
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    source: Optional[str] = Query(default=None, description="jsearch or adzuna"),
    job_type: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None, description="Search in title or company"),
):
    """
    Return paginated list of validated jobs from DB.
    Users always read from DB — no live API calls.
    """
    query: dict = {"is_valid_url": True}

    if source:
        query["source"] = source

    if job_type:
        query["job_type"] = {"$regex": job_type, "$options": "i"}

    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"company": {"$regex": search, "$options": "i"}},
            {"location": {"$regex": search, "$options": "i"}},
        ]

    skip = (page - 1) * size
    cursor = (
        jobs_collection.find(query, {"raw_data": 0})
        .sort("fetched_at", -1)
        .skip(skip)
        .limit(size)
    )
    jobs = await cursor.to_list(length=size)
    total = await jobs_collection.count_documents(query)

    return {
        "status": "success",
        "page": page,
        "size": size,
        "total": total,
        "data": [_serialize(j) for j in jobs],
    }


@router.get("/logs")
async def get_fetch_logs(limit: int = Query(default=10, ge=1, le=50)):
    """Return recent job fetch run logs."""
    cursor = job_fetch_logs_collection.find().sort("started_at", -1).limit(limit)
    logs = await cursor.to_list(length=limit)
    return {
        "status": "success",
        "data": [_serialize(log) for log in logs],
    }


@router.get("/{job_id}")
async def get_job(job_id: str):
    """Return a single job by ID."""
    try:
        oid = ObjectId(job_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid job ID format")

    job = await jobs_collection.find_one({"_id": oid, "is_valid_url": True}, {"raw_data": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {"status": "success", "data": _serialize(job)}


@router.post("/trigger")
async def trigger_fetch(full_refresh: bool = Query(default=False)):
    """
    Manually trigger a job aggregation run.
    Runs in background — returns immediately.
    """
    asyncio.create_task(run_aggregation(full_refresh=full_refresh))
    run_type = "full_refresh" if full_refresh else "incremental"
    logger.info("Manual job aggregation triggered — run_type: %s", run_type)
    return {
        "status": "success",
        "message": f"Job aggregation ({run_type}) started in background.",
    }
