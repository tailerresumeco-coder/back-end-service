import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

from app.utils.job_utils import make_dedup_hash

logger = logging.getLogger(__name__)

ADZUNA_BASE_URL = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


def _normalize_job(raw: dict, fetched_at: datetime) -> dict | None:
    """Map an Adzuna API result to the common job structure."""
    apply_url = (raw.get("redirect_url") or "").strip()
    title = (raw.get("title") or "").strip()
    company = (raw.get("company", {}).get("display_name") or "Unknown").strip()
    location = (raw.get("location", {}).get("display_name") or "India").strip()

    if not apply_url or not title:
        return None

    posted_at = None
    created_str = raw.get("created")
    if created_str:
        try:
            posted_at = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            posted_at = None

    salary_min = raw.get("salary_min")
    salary_max = raw.get("salary_max")

    return {
        "external_id": str(raw.get("id", "")),
        "source": "adzuna",
        "title": title,
        "company": company,
        "location": location,
        "description": raw.get("description"),
        "apply_url": apply_url,
        "salary_min": float(salary_min) if salary_min is not None else None,
        "salary_max": float(salary_max) if salary_max is not None else None,
        "salary_currency": "INR",
        "job_type": raw.get("contract_time"),
        "posted_at": posted_at,
        "fetched_at": fetched_at,
        "is_valid_url": None,
        "dedup_hash": make_dedup_hash(title, company, location, apply_url),
        "raw_data": raw,
    }


async def _fetch_page(
    client: httpx.AsyncClient,
    app_id: str,
    app_key: str,
    country: str,
    page: int,
    full_refresh: bool,
) -> list[dict]:
    """Fetch a single page from Adzuna. Returns raw job list."""
    url = ADZUNA_BASE_URL.format(country=country, page=page)
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": "50",
    }

    # Adzuna supports max_days_old for incremental fetches
    if not full_refresh:
        params["max_days_old"] = "1"

    max_retries = 3
    delay = 2

    for attempt in range(max_retries):
        try:
            response = await client.get(url, params=params, timeout=15)

            if response.status_code == 429:
                wait = delay * (2 ** attempt)
                logger.warning("Adzuna rate limit hit. Retrying in %ds...", wait)
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            data = response.json()
            return data.get("results", [])

        except httpx.HTTPStatusError as e:
            logger.warning("Adzuna HTTP error on page %d: %s", page, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(delay * (2 ** attempt))
            else:
                return []

        except Exception as e:
            logger.warning("Adzuna unexpected error on page %d: %s", page, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(delay * (2 ** attempt))
            else:
                return []

    return []


async def adzuna_fetch_jobs(full_refresh: bool) -> tuple[list[dict], int]:
    """
    Fetch jobs from Adzuna API.
    Gracefully skips if ADZUNA_APP_ID or ADZUNA_APP_KEY are not set.
    - full_refresh=False → max_days_old=1 (incremental)
    - full_refresh=True  → no date filter
    Returns (normalized_jobs, pages_fetched).
    """
    app_id = os.getenv("ADZUNA_APP_ID")
    app_key = os.getenv("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        logger.warning(
            "ADZUNA_APP_ID or ADZUNA_APP_KEY not set. Skipping Adzuna fetch."
        )
        return [], 0

    country = os.getenv("ADZUNA_COUNTRY", "in")
    max_pages = int(os.getenv("JOB_MAX_PAGES_PER_SOURCE", "20"))

    fetched_at = datetime.now(timezone.utc)
    all_jobs: list[dict] = []
    pages_fetched = 0

    async with httpx.AsyncClient() as client:
        for page in range(1, max_pages + 1):
            raw_jobs = await _fetch_page(client, app_id, app_key, country, page, full_refresh)

            if not raw_jobs:
                logger.info("Adzuna: no results on page %d, stopping.", page)
                break

            pages_fetched += 1

            for raw in raw_jobs:
                normalized = _normalize_job(raw, fetched_at)
                if normalized:
                    all_jobs.append(normalized)

            logger.info("Adzuna: page %d fetched — %d jobs", page, len(raw_jobs))

            # Adzuna returns 50 per page — fewer means last page
            if len(raw_jobs) < 50:
                break

    logger.info("Adzuna fetch complete — total normalized jobs: %d, pages: %d", len(all_jobs), pages_fetched)
    return all_jobs, pages_fetched
