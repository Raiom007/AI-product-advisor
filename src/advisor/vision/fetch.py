"""Image fetching for vision verification (§5.5)."""
import httpx
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path("data/cache/vision_images")
MAX_SIZE_BYTES = 5 * 1024 * 1024  # 5MB
TIMEOUT_SEC = 5.0

def fetch_image(url: str) -> bytes | None:
    """Fetch an image with timeout, size cap, and content-type check.
    
    Cache by URL hash.
    Returns bytes if valid, None if broken/HTML/oversize.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    url_hash = hashlib.sha256(url.encode()).hexdigest()
    cache_path = CACHE_DIR / f"{url_hash}.bin"
    
    if cache_path.exists():
        return cache_path.read_bytes()
        
    try:
        with httpx.Client(timeout=TIMEOUT_SEC) as client:
            # We use stream to check headers before downloading
            with client.stream("GET", url) as response:
                response.raise_for_status()
                
                content_type = response.headers.get("content-type", "")
                if not content_type.startswith("image/"):
                    logger.warning(f"Skipping {url}: Not an image ({content_type})")
                    return None
                    
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_SIZE_BYTES:
                    logger.warning(f"Skipping {url}: Oversize ({content_length} bytes)")
                    return None
                    
                # Read chunks to enforce size limit dynamically if content-length is missing
                content = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    content.extend(chunk)
                    if len(content) > MAX_SIZE_BYTES:
                        logger.warning(f"Skipping {url}: Oversize (dynamic)")
                        return None
                        
                final_bytes = bytes(content)
                cache_path.write_bytes(final_bytes)
                return final_bytes
                
    except Exception as e:
        logger.warning(f"Skipping {url}: Fetch failed ({e})")
        return None
