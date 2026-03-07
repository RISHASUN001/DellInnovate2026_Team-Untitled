"""
Image Download Pipeline
=======================
Downloads images from scraped Instagram post data and saves them
into the image-service input folder using the required naming convention:

    <ig_handle>__<YYYYMMDD>__<index>.(jpg|png|webp)

Usage:
    python download_images.py --json results/all-user-posts.json --username chrishemsworth
    python download_images.py --json results/all-user-posts.json --username chrishemsworth --max-posts 10
    python download_images.py --json results/all-user-posts.json --username chrishemsworth --output custom/folder

The script will:
  1. Load post data from a scraped JSON file
  2. Create the output folder if it doesn't exist
  3. Pick the best-quality image candidate for each post
  4. Download and save with the correct filename convention
  5. Print a download summary
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("download_images")

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_OUTPUT_FOLDER = Path(__file__).parent / "image-service" / "data" / "post_images"
DEFAULT_JSON_PATH = Path(__file__).parent / "instagram-scraper" / "results" / "all-user-posts.json"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _unix_to_date_str(taken_at: int | None) -> str:
    """Convert a Unix timestamp to YYYYMMDD string.  Falls back to today."""
    if taken_at:
        try:
            dt = datetime.fromtimestamp(taken_at, tz=timezone.utc)
            return dt.strftime("%Y%m%d")
        except (OSError, OverflowError, ValueError):
            pass
    return datetime.now(tz=timezone.utc).strftime("%Y%m%d")


def _ext_from_url(url: str) -> str:
    """Guess image extension from URL path (defaults to .jpg)."""
    path = urlparse(url).path.lower()
    for ext in (".jpg", ".jpeg", ".png", ".webp"):
        if ext in path:
            return ext
    return ".jpg"


def _best_image_url(post: dict) -> Optional[str]:
    """Return the URL of the highest-resolution still image from a post.

    Strategy:
      • image_versions2.candidates — sorted by pixel area (desc); pick largest
      • Falls back to thumbnail_src / display_url if present (older API shape)
    """
    iv2 = post.get("image_versions2") or {}
    candidates = iv2.get("candidates") or []

    # Filter out non-image entries (some have weird sizes like 0×0)
    valid = [c for c in candidates if c.get("url") and c.get("width", 0) > 0]
    if valid:
        best = max(valid, key=lambda c: c.get("width", 0) * c.get("height", 0))
        return best["url"]

    # Fallback for older parsed shapes (from parse_post / parse_user)
    for key in ("src", "thumbnail_src", "display_url"):
        url = post.get(key)
        if url:
            return url

    return None


def _build_filename(username: str, date_str: str, index: int, url: str) -> str:
    """Produce  <username>__<YYYYMMDD>__<index>.<ext>"""
    ext = _ext_from_url(url)
    if ext == ".jpeg":
        ext = ".jpg"
    return f"{username}__{date_str}__{index}{ext}"


def download_image(url: str, dest: Path, retries: int = 3, backoff: float = 2.0) -> bool:
    """Download *url* to *dest*.  Returns True on success."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
        "Referer": "https://www.instagram.com/",
    }
    for attempt in range(1, retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                dest.write_bytes(resp.read())
            return True
        except urllib.error.HTTPError as exc:
            log.warning("  HTTP %s on attempt %d/%d: %s", exc.code, attempt, retries, dest.name)
            if exc.code in (403, 410):
                # CDN URL expired / forbidden — no point retrying
                break
        except Exception as exc:
            log.warning("  Error attempt %d/%d: %s", attempt, retries, exc)
        if attempt < retries:
            time.sleep(backoff * attempt)
    return False


# ---------------------------------------------------------------------------
# Core pipeline
# ---------------------------------------------------------------------------


def run_pipeline(
    json_path: Path,
    username: str,
    output_folder: Path,
    max_posts: int = 0,
    skip_existing: bool = True,
    delay: float = 0.5,
) -> None:
    """Main download pipeline.

    Args:
        json_path:      Path to the scraped posts JSON (list of post dicts).
        username:       Instagram handle — used as the filename prefix.
        output_folder:  Where to save images (created if needed).
        max_posts:      Cap on number of posts to process (0 = all).
        skip_existing:  Skip download if file already exists.
        delay:          Seconds to wait between downloads (be polite).
    """
    # ---- Load posts --------------------------------------------------------
    log.info("Loading posts from: %s", json_path)
    with open(json_path, encoding="utf-8") as fh:
        posts: list[dict] = json.load(fh)
    log.info("Loaded %d posts.", len(posts))

    if max_posts and max_posts > 0:
        posts = posts[:max_posts]
        log.info("Capped to %d posts (--max-posts).", max_posts)

    # ---- Prepare output folder ---------------------------------------------
    output_folder.mkdir(parents=True, exist_ok=True)
    log.info("Output folder: %s", output_folder.resolve())

    # ---- Download loop -----------------------------------------------------
    total = len(posts)
    downloaded = skipped = failed = 0

    for idx, post in enumerate(posts):
        url = _best_image_url(post)
        if not url:
            log.warning("[%d/%d] No image URL found — skipping post %s", idx + 1, total, post.get("shortcode"))
            failed += 1
            continue

        taken_at = post.get("taken_at")
        date_str = _unix_to_date_str(taken_at)

        # Use post index as the filename index (matches image-service convention)
        filename = _build_filename(username, date_str, idx, url)
        dest = output_folder / filename

        if skip_existing and dest.exists():
            log.info("[%d/%d] Already exists — skipping: %s", idx + 1, total, filename)
            skipped += 1
            continue

        log.info("[%d/%d] Downloading → %s", idx + 1, total, filename)
        success = download_image(url, dest)

        if success:
            size_kb = dest.stat().st_size // 1024
            log.info("  ✓ Saved (%d KB)", size_kb)
            downloaded += 1
        else:
            log.error("  ✗ Failed: %s", filename)
            failed += 1

        if delay > 0:
            time.sleep(delay)

    # ---- Summary -----------------------------------------------------------
    print("\n" + "=" * 50)
    print("DOWNLOAD PIPELINE SUMMARY")
    print("=" * 50)
    print(f"  Total posts processed : {total}")
    print(f"  Downloaded            : {downloaded}")
    print(f"  Skipped (exists)      : {skipped}")
    print(f"  Failed                : {failed}")
    print(f"  Output folder         : {output_folder.resolve()}")
    print(f"  Naming convention     : {username}__YYYYMMDD__<index>.jpg")
    print("=" * 50)

    if downloaded > 0:
        # Show first few filenames as examples
        files = sorted(output_folder.iterdir())[:5]
        print("\nExample files saved:")
        for f in files:
            print(f"  {f.name}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download Instagram post images from scraped JSON data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=DEFAULT_JSON_PATH,
        help="Path to scraped posts JSON file",
    )
    parser.add_argument(
        "--username",
        type=str,
        required=True,
        help="Instagram username (used as filename prefix)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT_FOLDER,
        help="Output folder for downloaded images",
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=0,
        help="Maximum number of posts to download (0 = all)",
    )
    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Re-download even if file already exists",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to wait between downloads",
    )

    args = parser.parse_args()

    if not args.json.exists():
        parser.error(f"JSON file not found: {args.json}")

    run_pipeline(
        json_path=args.json,
        username=args.username,
        output_folder=args.output,
        max_posts=args.max_posts,
        skip_existing=not args.no_skip,
        delay=args.delay,
    )


if __name__ == "__main__":
    main()