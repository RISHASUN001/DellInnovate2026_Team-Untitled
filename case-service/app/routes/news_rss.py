"""
RSS routes for curated mental health news items used by the dashboard.

Endpoint:
- GET /rss/straits-times-mental-health?limit=5
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import List, Dict
import re
import xml.etree.ElementTree as ET

import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from loguru import logger


router = APIRouter(prefix="/rss", tags=["rss"])

# Preferred source first, with resilient fallback feeds.
RSS_CANDIDATE_URLS = [
    "https://www.straitstimes.com/rss/singapore.xml",
    "https://www.straitstimes.com/rss/world.xml",
    "https://news.google.com/rss/search?q=site:straitstimes.com+mental+health+OR+stress+OR+anxiety+OR+depression&hl=en-SG&gl=SG&ceid=SG:en",
]

MENTAL_HEALTH_KEYWORDS = {
    "mental health",
    "stress",
    "anxiety",
    "depression",
    "suicide",
    "wellbeing",
    "well-being",
    "counselling",
    "therapy",
    "burnout",
    "trauma",
    "self-harm",
}


def _add_cors_headers(response: JSONResponse) -> JSONResponse:
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return response


def _extract_text(element: ET.Element, tag_name: str) -> str:
    child = element.find(tag_name)
    return (child.text or "").strip() if child is not None else ""


def _parse_pub_date(pub_date_raw: str) -> str:
    if not pub_date_raw:
        return datetime.now(timezone.utc).isoformat()
    try:
        dt = parsedate_to_datetime(pub_date_raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat()
    except Exception:
        return datetime.now(timezone.utc).isoformat()


def _is_relevant_mental_health_item(title: str, description: str) -> bool:
    corpus = f"{title} {description}".lower()
    corpus = re.sub(r"\s+", " ", corpus)
    return any(keyword in corpus for keyword in MENTAL_HEALTH_KEYWORDS)


async def _fetch_and_parse_rss(url: str) -> List[Dict[str, str]]:
    async with httpx.AsyncClient(timeout=12.0, follow_redirects=True) as client:
        response = await client.get(url, headers={"Accept": "application/rss+xml, application/xml"})
        response.raise_for_status()

    root = ET.fromstring(response.text)

    # RSS 2.0 items are usually under channel/item
    items = root.findall("./channel/item")
    if not items:
        # Basic Atom fallback
        items = root.findall("{http://www.w3.org/2005/Atom}entry")

    parsed_items: List[Dict[str, str]] = []
    for item in items:
        title = _extract_text(item, "title")
        link = _extract_text(item, "link")
        description = _extract_text(item, "description")
        pub_date = _extract_text(item, "pubDate")

        # Atom fallback fields
        if not title:
            title = _extract_text(item, "{http://www.w3.org/2005/Atom}title")
        if not link:
            atom_link = item.find("{http://www.w3.org/2005/Atom}link")
            if atom_link is not None:
                link = (atom_link.attrib.get("href") or "").strip()
        if not pub_date:
            pub_date = _extract_text(item, "{http://www.w3.org/2005/Atom}updated")

        if not title or not link:
            continue

        if not _is_relevant_mental_health_item(title, description):
            continue

        parsed_items.append(
            {
                "title": title,
                "link": link,
                "summary": description,
                "published": _parse_pub_date(pub_date),
                "source": "The Straits Times",
            }
        )

    return parsed_items


@router.options("/straits-times-mental-health")
async def options_straits_times_mental_health() -> JSONResponse:
    response = JSONResponse(content={})
    return _add_cors_headers(response)


@router.get("/straits-times-mental-health")
async def get_straits_times_mental_health_news(
    limit: int = Query(5, ge=1, le=20),
):
    """Return latest mental health-related Straits Times items for dashboard widget."""
    last_error = None

    for feed_url in RSS_CANDIDATE_URLS:
        try:
            items = await _fetch_and_parse_rss(feed_url)
            if items:
                # Sort by published date descending (string is ISO 8601 UTC)
                items.sort(key=lambda x: x["published"], reverse=True)
                response = JSONResponse(content=items[:limit])
                return _add_cors_headers(response)
        except Exception as exc:
            last_error = exc
            logger.warning("RSS fetch failed for %s: %s", feed_url, exc)

    logger.error("All RSS sources failed or returned no relevant items")
    if last_error is not None:
        raise HTTPException(status_code=502, detail=f"Unable to fetch RSS feed: {last_error}")
    raise HTTPException(status_code=404, detail="No relevant mental health news found")
