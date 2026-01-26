from dataclasses import dataclass
from typing import List

@dataclass(frozen=True)
class ShadowRSSSource:
    source_id: str
    feed_url: str
    poll_interval_seconds: int

# Minimal, conservative starter set (switched to more permissive feeds)
SHADOW_RSS_SOURCES: List[ShadowRSSSource] = [
    ShadowRSSSource(
        source_id="bbc_world",
        feed_url="http://feeds.bbci.co.uk/news/world/rss.xml",
        poll_interval_seconds=300,
    ),
    ShadowRSSSource(
        source_id="hacker_news",
        feed_url="https://news.ycombinator.com/rss",
        poll_interval_seconds=300,
    ),
]
