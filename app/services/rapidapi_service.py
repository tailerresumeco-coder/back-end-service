import asyncio
import logging
import os
from datetime import datetime, timezone

import httpx

from app.utils.job_utils import make_dedup_hash

logger = logging.getLogger(__name__)

JSEARCH_BASE_URL = "https://jsearch.p.rapidapi.com/search"


def _normalize_job(raw: dict, fetched_at: datetime) -> dict | None:
    """Map a JSearch API result to the common job structure."""
    apply_url = (raw.get("job_apply_link") or "").strip()
    title = (raw.get("job_title") or "").strip()
    company = (raw.get("employer_name") or "").strip()

    city = raw.get("job_city") or ""
    country = raw.get("job_country") or ""
    location = ", ".join(filter(None, [city, country])).strip() or "India"

    if not apply_url or not title or not company:
        return None

    posted_at = None
    posted_str = raw.get("job_posted_at_datetime_utc")
    if posted_str:
        try:
            posted_at = datetime.fromisoformat(posted_str.replace("Z", "+00:00"))
        except (ValueError, AttributeError):
            posted_at = None

    return {
        "external_id": raw.get("job_id"),
        "source": "jsearch",
        "title": title,
        "company": company,
        "location": location,
        "description": raw.get("job_description"),
        "apply_url": apply_url,
        "salary_min": raw.get("job_min_salary"),
        "salary_max": raw.get("job_max_salary"),
        "salary_currency": raw.get("job_salary_currency"),
        "job_type": raw.get("job_employment_type"),
        "posted_at": posted_at,
        "fetched_at": fetched_at,
        "is_valid_url": None,
        "dedup_hash": make_dedup_hash(title, company, location, apply_url),
        "raw_data": raw,
    }


async def _fetch_page(
    client: httpx.AsyncClient,
    headers: dict,
    query: str,
    page: int,
    date_posted: str | None,
) -> list[dict]:
    """Fetch a single page from JSearch. Returns raw job list."""
    params = {
        "query": query,
        "page": str(page),
        "num_pages": "1",
    }
    if date_posted:
        params["date_posted"] = date_posted

    max_retries = 3
    delay = 2

    for attempt in range(max_retries):
        try:
            response = await client.get(
                JSEARCH_BASE_URL,
                headers=headers,
                params=params,
                timeout=15,
            )

            if response.status_code == 429:
                wait = delay * (2 ** attempt)
                logger.warning("JSearch rate limit hit. Retrying in %ds...", wait)
                await asyncio.sleep(wait)
                continue

            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

        except httpx.HTTPStatusError as e:
            logger.warning("JSearch HTTP error on page %d: %s", page, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(delay * (2 ** attempt))
            else:
                return []

        except Exception as e:
            logger.warning("JSearch unexpected error on page %d: %s", page, e)
            if attempt < max_retries - 1:
                await asyncio.sleep(delay * (2 ** attempt))
            else:
                return []

    return []


async def jsearch_fetch_jobs(full_refresh: bool) -> tuple[list[dict], int]:
    """
    Fetch jobs from JSearch API.
    - full_refresh=False → date_posted="today" (incremental)
    - full_refresh=True  → no date filter (all available jobs)
    Returns (normalized_jobs, pages_fetched).
    """
    api_key = os.getenv("RAPIDAPI_KEY") or os.getenv("X-RapidAPI-Key")
    api_host = os.getenv("RAPIDAPI_HOST") or os.getenv("X-RapidAPI-Host", "jsearch.p.rapidapi.com")

    if not api_key:
        logger.error("X-RapidAPI-Key not set. Skipping JSearch fetch.")
        return [], 0

    query = os.getenv("JOB_SEARCH_QUERY", "jobs in India")
    max_pages = int(os.getenv("JOB_MAX_PAGES_PER_SOURCE", "20"))
    date_posted = None if full_refresh else "today"

    headers = {
        "X-RapidAPI-Key": api_key,
        "X-RapidAPI-Host": api_host,
    }

    fetched_at = datetime.now(timezone.utc)
    all_jobs: list[dict] = []
    pages_fetched = 0

    async with httpx.AsyncClient() as client:
        for page in range(1, max_pages + 1):
            raw_jobs = await _fetch_page(client, headers, query, page, date_posted)

            if not raw_jobs:
                logger.info("JSearch: no results on page %d, stopping.", page)
                break

            pages_fetched += 1

            for raw in raw_jobs:
                normalized = _normalize_job(raw, fetched_at)
                if normalized:
                    all_jobs.append(normalized)

            logger.info("JSearch: page %d fetched — %d jobs", page, len(raw_jobs))

            # JSearch returns 10 per page — fewer means last page
            if len(raw_jobs) < 10:
                break

    logger.info("JSearch fetch complete — total normalized jobs: %d, pages: %d", len(all_jobs), pages_fetched)
    return all_jobs, pages_fetched
