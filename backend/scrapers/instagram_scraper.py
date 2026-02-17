"""
Instagram scraper using Scrapfly API
Based on: https://scrapfly.io/blog/how-to-scrape-instagram/
"""
import json
import os
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
            result = await self.client.async_scrape(
                ScrapeConfig(
                    url=f"https://i.instagram.com/api/v1/users/web_profile_info/?username={username}",
                    headers={"x-ig-app-id": self.INSTAGRAM_APP_ID},
                    **self.base_config,
                )
            )
            data = json.loads(result.content)
            user_data = self.parse_user(data["data"]["user"])
            user_data["username"] = username  # Ensure username is set
            return user_data
        except Exception as e:
            log.error(f"Failed to scrape user {username}: {e}")
            raise

    def parse_comments(self, data: Dict) -> Dict:
        """Parse the comments data from the post dataset"""
        if "edge_media_to_comment" in data:
            return jmespath.search(
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
        else:
            return jmespath.search(
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

    def parse_post(self, data: Dict) -> Dict:
        """Reduce post dataset to the most important fields"""
        log.debug(f"Parsing post data for {data.get('shortcode', 'unknown')}")
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
            related_profiles: edge_related_profiles.edges[].node.username
        }""",
            data,
        )
        comments_data = self.parse_comments(data)
        result.update(comments_data)
        
        # Extract username from the URL or data if available
        if "owner" in data and "username" in data["owner"]:
            result["username"] = data["owner"]["username"]
            
        return result

    async def scrape_post(self, url_or_shortcode: str) -> Dict:
        """Scrape single Instagram post data"""
        if "http" in url_or_shortcode:
            shortcode = url_or_shortcode.split("/p/")[-1].split("/")[0]
        else:
            shortcode = url_or_shortcode
            
        log.info(f"Scraping instagram post: {shortcode}")
        try:
            variables = json.dumps({
                'shortcode': shortcode,
                'fetch_tagged_user_count': None,
                'hoisted_comment_id': None,
                'hoisted_reply_id': None
            }, separators=(',', ':'))
            
            body = f"variables={variables}&doc_id={self.INSTAGRAM_DOCUMENT_ID}"
            url = "https://www.instagram.com/graphql/query"
            
            result = await self.client.async_scrape(
                ScrapeConfig(
                    url=url,
                    method="POST",
                    body=body,
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                    **self.base_config
                )
            )

            data = json.loads(result.content)
            post_data = self.parse_post(data["data"]["xdt_shortcode_media"])
            post_data["shortcode"] = shortcode
            return post_data
        except Exception as e:
            log.error(f"Failed to scrape post {shortcode}: {e}")
            raise

    def parse_user_posts(self, data: Dict) -> Dict:
        """Reduce users posts' dataset to the most important fields"""
        log.debug(f"Parsing post data for {data.get('code', 'unknown')}")
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
            clips_metadata: clips_metadata,
            comments: comments
        }""",
            data,
        )
        
        # Add username if available
        if "user" in data:
            result["username"] = data["user"]["username"]
            
        return result

    async def scrape_user_posts(self, username: str, page_size=12, max_pages: Optional[int] = None) -> AsyncGenerator[Dict, None]:
        """Scrape all posts of an instagram user"""
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

        while True:
            try:
                params = {
                    "doc_id": self.INSTAGRAM_ACCOUNT_DOCUMENT_ID,
                    "variables": json.dumps(variables, separators=(",", ":"))
                }

                final_url = f"{base_url}?{urlencode(params)}"
                result = await self.client.async_scrape(ScrapeConfig(
                    final_url, 
                    **self.base_config, 
                    method="GET",
                    headers={"content-type": "application/x-www-form-urlencoded"},
                ))

                data = json.loads(result.content)
                
                posts = data["data"]["xdt_api__v1__feed__user_timeline_graphql_connection"]
                
                for post in posts["edges"]:
                    post_data = self.parse_user_posts(post["node"])
                    post_data["username"] = username
                    yield post_data

                page_info = posts["page_info"]
                log.info(f"Scraped posts page {page_number} for {username}")
                
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