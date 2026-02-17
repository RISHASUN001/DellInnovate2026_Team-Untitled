import re
from typing import List

def extract_shortcode_from_url(url: str) -> str:
    """Extract shortcode from Instagram post URL"""
    pattern = r"(?:instagram\.com/p/|instagram\.com/reel/)([^/?]+)"
    match = re.search(pattern, url)
    if match:
        return match.group(1)
    return url  # Return original if not a URL

def validate_usernames(usernames: List[str]) -> List[str]:
    """Validate and clean Instagram usernames"""
    cleaned = []
    for username in usernames:
        # Remove @ if present
        username = username.strip().lstrip('@')
        # Remove any URL parts
        if "instagram.com/" in username:
            username = username.split("instagram.com/")[-1].split("/")[0]
        # Basic validation
        if username and re.match(r'^[a-zA-Z0-9._]{1,30}$', username):
            cleaned.append(username)
    return cleaned

def format_result_for_response(data: dict) -> dict:
    """Format MongoDB result for API response"""
    if "_id" in data:
        data["_id"] = str(data["_id"])
    return data