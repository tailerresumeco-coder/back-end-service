from dotenv import load_dotenv
load_dotenv()

import asyncio
import os
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.routers.resume_router import router as resume_router
from app.routers.token_router import router as token_router
from app.routers.mail_router import router as mail_router
from app.routers.job_router import router as job_router
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

app = FastAPI(
    title="My FastAPI Service",
    version="1.0.0"
)

# ✅ CORRECT CORS CONFIG (Netlify → Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tailer-resume.netlify.app",
        "http://localhost:5173",
        "https://tailerresume.com",
        "https://www.tailerresume.com"
    ],
    allow_credentials=False,   # ✅ REQUIRED (no cookies/auth used)
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"]
)

from app.db import setup_job_indexes
from app.services.job_aggregation_service import run_aggregation

scheduler = AsyncIOScheduler()

# ─────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    # Set up MongoDB indexes for jobs
    await setup_job_indexes()

    # Incremental run — every N hours (default 6)
    interval_hours = int(os.getenv("JOB_FETCH_INTERVAL_HOURS", "6"))
    scheduler.add_job(
        run_aggregation,
        trigger=IntervalTrigger(hours=interval_hours),
        kwargs={"full_refresh": False},
        id="job_aggregation_incremental",
        name="Incremental job fetch",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    # Full refresh — every Sunday at 1:00 AM
    scheduler.add_job(
        run_aggregation,
        trigger=CronTrigger(day_of_week="sun", hour=1, minute=0),
        kwargs={"full_refresh": True},
        id="job_aggregation_full_refresh",
        name="Weekly full job refresh",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=3600,
    )

    scheduler.start()


@app.on_event("shutdown")
def shutdown():
    scheduler.shutdown(wait=False)


# ─────────────────────────────────────────────

@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI 🚀"}

@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "query": q}

class Item(BaseModel):
    name: str
    price: float
    in_stock: bool = True

@app.post("/items")
def create_item(item: Item):
    return {
        "message": "Item created",
        "item": item,
    }

# Include routers LAST
app.include_router(resume_router)
app.include_router(token_router)
app.include_router(mail_router)
app.include_router(job_router)
