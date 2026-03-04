from typing import Optional
import math

from app.db import users_collection

async def getAllUsers(
    page: int = 1,
    size: int = 10,
    search: Optional[str] = None
):
    # Pagination logic
    skip = (page - 1) * size

    # Base query
    query = {}

    # Search logic (case-insensitive)
    if search:
        query = {
            "$or": [
                {"name": {"$regex": search, "$options": "i"}},
                {"email": {"$regex": search, "$options": "i"}},
                {"username": {"$regex": search, "$options": "i"}},
            ]
        }

    # Fetch users
    cursor = (
        users_collection
        .find(query)
        .skip(skip)
        .limit(size)
        .sort("createdAt", -1)
    )

    users = []
    async for user in cursor:
        user["_id"] = str(user["_id"])
        users.append(user)

    # Total count
    total = await users_collection.count_documents(query)

    return {
        "page": page,
        "size": size,
        "total": total,
        "totalPages": math.ceil(total / size),
        "data": users
    }