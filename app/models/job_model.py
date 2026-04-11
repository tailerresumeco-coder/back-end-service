from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class JobModel(BaseModel):
    external_id: Optional[str] = None
    source: str                          # "jsearch" | "adzuna"
    title: str
    company: str
    location: str
    description: Optional[str] = None
    apply_url: str
    salary_min: Optional[float] = None
    salary_max: Optional[float] = None
    salary_currency: Optional[str] = None
    job_type: Optional[str] = None       # full-time, part-time, contract, intern
    posted_at: Optional[datetime] = None
    fetched_at: datetime
    is_valid_url: Optional[bool] = None  # None=pending, True=valid, False=invalid
    dedup_hash: str
    raw_data: Optional[dict] = None


class JobListResponse(BaseModel):
    page: int
    size: int
    total: int
    data: list[dict]


class JobFetchLogModel(BaseModel):
    source: str
    run_type: str                        # "incremental" | "full_refresh"
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str                          # "running" | "completed" | "failed"
    pages_fetched: int = 0
    jobs_fetched: int = 0
    jobs_stored: int = 0
    jobs_duplicate: int = 0
    jobs_invalid_url: int = 0
    error: Optional[str] = None
