# Place your images here — filenames must follow the convention:
#
#   <ig_handle>__<YYYYMMDD>__<index>.(jpg|jpeg|png|webp)
#
# Examples:
#   johndoe__20240101__0.jpg
#   brand_co__20231215__3.png
#
# Sub-folders are allowed; the service scans recursively.


# To test:
# 1. Set the key
export SCRAPFLY_KEY="your_key"

# 2. Scrape fresh data
cd instagram-scraper && python3 run.py

# 3. Immediately download images
cd .. && python3 download_images.py --username chrishemsworth --max-posts 5

# 4. Check images landed
ls image-service/data/post_images/