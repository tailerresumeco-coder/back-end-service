from dotenv import load_dotenv
load_dotenv()

import asyncio
import sys

if sys.platform.startswith("win"):
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.routers.resume_router import router as resume_router, keep_a_live
from app.routers.token_router import router as token_router
from apscheduler.schedulers.background import BackgroundScheduler

app = FastAPI(
    title="My FastAPI Service",
    version="1.0.0"
)

# ✅ CORRECT CORS CONFIG (Netlify → Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tailer-resume.netlify.app",
        "http://localhost:5173"
    ],
    allow_credentials=False,   # ✅ REQUIRED (no cookies/auth used)
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Content-Type"],
    expose_headers=["Content-Disposition"]
)

background_scheduler = BackgroundScheduler()

# ─────────────────────────────────────────────

@app.on_event("startup")
def startup_event():
    background_scheduler.add_job(keep_a_live, "interval", minutes=1)
    background_scheduler.start()

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
