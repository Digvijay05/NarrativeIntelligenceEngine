import httpx

def fetch_rss_bytes(feed_url: str) -> bytes:
    """
    Fetch RSS feed as raw bytes.
    No parsing. No decoding assumptions.
    """
    with httpx.Client(timeout=15.0, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}, follow_redirects=True) as client:
        resp = client.get(feed_url)
        resp.raise_for_status()
        return resp.content
