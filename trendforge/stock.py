"""Stock-provider routing and Pixabay's normalized, cached video search."""

import hashlib
import json
import os
import tempfile
import time
from urllib.parse import urlparse

import httpx

from .errors import AppError
from .integrations import pexels_search


def validate_stock_url(url, provider):
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    approved = (host == "cdn.pixabay.com" if provider == "pixabay" else
                provider == "pexels" and host.endswith(".pexels.com"))
    if (parsed.scheme != "https" or not approved or parsed.username or parsed.password
            or parsed.port not in (None, 443)):
        raise AppError("The stock file is not hosted on an approved media domain.")
    return url


async def search_stock(settings, query):
    query = query.strip()
    if not 2 <= len(query) <= 100:
        raise AppError("Enter a search between 2 and 100 characters.")
    provider = settings.get("stock_provider", "pixabay")
    if provider == "pexels":
        return [{**item, "provider": "pexels"} for item in await pexels_search(settings, query)]
    if provider != "pixabay":
        raise AppError("Choose pixabay or pexels as the stock footage provider.")
    return await pixabay_search(settings, query)


async def pixabay_search(settings, query):
    key = settings.get("pixabay_api_key")
    if not key:
        raise AppError("Pixabay stock footage needs setup. Set PIXABAY_API_KEY in .env and restart TrendForge. You can still upload your own clips.",
                       "PIXABAY_NOT_CONFIGURED", 409)
    # Cache across restarts for 24 hours, including empty results, per Pixabay's API rules.
    # Hash the key into the cache identity so changing credentials never reuses old access.
    identity = hashlib.sha256(json.dumps([key, query.casefold(), 1]).encode()).hexdigest()
    cache_dir = settings.directory / "cache" / "stock" / "pixabay"
    cache_path = cache_dir / f"{identity}.json"
    try:
        cached = json.loads(cache_path.read_text(encoding="utf-8"))
        if 0 <= time.time() - cached["fetched_at"] < 86400 and isinstance(cached["items"], list):
            return cached["items"]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get("https://pixabay.com/api/videos/", params={
                "key": key, "q": query, "per_page": 20, "safesearch": "true",
            })
        if response.status_code == 429:
            raise AppError("Pixabay's request limit has been reached. Wait a minute and try again.", "PIXABAY_QUOTA", 429)
        if response.status_code >= 400:
            raise AppError("Pixabay could not complete this search. Check your API key and quota.", "PIXABAY_ERROR", 502)
        result = []
        for video in response.json()["hits"]:
            if not 3 <= video.get("duration", 0) <= 120:
                continue
            variants = [v for v in video.get("videos", {}).values() if
                        360 <= min(v.get("width", 0), v.get("height", 0)) and
                        max(v.get("width", 0), v.get("height", 0)) <= 1920 and
                        0 < v.get("size", 0) <= 100 * 1024 * 1024 and v.get("url")]
            if not variants:
                continue
            chosen = max(variants, key=lambda v: v["width"] * v["height"])
            validate_stock_url(chosen["url"], "pixabay")
            result.append({"id": video["id"], "provider": "pixabay", "url": video["pageURL"],
                           "image": chosen.get("thumbnail", ""), "duration": video["duration"],
                           "creator": video.get("user") or "Pixabay contributor",
                           "creator_url": f"https://pixabay.com/users/id-{int(video['user_id'])}/",
                           "file_url": chosen["url"], "width": chosen["width"], "height": chosen["height"]})
        # Prefer portrait footage, while allowing landscape clips the editor can fit.
        result.sort(key=lambda v: v["height"] >= v["width"], reverse=True)
        result = result[:5]
    except httpx.HTTPError:
        raise AppError("Pixabay could not be reached. Your uploaded clips are still available.", "PIXABAY_UNAVAILABLE", 503)
    except (ValueError, KeyError, TypeError, AttributeError):
        raise AppError("Pixabay returned an incomplete response. Try another search.", "PIXABAY_INVALID_RESPONSE", 502)
    cache_dir.mkdir(parents=True, exist_ok=True)
    # Atomic replacement prevents interrupted/concurrent searches from corrupting the cache.
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=cache_dir, delete=False) as stream:
            name = stream.name
            json.dump({"fetched_at": time.time(), "items": result}, stream)
        os.replace(name, cache_path)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return result
