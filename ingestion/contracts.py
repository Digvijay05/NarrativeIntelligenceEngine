"""
RSS Ingestion Contracts

Immutable data structures for RSS ingestion pipeline.

BOUNDARY: Backend Ingestion Layer
All RSS data enters through these contracts.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Optional, FrozenSet
from datetime import datetime
from enum import Enum
import hashlib


# =============================================================================
# ENUMS
# =============================================================================

class FeedCategory(Enum):
    """Categories of RSS feeds."""
    NATIONAL_NEWS = "national_news"
    GOVERNMENT_POLICY = "government_policy"
    BUSINESS_ECONOMY = "business_economy"
    REGIONAL = "regional"
    INVESTIGATIVE = "investigative_factcheck"
    GLOBAL_CONTEXT = "global_context"
    SPECIALIZED = "specialized_longform"


class FeedTier(Enum):
    """Polling priority tiers."""
    TIER_1 = 1  # Critical - poll frequently
    TIER_2 = 2  # Important - standard polling
    TIER_3 = 3  # Background - infrequent polling


class FetchStatus(Enum):
    """Status of a fetch attempt."""
    SUCCESS = "success"
    TIMEOUT = "timeout"
    HTTP_ERROR = "http_error"
    PARSE_ERROR = "parse_error"
    NETWORK_ERROR = "network_error"
    PAYWALL_BLOCKED = "paywall_blocked"
    FEED_DISABLED = "feed_disabled"


class ContentType(Enum):
    """Type of raw content."""
    RSS_XML = "rss_xml"
    ATOM_XML = "atom_xml"
    ARTICLE_HTML = "article_html"
    ARTICLE_TEXT = "article_text"


# =============================================================================
# FEED CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class FeedSource:
    """Configuration for a single RSS feed."""
    source_id: str
    name: str
    url: str
    category: FeedCategory
    tier: FeedTier
    language: str
    region: str
    enabled: bool
    source_type: str = "news"
    notes: Optional[str] = None
    
    def __hash__(self):
        return hash(self.source_id)


@dataclass(frozen=True)
class PollConfig:
    """Polling configuration for a feed category."""
    category: FeedCategory
    interval_minutes: int
    retry_after_minutes: int
    max_retries: int = 3


# =============================================================================
# RAW PAYLOAD CONTRACTS (never deleted)
# =============================================================================

@dataclass(frozen=True)
class RawRSSPayload:
    """
    Raw RSS/Atom XML exactly as received.
    
    NEVER DELETED - this is the source of truth.
    """
    payload_id: str
    source_id: str
    fetched_at: datetime
    url: str
    http_status: int
    content_type: ContentType
    raw_bytes: bytes
    content_hash: str
    headers: Tuple[Tuple[str, str], ...]
    
    @classmethod
    def create(
        cls,
        source_id: str,
        url: str,
        http_status: int,
        raw_bytes: bytes,
        headers: dict,
        fetched_at: Optional[datetime] = None
    ) -> 'RawRSSPayload':
        """Create from raw response."""
        fetched = fetched_at or datetime.utcnow()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        payload_id = f"rss_{source_id}_{fetched.strftime('%Y%m%d%H%M%S')}_{content_hash[:8]}"
        
        # Detect content type
        content_type_header = headers.get('content-type', '').lower()
        if 'atom' in content_type_header:
            ct = ContentType.ATOM_XML
        else:
            ct = ContentType.RSS_XML
        
        return cls(
            payload_id=payload_id,
            source_id=source_id,
            fetched_at=fetched,
            url=url,
            http_status=http_status,
            content_type=ct,
            raw_bytes=raw_bytes,
            content_hash=content_hash,
            headers=tuple((k, v) for k, v in headers.items())
        )


@dataclass(frozen=True)
class RawArticlePayload:
    """
    Raw article HTML exactly as fetched.
    
    NEVER DELETED - enables re-extraction with improved algorithms.
    """
    payload_id: str
    article_url: str
    source_id: str
    rss_payload_id: str  # Links back to the RSS that contained this
    fetched_at: datetime
    http_status: int
    raw_bytes: bytes
    content_hash: str
    headers: Tuple[Tuple[str, str], ...]
    
    @classmethod
    def create(
        cls,
        article_url: str,
        source_id: str,
        rss_payload_id: str,
        http_status: int,
        raw_bytes: bytes,
        headers: dict,
        fetched_at: Optional[datetime] = None
    ) -> 'RawArticlePayload':
        """Create from raw response."""
        fetched = fetched_at or datetime.utcnow()
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        payload_id = f"article_{content_hash[:16]}"
        
        return cls(
            payload_id=payload_id,
            article_url=article_url,
            source_id=source_id,
            rss_payload_id=rss_payload_id,
            fetched_at=fetched,
            http_status=http_status,
            raw_bytes=raw_bytes,
            content_hash=content_hash,
            headers=tuple((k, v) for k, v in headers.items())
        )


# =============================================================================
# PARSED ITEM CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class RSSItem:
    """
    Parsed RSS item (not yet a fragment).
    
    Represents a single entry from an RSS feed.
    """
    item_id: str
    source_id: str
    rss_payload_id: str
    
    # Core fields
    title: str
    link: str
    description: str
    
    # Temporal
    published_at: Optional[datetime]  # From feed
    fetched_at: datetime  # When we got it
    
    # Metadata
    author: Optional[str] = None
    categories: Tuple[str, ...] = field(default_factory=tuple)
    guid: Optional[str] = None
    
    def content_hash(self) -> str:
        """Compute content hash for deduplication."""
        content = f"{self.link}|{self.title}|{self.description}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass(frozen=True)
class ExtractedArticle:
    """
    Extracted and cleaned article content.
    
    Ready for normalization into fragments.
    """
    article_id: str
    source_id: str
    rss_item_id: str
    article_payload_id: str
    
    # URLs
    url: str
    canonical_url: Optional[str]
    
    # Content
    title: str
    clean_text: str
    
    # Temporal
    published_at: Optional[datetime]  # From article metadata
    rss_published_at: Optional[datetime]  # From RSS
    fetched_at: datetime
    extracted_at: datetime
    
    # Metadata
    author: Optional[str] = None
    section: Optional[str] = None
    tags: Tuple[str, ...] = field(default_factory=tuple)
    word_count: int = 0
    language: str = "en"
    
    # Extraction info
    extraction_method: str = "default"
    extraction_confidence: float = 1.0


# =============================================================================
# FETCH RESULT CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class FetchResult:
    """
    Result of a fetch attempt (success or failure).
    
    Failed fetches are FIRST-CLASS outputs, not exceptions.
    """
    result_id: str
    source_id: str
    url: str
    attempted_at: datetime
    completed_at: datetime
    status: FetchStatus
    
    # On success
    payload_id: Optional[str] = None
    items_count: int = 0
    
    # On failure
    error_message: Optional[str] = None
    http_status: Optional[int] = None
    retry_after: Optional[datetime] = None
    
    @property
    def success(self) -> bool:
        return self.status == FetchStatus.SUCCESS
    
    @property
    def duration_ms(self) -> float:
        return (self.completed_at - self.attempted_at).total_seconds() * 1000


@dataclass(frozen=True)
class FetchBatch:
    """Batch of fetch results from a poll cycle."""
    batch_id: str
    started_at: datetime
    completed_at: datetime
    results: Tuple[FetchResult, ...]
    
    @property
    def success_count(self) -> int:
        return sum(1 for r in self.results if r.success)
    
    @property
    def failure_count(self) -> int:
        return sum(1 for r in self.results if not r.success)


# =============================================================================
# DEDUPLICATION CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class ContentFingerprint:
    """Fingerprint for deduplication."""
    fingerprint_id: str
    content_hash: str
    url_hash: str
    title_hash: str
    first_seen_at: datetime
    source_ids: FrozenSet[str]  # All sources that published this


@dataclass(frozen=True)
class DuplicateDetection:
    """Result of duplicate detection."""
    item_id: str
    is_duplicate: bool
    duplicate_of: Optional[str]  # Original item ID
    similarity_score: float
    detection_method: str
