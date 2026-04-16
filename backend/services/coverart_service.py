import logging
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

BASE_URL = "https://coverartarchive.org"


def get_cover_art_url(release_mbid: str, size: int = 500) -> str:
    """Get the Cover Art Archive thumbnail URL for a release.

    Args:
        release_mbid: MusicBrainz release ID
        size: Thumbnail size (250, 500, or 1200)

    Returns:
        URL string for the cover art thumbnail.
    """
    return f"{BASE_URL}/release/{release_mbid}/front-{size}"


def get_cover_art_urls(release_mbid: str) -> dict:
    """Get all cover art image URLs for a release.

    Returns:
        Dict with keys: front, back, thumbnails (list of all images)
    """
    try:
        resp = requests.get(
            f"{BASE_URL}/release/{release_mbid}/",
            headers={"Accept": "application/json"},
            timeout=10,
        )
        if resp.status_code == 404:
            return {"front": None, "back": None, "thumbnails": []}

        resp.raise_for_status()
        data = resp.json()

        front = None
        back = None
        thumbnails = []

        for image in data.get("images", []):
            thumb = {
                "id": image.get("id"),
                "types": image.get("types", []),
                "small": image.get("thumbnails", {}).get("500", ""),
                "large": image.get("thumbnails", {}).get("1200", ""),
                "original": image.get("image", ""),
            }
            thumbnails.append(thumb)

            if image.get("front"):
                front = thumb["original"]
            if image.get("back"):
                back = thumb["original"]

        return {"front": front, "back": back, "thumbnails": thumbnails}

    except requests.RequestException as e:
        logger.warning("Failed to fetch cover art for %s: %s", release_mbid, e)
        return {"front": None, "back": None, "thumbnails": []}


def download_cover_art(release_mbid: str, output_path: str) -> bool:
    """Download the front cover art image to a local file.

    Args:
        release_mbid: MusicBrainz release ID
        output_path: Where to save the image

    Returns:
        True if download succeeded, False otherwise.
    """
    url = f"{BASE_URL}/release/{release_mbid}/front"
    try:
        resp = requests.get(url, timeout=30, allow_redirects=True)
        if resp.status_code == 404:
            logger.info("No cover art available for %s", release_mbid)
            return False

        resp.raise_for_status()

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(resp.content)

        logger.info("Downloaded cover art to %s", output_path)
        return True

    except requests.RequestException as e:
        logger.warning("Failed to download cover art for %s: %s", release_mbid, e)
        return False
