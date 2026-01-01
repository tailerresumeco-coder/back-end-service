from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Any, Dict
from fastapi.middleware.cors import CORSMiddleware
from app.routers.resume_router import router as resume_router

app = FastAPI(
    title="My FastAPI Service",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware, 
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://tailer-resume.netlify.app" 
    ],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 1) Simple GET endpoint
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI 🚀"}

# 2) Path & query params
@app.get("/items/{item_id}")
def read_item(item_id: int, q: str | None = None):
    return {"item_id": item_id, "query": q}

# 3) Request body with Pydantic
class Item(BaseModel):
    name: str
    price: float
    in_stock: bool = True

@app.post("/items")
def create_item(item: Item):
    # In real app, save to DB here
    return {
        "message": "Item created",
        "item": item,
    }

app.include_router(resume_router)


# pip install -r requirements.txt
# python -m uvicorn app.main:app --reload
