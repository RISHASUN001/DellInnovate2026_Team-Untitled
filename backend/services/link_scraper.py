"""
Service for scraping bio links and extracting metadata
"""
import asyncio
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urlparse, urljoin
import httpx
from bs4 import BeautifulSoup
from loguru import logger

class LinkScraperService:
    # Common social media domains to skip
    SOCIAL_MEDIA_DOMAINS = {
        'twitter.com', 'x.com', 'facebook.com', 'fb.com', 'instagram.com',
        'linkedin.com', 'tiktok.com', 'youtube.com', 'youtu.be', 'snapchat.com',
        'pinterest.com', 'reddit.com', 'discord.com', 'telegram.org', 't.me',
        'whatsapp.com', 'twitch.tv', 'vimeo.com', 'tumblr.com', 'flickr.com',
        'spotify.com', 'soundcloud.com', 'apple.com/music', 'music.apple.com'
    }
    
    # Regex patterns for social media links
    SOCIAL_MEDIA_PATTERNS = {
        'twitter': [r'twitter\.com/([^/]+)', r'x\.com/([^/]+)'],
        'facebook': [r'facebook\.com/([^/]+)', r'fb\.com/([^/]+)'],
        'linkedin': [r'linkedin\.com/in/([^/]+)', r'linkedin\.com/company/([^/]+)'],
        'tiktok': [r'tiktok\.com/@([^/]+)'],
        'youtube': [r'youtube\.com/(@[^/]+|c/[^/]+|channel/[^/]+|user/[^/]+)', r'youtu\.be/([^/]+)'],
        'snapchat': [r'snapchat\.com/add/([^/]+)'],
        'pinterest': [r'pinterest\.com/([^/]+)'],
        'reddit': [r'reddit\.com/u(?:ser)?/([^/]+)'],
        'twitch': [r'twitch\.tv/([^/]+)'],
        'spotify': [r'open\.spotify\.com/artist/([^/]+)'],
        'soundcloud': [r'soundcloud\.com/([^/]+)'],
    }
    
    def __init__(self, timeout: int = 10, max_redirects: int = 5):
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }
    
    def is_social_media_link(self, url: str) -> bool:
        """Check if a URL is a social media link"""
        try:
            domain = urlparse(url).netloc.lower()
            # Remove www. prefix
            domain = domain.replace('www.', '')
            
            # Check if domain matches any social media domain
            for social_domain in self.SOCIAL_MEDIA_DOMAINS:
                if domain == social_domain or domain.endswith('.' + social_domain):
                    return True
            return False
        except Exception:
            return False
    
    def extract_social_media_info(self, url: str) -> Optional[Dict[str, str]]:
        """Extract social media platform and username from URL"""
        try:
            url_lower = url.lower()
            
            for platform, patterns in self.SOCIAL_MEDIA_PATTERNS.items():
                for pattern in patterns:
                    match = re.search(pattern, url_lower)
                    if match:
                        username = match.group(1)
                        return {
                            'platform': platform,
                            'profile_url': url,
                            'profile_username': username
                        }
            
            # If no specific pattern matched but it's a social media link
            if self.is_social_media_link(url):
                domain = urlparse(url).netloc.lower().replace('www.', '')
                for platform_domain in ['twitter.com', 'x.com', 'facebook.com', 'linkedin.com', 
                                       'tiktok.com', 'youtube.com', 'snapchat.com']:
                    if platform_domain in domain:
                        platform_name = platform_domain.split('.')[0]
                        if platform_name == 'x':
                            platform_name = 'twitter'
                        return {
                            'platform': platform_name,
                            'profile_url': url,
                            'profile_username': None
                        }
            
            return None
        except Exception as e:
            logger.error(f"Error extracting social media info from {url}: {e}")
            return None
    
    async def scrape_link_metadata(self, url: str) -> Dict:
        """Scrape metadata from a single URL"""
        result = {
            'url': url,
            'scraped_url': None,
            'title': None,
            'description': None,
            'image': None,
            'site_name': None,
            'status_code': None,
            'content_type': None,
            'error': None
        }
        
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout,
                follow_redirects=True,
                max_redirects=self.max_redirects,
                headers=self.headers
            ) as client:
                response = await client.get(url)
                result['status_code'] = response.status_code
                result['scraped_url'] = str(response.url)
                result['content_type'] = response.headers.get('content-type', '')
                
                if response.status_code != 200:
                    result['error'] = f"HTTP {response.status_code}"
                    return result
                
                # Only parse HTML content
                if 'text/html' not in result['content_type'].lower():
                    result['error'] = f"Non-HTML content: {result['content_type']}"
                    return result
                
                # Parse HTML
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Extract Open Graph metadata (preferred)
                og_title = soup.find('meta', property='og:title')
                og_description = soup.find('meta', property='og:description')
                og_image = soup.find('meta', property='og:image')
                og_site_name = soup.find('meta', property='og:site_name')
                
                # Extract Twitter Card metadata as fallback
                twitter_title = soup.find('meta', attrs={'name': 'twitter:title'})
                twitter_description = soup.find('meta', attrs={'name': 'twitter:description'})
                twitter_image = soup.find('meta', attrs={'name': 'twitter:image'})
                
                # Extract standard HTML metadata
                html_title = soup.find('title')
                html_description = soup.find('meta', attrs={'name': 'description'})
                
                # Prioritize Open Graph, then Twitter Card, then standard HTML
                result['title'] = (
                    og_title.get('content') if og_title else
                    twitter_title.get('content') if twitter_title else
                    html_title.string if html_title else
                    None
                )
                
                result['description'] = (
                    og_description.get('content') if og_description else
                    twitter_description.get('content') if twitter_description else
                    html_description.get('content') if html_description else
                    None
                )
                
                result['image'] = (
                    og_image.get('content') if og_image else
                    twitter_image.get('content') if twitter_image else
                    None
                )
                
                # Make image URL absolute if it's relative
                if result['image'] and not result['image'].startswith(('http://', 'https://')):
                    result['image'] = urljoin(str(response.url), result['image'])
                
                result['site_name'] = og_site_name.get('content') if og_site_name else None
                
                logger.info(f"Successfully scraped metadata from {url}")
                
        except httpx.TimeoutException:
            result['error'] = "Request timeout"
            logger.warning(f"Timeout scraping {url}")
        except httpx.HTTPError as e:
            result['error'] = f"HTTP error: {str(e)}"
            logger.error(f"HTTP error scraping {url}: {e}")
        except Exception as e:
            result['error'] = str(e)
            logger.error(f"Error scraping {url}: {e}")
        
        return result
    
    async def scrape_multiple_links(self, urls: List[str], filter_social_media: bool = True) -> Dict[str, List[Dict]]:
        """Scrape multiple links and separate social media from other links"""
        results = {
            'scraped_links': [],
            'social_media_links': [],
            'failed_links': []
        }
        
        for url in urls:
            try:
                # Check if it's a social media link
                social_info = self.extract_social_media_info(url)
                
                if social_info:
                    results['social_media_links'].append(social_info)
                    logger.info(f"Identified social media link: {url} ({social_info['platform']})")
                elif not filter_social_media or not self.is_social_media_link(url):
                    # Only scrape non-social media links
                    metadata = await self.scrape_link_metadata(url)
                    if metadata['error']:
                        results['failed_links'].append(metadata)
                    else:
                        results['scraped_links'].append(metadata)
                
            except Exception as e:
                logger.error(f"Error processing link {url}: {e}")
                results['failed_links'].append({
                    'url': url,
                    'error': str(e)
                })
        
        logger.info(f"Scraped {len(results['scraped_links'])} links, "
                   f"found {len(results['social_media_links'])} social media links, "
                   f"{len(results['failed_links'])} failed")
        
        return results
    
    async def scrape_bio_links_from_user_data(self, user_data: Dict) -> Dict[str, List[Dict]]:
        """Extract and scrape bio links from user data"""
        bio_links = user_data.get('bio_links', [])
        
        if not bio_links:
            logger.info(f"No bio links found for user {user_data.get('username')}")
            return {
                'scraped_links': [],
                'social_media_links': [],
                'failed_links': []
            }
        
        logger.info(f"Found {len(bio_links)} bio links for user {user_data.get('username')}")
        return await self.scrape_multiple_links(bio_links)
