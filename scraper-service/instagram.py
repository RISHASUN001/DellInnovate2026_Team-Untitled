# Copied and adapted from backend/instagram-scraper/instagram.py
# Only importable functions and constants for scraping are included
import json
import os
from typing import Dict, Optional
from urllib.parse import urlencode
import jmespath
from loguru import logger as log
from scrapfly import ScrapeConfig, ScrapflyClient

SCRAPFLY = os.getenv('SCRAPFLY_KEY')
BASE_CONFIG = {
    "asp": True,
    "country": "CA",
}
INSTAGRAM_APP_ID = "936619743392459"
INSTAGRAM_DOCUMENT_ID = "8845758582119845"
INSTAGRAM_ACCOUNT_DOCUMENT_ID = "9310670392322965"

def parse_user(data: Dict) -> Dict:
    result = jmespath.search(
        """{
        name: full_name,
        username: username,
        id: id,
        category: category_name,
        business_category: business_category_name,
        phone: business_phone_number,
        email: business_email,
        bio: biography,
        bio_links: bio_links[].url,
        homepage: external_url,
        followers: edge_followed_by.count,
        follows: edge_follow.count,
        facebook_id: fbid,
        is_private: is_private,
        is_verified: is_verified,
        profile_image: profile_pic_url_hd
    }""",
        data,
    )
    return result

async def scrape_user(username: str) -> Dict:
    log.info("scraping instagram user {}", username)
    result = await SCRAPFLY.async_scrape(
        ScrapeConfig(
            url=f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
            headers={"x-ig-app-id": INSTAGRAM_APP_ID},
            **BASE_CONFIG,
        )
    )
    data = json.loads(result.content)
    return parse_user(data["data"]["user"])
