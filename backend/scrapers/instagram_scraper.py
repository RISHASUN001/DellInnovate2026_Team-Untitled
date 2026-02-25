"""
Instagram scraper using Scrapfly API
Based on: https://scrapfly.io/blog/how-to-scrape-instagram/
"""
import httpx
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
import asyncio
from typing import Dict, Optional, AsyncGenerator, List
from urllib.parse import quote, urlencode
import jmespath
from loguru import logger as log
from scrapfly import ScrapeConfig, ScrapflyClient
from dotenv import load_dotenv

load_dotenv()

class InstagramScraper:
    def __init__(self, scrapfly_key: str = None):
        self.scrapfly_key = scrapfly_key or os.getenv("SCRAPFLY_KEY")
        if not self.scrapfly_key:
            raise ValueError("SCRAPFLY_KEY is required")
        
        self.client = ScrapflyClient(key=self.scrapfly_key)
        self.base_config = {
            "asp": True,  # Anti Scraping Protection bypass
            "country": "US",  # Change country as needed
            "cache": True,  # Enable caching for development
        }
        self.INSTAGRAM_APP_ID = "936619743392459"  # Public app id for instagram.com
        self.INSTAGRAM_DOCUMENT_ID = "8845758582119845"  # Constant id for post documents
        self.INSTAGRAM_ACCOUNT_DOCUMENT_ID = "9310670392322965"
        self.INSTAGRAM_POST_QUERY_HASH = "9f8827793ef34641b2fb195d4c411ebc"  # Alternative query hash for posts
        
        # Rate limiting settings
        self.request_delay = 2.0  # Delay between requests in seconds
        self.max_retries = 3
        self.retry_delay = 5  # Initial retry delay in seconds

    async def _make_request_with_retry(self, scrape_config: ScrapeConfig, retry_count: int = 0) -> any:
        """Make a request with retry logic and rate limiting"""
        try:
            # Add delay before request to avoid rate limiting
            await asyncio.sleep(self.request_delay)
            
            result = await self.client.async_scrape(scrape_config)
            
            # Check for rate limiting in response
            if hasattr(result, 'status_code'):
                if result.status_code == 429:
                    if retry_count < self.max_retries:
                        wait_time = self.retry_delay * (2 ** retry_count)  # Exponential backoff
                        log.warning(f"Rate limited (429). Retrying in {wait_time} seconds... (Attempt {retry_count + 1}/{self.max_retries})")
                        await asyncio.sleep(wait_time)
                        return await self._make_request_with_retry(scrape_config, retry_count + 1)
                    else:
                        raise Exception(f"Max retries exceeded for rate limiting")
            
            return result
            
        except Exception as e:
            if "429" in str(e) or "rate limit" in str(e).lower():
                if retry_count < self.max_retries:
                    wait_time = self.retry_delay * (2 ** retry_count)
                    log.warning(f"Rate limited. Retrying in {wait_time} seconds... (Attempt {retry_count + 1}/{self.max_retries})")
                    await asyncio.sleep(wait_time)
                    return await self._make_request_with_retry(scrape_config, retry_count + 1)
            
            # For other errors, retry as well
            if retry_count < self.max_retries:
                wait_time = self.retry_delay * (2 ** retry_count)
                log.warning(f"Request failed: {e}. Retrying in {wait_time} seconds... (Attempt {retry_count + 1}/{self.max_retries})")
                await asyncio.sleep(wait_time)
                return await self._make_request_with_retry(scrape_config, retry_count + 1)
            
            raise

    def parse_user(self, data: Dict) -> Dict:
        """Reduce the user data to the relevant fields"""
        log.debug(f"Parsing user data for {data.get('username', 'unknown')}")
        result = jmespath.search(
            """{
            name: full_name,
            username: username,
            user_id: id,
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
            profile_image: profile_pic_url_hd,
            video_count: edge_felix_video_timeline.count,
            videos: edge_felix_video_timeline.edges[].node.{
                post_id: id, 
                title: title,
                shortcode: shortcode,
                thumb: display_url,
                url: video_url,
                views: video_view_count,
                tagged: edge_media_to_tagged_user.edges[].node.user.username,
                captions: edge_media_to_caption.edges[].node.text,
                comments_count: edge_media_to_comment.count,
                comments_disabled: comments_disabled,
                taken_at: taken_at_timestamp,
                likes: edge_liked_by.count,
                location: location.name,
                duration: video_duration
            },
            image_count: edge_owner_to_timeline_media.count,
            images: edge_owner_to_timeline_media.edges[].node.{
                post_id: id, 
                title: title,
                shortcode: shortcode,
                src: display_url,
                url: video_url,
                views: video_view_count,
                tagged: edge_media_to_tagged_user.edges[].node.user.username,
                captions: edge_media_to_caption.edges[].node.text,
                comments_count: edge_media_to_comment.count,
                comments_disabled: comments_disabled,
                taken_at: taken_at_timestamp,
                likes: edge_liked_by.count,
                location: location.name,
                accessibility_caption: accessibility_caption,
                duration: video_duration
            },
            saved_count: edge_saved_media.count,
            collections_count: edge_saved_media.count,
            related_profiles: edge_related_profiles.edges[].node.username
        }""",
            data,
        )
        return result

    async def scrape_user(self, username: str) -> Dict:
        """Scrape instagram user's data"""
        log.info(f"Scraping instagram user: {username}")
        try:
            result = await self._make_request_with_retry(
                ScrapeConfig(
                    url=f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
                    headers={"x-ig-app-id": self.INSTAGRAM_APP_ID},
                    **self.base_config,
                )
            )
            data = await self._parse_json_result(result, f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}")
            user_data = self.parse_user(data["data"]["user"])

            # ensure username present
            user_data["username"] = username

            # normalize and scrape bio links (non-scrapfly)
            bio_links = user_data.get("bio_links") or []
            bio_links_data = []
            for raw_link in bio_links:
                try:
                    link = raw_link or ""
                    # normalize scheme
                    if link and not urlparse(link).scheme:
                        link = "http://" + link
                    meta = await self.scrape_external_link(link)
                    bio_links_data.append(meta)
                except Exception as e:
                    log.warning("error scraping bio link %s: %s", raw_link, e)
                    bio_links_data.append({"url": raw_link, "error": str(e)})

            # always attach (even if empty) so downstream can persist it
            user_data["bio_links_data"] = bio_links_data

            return user_data
        except Exception as e:
            log.error(f"Failed to scrape user {username}: {e}")
            raise

    def parse_comments(self, data: Dict) -> Dict:
        """Parse the comments data from the post dataset"""
        # Limit comments to first 500 if more exist
        comments_data = {}
        
        if "edge_media_to_comment" in data:
            comments_data = jmespath.search(
                """{
                    comments_count: edge_media_to_comment.count,
                    comments_disabled: comments_disabled,
                    comments_next_page: edge_media_to_comment.page_info.end_cursor,
                    comments: edge_media_to_comment.edges[].node.{
                        id: id,
                        text: text,
                        created_at: created_at,
                        owner_id: owner.id,
                        owner: owner.username,
                        owner_verified: owner.is_verified,
                        viewer_has_liked: viewer_has_liked
                    }
                }""",
                data,
            )
        elif "edge_media_to_parent_comment" in data:
            comments_data = jmespath.search(
                """{
                    comments_count: edge_media_to_parent_comment.count,
                    comments_disabled: comments_disabled,
                    comments_next_page: edge_media_to_parent_comment.page_info.end_cursor,
                    comments: edge_media_to_parent_comment.edges[].node.{
                        id: id,
                        text: text,
                        created_at: created_at,
                        owner: owner.username,
                        owner_verified: owner.is_verified,
                        viewer_has_liked: viewer_has_liked,
                        likes: edge_liked_by.count
                    }
                }""",
                data,
            )
        else:
            # Try alternative comment structure
            comments_data = {
                "comments_count": data.get("comment_count", 0),
                "comments_disabled": data.get("comments_disabled", False),
                "comments": []
            }
        
        # Limit comments to first 500
        if comments_data and comments_data.get("comments"):
            comments_data["comments"] = comments_data["comments"][:500]
            
        return comments_data

    def parse_post(self, data: Dict) -> Dict:
        """Reduce post dataset to the most important fields"""
        log.debug(f"Parsing post data for {data.get('shortcode', 'unknown')}")
        
        # Try to get data from different possible paths
        post_media = data.get("data", {}).get("xdt_shortcode_media", data)
        
        result = jmespath.search(
            """{
            post_id: id,
            shortcode: shortcode,
            dimensions: dimensions,
            src: display_url,
            thumbnail_src: thumbnail_src,
            media_preview: media_preview,
            video_url: video_url,
            views: video_view_count,
            likes: edge_media_preview_like.count,
            location: location.name,
            taken_at: taken_at_timestamp,
            related: edge_web_media_to_related_media.edges[].node.shortcode,
            type: product_type,
            video_duration: video_duration,
            music: clips_music_attribution_info,
            is_video: is_video,
            tagged_users: edge_media_to_tagged_user.edges[].node.user.username,
            captions: edge_media_to_caption.edges[].node.text,
            related_profiles: edge_related_profiles.edges[].node.username,
            owner: owner.username
        }""",
            post_media,
        )
        
        # Get comments data
        comments_data = self.parse_comments(post_media)
        result.update(comments_data)
        
        # Extract username from the URL or data if available
        if "owner" in post_media and "username" in post_media["owner"]:
            result["username"] = post_media["owner"]["username"]
            
        return result

    async def scrape_post(self, url_or_shortcode: str) -> Dict:
        """Scrape single Instagram post data with fallback methods"""
        if "http" in url_or_shortcode:
            shortcode = url_or_shortcode.split("/p/")[-1].split("/")[0]
        else:
            shortcode = url_or_shortcode
            
        log.info(f"Scraping instagram post: {shortcode}")
        
        # Try multiple methods to get post data
        post_data = None
        errors = []
        
        # Method 1: GraphQL with document ID
        try:
            variables = json.dumps({
                'shortcode': shortcode,
                'fetch_tagged_user_count': None,
                'hoisted_comment_id': None,
                'hoisted_reply_id': None
            }, separators=(',', ':'))
            
            body = f"variables={variables}&doc_id={self.INSTAGRAM_DOCUMENT_ID}"
            url = "https://www.instagram.com/graphql/query"
            
            result = await self._make_request_with_retry(
                ScrapeConfig(
                    url=url,
                    method="POST",
                    body=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    **self.base_config
                )
            )

            data = await self._parse_json_result(result, url)
            if "data" in data and data["data"]:
                post_data = self.parse_post(data)
                post_data["shortcode"] = shortcode
                log.success(f"Successfully scraped post {shortcode} using Method 1")
                return post_data
        except Exception as e:
            errors.append(f"Method 1 failed: {str(e)}")
            log.debug(f"Method 1 failed for {shortcode}: {e}")

        # Method 2: Alternative GraphQL endpoint with query hash
        try:
            variables = json.dumps({
                "shortcode": shortcode,
                "include_reel_comment": True,
                "include_logged_out": True
            }, separators=(',', ':'))
            
            url = f"https://www.instagram.com/graphql/query/?query_hash={self.INSTAGRAM_POST_QUERY_HASH}&variables={quote(variables)}"
            
            result = await self._make_request_with_retry(
                ScrapeConfig(
                    url=url,
                    method="GET",
                    headers={"content-type": "application/x-www-form-urlencoded"},
                    **self.base_config
                )
            )

            data = await self._parse_json_result(result, url)
            if "data" in data and data["data"] and "shortcode_media" in data["data"]:
                post_data = self.parse_post(data["data"]["shortcode_media"])
                post_data["shortcode"] = shortcode
                log.success(f"Successfully scraped post {shortcode} using Method 2")
                return post_data
        except Exception as e:
            errors.append(f"Method 2 failed: {str(e)}")
            log.debug(f"Method 2 failed for {shortcode}: {e}")

        # Method 3: Try to get from web profile info (limited data)
        try:
            result = await self._make_request_with_retry(
                ScrapeConfig(
                    url=f"https://www.instagram.com/p/{shortcode}/embed/?cr=1",
                    **self.base_config,
                )
            )
            # This would need HTML parsing, but for now we'll return basic data
            log.warning(f"Using fallback for post {shortcode}")
            return {
                "shortcode": shortcode,
                "comments": [],
                "comments_count": 0,
                "comments_disabled": False,
                "tagged_users": [],
                "captions": [],
                "likes": 0,
                "is_video": False,
                "username": None
            }
        except Exception as e:
            errors.append(f"Method 3 failed: {str(e)}")

        # If all methods failed, raise error
        error_msg = f"All methods failed to scrape post {shortcode}: {'; '.join(errors)}"
        log.error(error_msg)
        raise Exception(error_msg)

    def parse_user_posts(self, data: Dict) -> Dict:
        """Enhanced parser for user posts to include comments and other details"""
        log.debug(f"Parsing enhanced post data for {data.get('code', 'unknown')}")
        
        # First, get the basic post info
        result = jmespath.search(
            """{
            post_id: id,
            shortcode: code,
            caption: caption,
            taken_at: taken_at,
            video_versions: video_versions,
            image_versions2: image_versions2,
            original_height: original_height,
            original_width: original_width,
            link: link,
            title: title,
            comment_count: comment_count,
            top_likers: top_likers,
            like_count: like_count,
            usertags: usertags,
            clips_metadata: clips_metadata
        }""",
            data,
        )
        
        # Parse comments from the comments field if available
        if "comments" in data and data["comments"]:
            comments_list = []
            for comment in data["comments"]:
                if isinstance(comment, dict):
                    comment_data = {
                        "id": comment.get("pk"),
                        "text": comment.get("text"),
                        "created_at": comment.get("created_at"),
                        "owner_id": comment.get("user", {}).get("pk"),
                        "owner": comment.get("user", {}).get("username"),
                        "owner_verified": comment.get("user", {}).get("is_verified", False),
                        "likes": comment.get("comment_like_count", 0)
                    }
                    comments_list.append(comment_data)
            
            # Limit to first 500 comments
            result["comments"] = comments_list[:500]
            result["comments_count"] = len(comments_list)
            result["comments_disabled"] = False
        else:
            result["comments"] = []
            result["comments_count"] = 0
            result["comments_disabled"] = False
        
        # Parse tagged users
        if "usertags" in data and data["usertags"]:
            tagged_users = []
            for tag in data["usertags"].get("in", []):
                if "user" in tag:
                    tagged_users.append(tag["user"].get("username"))
            result["tagged_users"] = tagged_users
        else:
            result["tagged_users"] = []
        
        # Parse captions
        if "caption" in data and data["caption"]:
            if isinstance(data["caption"], dict):
                result["captions"] = [data["caption"].get("text", "")]
            else:
                result["captions"] = [str(data["caption"])]
        else:
            result["captions"] = []
        
        # Parse location
        if "location" in data and data["location"]:
            result["location"] = data["location"].get("name")
        
        # Parse media info
        result["is_video"] = data.get("media_type") == 2
        
        if result["is_video"] and "video_versions" in data and data["video_versions"]:
            result["video_url"] = data["video_versions"][0].get("url")
            result["views"] = data.get("play_count", 0)
            result["video_duration"] = data.get("video_duration")
        
        # Parse image URL
        if "image_versions2" in data and data["image_versions2"]:
            candidates = data["image_versions2"].get("candidates", [])
            if candidates:
                result["src"] = candidates[0].get("url")
                result["thumbnail_src"] = candidates[0].get("url")
        
        # Add username if available
        if "user" in data:
            result["username"] = data["user"].get("username")
        
        return result

    async def scrape_user_posts(self, username: str, page_size=12, max_pages: Optional[int] = None) -> AsyncGenerator[Dict, None]:
        """Scrape all posts of an instagram user with enhanced data including comments"""
        base_url = "https://www.instagram.com/graphql/query/"
        variables = {
            "after": None,
            "before": None,
            "data": {
                "count": page_size,
                "include_reel_media_seen_timestamp": True,
                "include_relationship_info": True,
                "latest_besties_reel_media": True,
                "latest_reel_media": True
            },
            "first": page_size,
            "last": None,
            "username": username,
            "__relay_internal__pv__PolarisIsLoggedInrelayprovider": True,
            "__relay_internal__pv__PolarisShareSheetV3relayprovider": True
        }

        prev_cursor = None
        page_number = 1
        post_count = 0

        while True:
            try:
                params = {
                    "doc_id": self.INSTAGRAM_ACCOUNT_DOCUMENT_ID,
                    "variables": json.dumps(variables, separators=(",", ":"))
                }

                final_url = f"{base_url}?{urlencode(params)}"
                result = await self._make_request_with_retry(ScrapeConfig(
                    final_url, 
                    **self.base_config, 
                    method="GET",
                    headers={"content-type": "application/x-www-form-urlencoded"},
                ))

                data = await self._parse_json_result(result, final_url)
                
                posts = data["data"]["xdt_api__v1__feed__user_timeline_graphql_connection"]
                
                for post in posts["edges"]:
                    post_node = post["node"]
                    shortcode = post_node.get("code")
                    
                    if shortcode:
                        try:
                            # Get detailed post data including comments
                            detailed_post = await self.scrape_post(shortcode)
                            yield detailed_post
                            post_count += 1
                        except Exception as e:
                            log.warning(f"Failed to get detailed post for {shortcode}, using basic data: {e}")
                            post_data = self.parse_user_posts(post_node)
                            post_data["username"] = username
                            # Ensure comments is always a list
                            if "comments" not in post_data:
                                post_data["comments"] = []
                            yield post_data
                            post_count += 1
                    else:
                        post_data = self.parse_user_posts(post_node)
                        post_data["username"] = username
                        # Ensure comments is always a list
                        if "comments" not in post_data:
                            post_data["comments"] = []
                        yield post_data
                        post_count += 1

                page_info = posts["page_info"]
                log.info(f"Scraped posts page {page_number} for {username} (total posts so far: {post_count})")
                
                if not page_info.get("has_next_page"):
                    break

                if page_info.get("end_cursor") == prev_cursor:
                    log.warning("Found no new posts, breaking")
                    break

                prev_cursor = page_info["end_cursor"]
                variables["after"] = page_info["end_cursor"]
                page_number += 1

                if max_pages and page_number > max_pages:
                    break
                    
            except Exception as e:
                log.error(f"Failed to scrape posts page for {username}: {e}")
                break

    async def scrape_multiple_users(self, usernames: List[str], scrape_posts: bool = True, max_posts_per_user: Optional[int] = None) -> Dict:
        """Scrape multiple Instagram users"""
        results = {
            "users": [],
            "posts": []
        }
        
        for username in usernames:
            try:
                log.info(f"Processing user: {username}")
                
                # Add delay between users to avoid rate limiting
                if len(results["users"]) > 0:
                    await asyncio.sleep(3)
                
                # Scrape user profile
                user_data = await self.scrape_user(username)
                results["users"].append(user_data)
                
                # Scrape user posts if requested
                if scrape_posts:
                    posts = []
                    async for post in self.scrape_user_posts(username, max_pages=max_posts_per_user):
                        posts.append(post)
                    results["posts"].extend(posts)
                    log.info(f"Scraped {len(posts)} posts for {username}")
                    
            except Exception as e:
                log.error(f"Error processing user {username}: {e}")
                results["users"].append({
                    "username": username,
                    "error": str(e)
                })
        
        return results

    async def scrape_external_link(self, url: str) -> Dict:
        """Fetch simple metadata (title, description, image) for an external URL using httpx + bs4."""
        try:
            async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": "Mozilla/5.0"}) as client:
                resp = await client.get(url, follow_redirects=True)
            if resp.status_code != 200:
                return {"url": url, "status": resp.status_code}
            content_type = resp.headers.get("content-type", "")
            if "html" not in content_type:
                return {"url": url, "status": resp.status_code, "content_type": content_type}
            soup = BeautifulSoup(resp.text, "html.parser")
            title = None
            if soup.title and soup.title.string:
                title = soup.title.string.strip()
            desc_tag = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
            description = desc_tag.get("content").strip() if desc_tag and desc_tag.get("content") else None
            img_tag = soup.find("meta", attrs={"property": "og:image"}) or soup.find("img")
            image = None
            if img_tag:
                if img_tag.name == "meta":
                    image = img_tag.get("content")
                else:
                    image = img_tag.get("src")
            if image and image.startswith("/"):
                image = urljoin(url, image)
            return {"url": url, "status": 200, "title": title, "description": description, "image": image}
        except Exception as e:
            log.warning("failed to scrape external link %s: %s", url, e)
            return {"url": url, "error": str(e)}

    async def _parse_json_result(self, result, url: str | None = None) -> Dict:
        """Safely parse result.content as JSON; log helpful debug on failure."""
        status = getattr(result, "status_code", None)
        body = getattr(result, "content", None)
        text = None
        if body is None:
            log.error("Empty response from Scrapfly for %s (status=%s)", url or "<unknown>", status)
            raise ValueError(f"Empty response from scraper (status={status})")
        try:
            if isinstance(body, (bytes, bytearray)):
                text = body.decode("utf-8", errors="replace")
            else:
                text = str(body)
            return json.loads(text)
        except Exception as e:
            # log first chunk of body to help debugging (avoid huge dumps)
            preview = text[:1000] if text else "<no-text>"
            log.error("Failed to parse JSON from %s (status=%s): %s\nBody preview: %s", url or "<unknown>", status, e, preview)
            raise ValueError(f"Failed to parse JSON from scraper (status={status}): {e}")