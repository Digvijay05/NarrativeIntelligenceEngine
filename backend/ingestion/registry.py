"""
Source Registry
===============

IMMUTABLE registry of allowed RSS sources.
Constitutional Constraint: No dynamic discovery.
"""

from dataclasses import dataclass
from typing import Tuple

@dataclass(frozen=True)
class RegisteredSource:
    source_id: str
    url: str
    tier: str  # "primary", "secondary"
    poll_interval_seconds: int

# HARDCODED SOURCE LIST (The "Finite Set")
_REGISTRY = (
    RegisteredSource(
        source_id="src_et_top",
        url="https://economictimes.indiatimes.com/rssfeedstopstories.cms",
        tier="primary",
        poll_interval_seconds=300
    ),
    RegisteredSource(
        source_id="src_toi_top",
        url="https://timesofindia.indiatimes.com/rssfeedstopstories.cms",
        tier="primary",
        poll_interval_seconds=300
    ),
    RegisteredSource(
        source_id="src_hindu_nat",
        url="https://www.thehindu.com/news/national/feeder/default.rss",
        tier="secondary",
        poll_interval_seconds=600
    ),
)

def get_all_sources() -> Tuple[RegisteredSource, ...]:
    """Return all registered sources."""
    return _REGISTRY

def get_source_by_id(source_id: str) -> RegisteredSource:
    """Lookup source by ID or raise error."""
    for src in _REGISTRY:
        if src.source_id == source_id:
            return src
    raise ValueError(f"Unknown source_id: {source_id}")
