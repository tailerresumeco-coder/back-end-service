import os
import io
import time
import boto3
from bson import ObjectId
from datetime import datetime, timezone
from fastapi import UploadFile, HTTPException
from pymongo import ReturnDocument

from app.db import user_resumes_collection, resumes_lists_collection

S3_BUCKET = os.getenv("S3_BUCKET_NAME", "io-resumes")
ALLOWED_TYPES = {"application/pdf", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
ALLOWED_EXTENSIONS = {".pdf", ".docx"}


def _serialize(doc: dict) -> dict:
    return {
        "id": str(doc["_id"]),
        "email": doc["email"],
        "name": doc["name"],
        "s3_key": doc["s3_key"],
        "file_type": doc["file_type"],
        "uploaded_at": doc["uploaded_at"],
        "is_active": doc["is_active"],
    }


async def upload_resume(email: str, file: UploadFile, name: str) -> dict:
    # Validate name
    if not name or not name.strip():
        raise HTTPException(status_code=400, detail="Resume name cannot be empty.")

    # Validate file type
    ext = os.path.splitext(file.filename or "")[-1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF and DOCX files are supported.")

    content_type = file.content_type or ""
    if content_type not in ALLOWED_TYPES and ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Invalid file type.")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Build S3 key: user-resumes/{email}/{timestamp}_{safe_name}{ext}
    safe_name = name.strip().replace(" ", "_")[:60]
    timestamp = int(time.time())
    s3_key = f"user-resumes/{email}/{timestamp}_{safe_name}{ext}"

    # Upload to S3
    content_type_map = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"}
    boto3.client(
        "s3",
        region_name=os.getenv("AWS_REGION"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
    ).upload_fileobj(
        io.BytesIO(file_bytes),
        S3_BUCKET,
        s3_key,
        ExtraArgs={"ContentType": content_type_map.get(ext, "application/octet-stream")},
    )

    # If this is the first resume, auto-activate it; otherwise leave inactive
    existing_count = await user_resumes_collection.count_documents({"email": email})
    is_active = existing_count == 0

    if is_active:
        # Deactivate any existing active (safety)
        await user_resumes_collection.update_many({"email": email}, {"$set": {"is_active": False}})

    doc = {
        "email": email,
        "name": name.strip(),
        "s3_key": s3_key,
        "file_type": ext.lstrip("."),
        "uploaded_at": datetime.now(timezone.utc),
        "is_active": is_active,
    }

    result = await user_resumes_collection.insert_one(doc)
    doc["_id"] = result.inserted_id
    return _serialize(doc)


async def list_resumes(email: str) -> list[dict]:
    cursor = user_resumes_collection.find({"email": email}).sort("uploaded_at", -1)
    return [_serialize(doc) async for doc in cursor]


async def get_active_resume(email: str) -> dict | None:
    doc = await user_resumes_collection.find_one({"email": email, "is_active": True})
    return _serialize(doc) if doc else None


async def activate_resume(email: str, resume_id: str) -> dict:
    try:
        oid = ObjectId(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume ID.")

    target = await user_resumes_collection.find_one({"_id": oid, "email": email})
    if not target:
        raise HTTPException(status_code=404, detail="Resume not found.")

    # Deactivate all, then activate the chosen one
    await user_resumes_collection.update_many({"email": email}, {"$set": {"is_active": False}})
    await user_resumes_collection.update_one({"_id": oid}, {"$set": {"is_active": True}})

    target["is_active"] = True
    return _serialize(target)


async def delete_resume(email: str, resume_id: str) -> dict:
    try:
        oid = ObjectId(resume_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid resume ID.")

    target = await user_resumes_collection.find_one({"_id": oid, "email": email})
    if not target:
        raise HTTPException(status_code=404, detail="Resume not found.")

    # Delete from S3
    try:
        boto3.client(
            "s3",
            region_name=os.getenv("AWS_REGION"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        ).delete_object(Bucket=S3_BUCKET, Key=target["s3_key"])
    except Exception:
        pass  # S3 delete failure is non-fatal; DB record still removed

    await user_resumes_collection.delete_one({"_id": oid})
    return {"deleted": True, "id": resume_id}

async def add_resumes_lists(email: str, resume_name: str) -> dict:
    data = {
        "email": email,
        "resume_name": resume_name,
        "created_on": datetime.now(timezone.utc),
        "updated_on": datetime.now(timezone.utc),
        "active": True
    }

    result = await resumes_lists_collection.insert_one(data)
    data["_id"] = str(result.inserted_id)  # optional: attach id

    return data

async def get_resume_lists(email: str) -> dict:
    try:
        cursor = resumes_lists_collection.find({
            "email": email,
            "active": True
        }).sort("created_on", -1)

        all_resumes = await cursor.to_list(length=None)

        # 🔥 FIX HERE
        for r in all_resumes:
            r["_id"] = str(r["_id"])

        return {
            "status": "success",
            "resumes": all_resumes
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error getting resumes: {str(e)}"
        )