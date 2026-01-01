from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.routers.resume_router import router as resume_router

app = FastAPI(
    title="My FastAPI Service",
    version="1.0.0"
)

# ✅ CORRECT CORS CONFIG (Netlify → Render)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://tailer-resume.netlify.app"
    ],
    allow_credentials=False,   # ✅ REQUIRED (no cookies/auth used)
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

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
