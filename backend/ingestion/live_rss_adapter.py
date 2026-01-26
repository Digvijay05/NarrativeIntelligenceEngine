"""
Live RSS Ingestion Adapter
===========================

Real-world RSS ingestion adapter for shadow mode.

SIBLING to mock adapters, NOT a replacement.

GUARANTEES:
===========
1. Raw XML bytes stored VERBATIM before any parsing
2. Full provenance: source_id, fetch_time, content_hash, raw_path
3. RawIngestionEvent schema identical to mock adapter
4. SourceTier.PUBLIC_RSS for all events

DOES NOT:
=========
- Interpret content
- Rank importance
- Analyze sentiment
- Adjudicate truth
- Smooth or predict
"""

from __future__ import annotations
from typing import Iterator, Optional, Dict, List, Any
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass
import hashlib
import json

from ..contracts.base import SourceId, Timestamp, Error, ErrorCode, Result, SourceTier
from ..contracts.events import RawIngestionEvent
from .import IngestionAdapter


@dataclass(frozen=True)
class FetchProvenance:
    """Immutable provenance record for a fetch operation."""
    source_id: str
    fetch_timestamp: datetime
    content_hash: str
    raw_payload_path: str
    payload_size_bytes: int
    http_status: Optional[int] = None
    fetch_duration_ms: Optional[float] = None


class LiveRSSAdapter(IngestionAdapter):
    """
    Real-world RSS ingestion adapter.
    
    SIBLING to mock adapter, not a replacement.
    
    CRITICAL ORDERING:
    ==================
    1. HTTP fetch raw bytes
    2. Store verbatim (BEFORE parsing)
    3. Parse XML
    4. Yield events
    
    This ordering guarantees raw bytes are preserved even if parsing fails.
    """
    
    def __init__(
        self,
        config: Dict[str, Any],
        storage_dir: Path,
        logical_clock: Any = None  # Optional: for deterministic replay
    ):
        """
        Initialize with configuration and storage.
        
        Args:
            config: Feed configuration (same schema as live_feeds.json)
            storage_dir: Directory for raw payload storage
            logical_clock: Optional clock for deterministic time
        """
        self._config = config
        self._storage_dir = Path(storage_dir)
        self._clock = logical_clock
        
        # Ensure raw storage directory exists
        self._raw_dir = self._storage_dir / "raw"
        self._raw_dir.mkdir(parents=True, exist_ok=True)
        
        # Build source URL mapping from config
        self._source_urls: Dict[str, str] = {}
        self._source_names: Dict[str, str] = {}
        self._load_sources_from_config()
    
    def _load_sources_from_config(self) -> None:
        """Load source URLs from configuration."""
        feeds = self._config.get('feeds', {})
        for category_name, category_data in feeds.items():
            for source in category_data.get('sources', []):
                if source.get('enabled', True):
                    source_id = source['id']
                    self._source_urls[source_id] = source['url']
                    self._source_names[source_id] = source.get('name', source_id)
    
    @property
    def source_type(self) -> str:
        return "live_rss"
    
    @property
    def source_tier(self) -> SourceTier:
        """All events from this adapter are PUBLIC_RSS tier."""
        return SourceTier.PUBLIC_RSS
    
    def validate_source(self, source_id: SourceId) -> Result:
        """Validate that source_id exists in configuration."""
        if source_id.value not in self._source_urls:
            return Result.failure(Error(
                code=ErrorCode.INVALID_SOURCE_ID,
                message=f"Source {source_id.value} not found in configuration",
                timestamp=self._get_time()
            ))
        return Result.success(True)
    
    def pull_events(
        self,
        source_id: SourceId,
        since: Optional[Timestamp] = None
    ) -> Iterator[RawIngestionEvent]:
        """
        Fetch live RSS and yield events.
        
        ORDERING (critical for forensic integrity):
        1. HTTP fetch raw bytes
        2. Store verbatim BEFORE parsing
        3. Parse XML
        4. Yield events with full provenance
        """
        # Validate source
        if source_id.value not in self._source_urls:
            return
        
        url = self._source_urls[source_id.value]
        fetch_time = self._get_time()
        
        # 1. HTTP Fetch raw bytes
        raw_bytes, http_status, fetch_duration = self._fetch_raw(url)
        
        if raw_bytes is None:
            # Network failure - this IS a signal (absence/silence)
            # We don't emit events, but the absence is detectable
            return
        
        # 2. Store verbatim BEFORE parsing
        raw_path = self._store_raw_payload(source_id.value, raw_bytes, fetch_time)
        content_hash = hashlib.sha256(raw_bytes).hexdigest()
        
        # Record provenance
        provenance = FetchProvenance(
            source_id=source_id.value,
            fetch_timestamp=fetch_time,
            content_hash=content_hash,
            raw_payload_path=str(raw_path),
            payload_size_bytes=len(raw_bytes),
            http_status=http_status,
            fetch_duration_ms=fetch_duration
        )
        
        # 3. Parse XML
        items = self._parse_rss(raw_bytes)
        
        # 4. Yield events with full provenance
        for item in items:
            # Construct payload matching mock adapter schema
            payload = {
                'title': item.get('title', ''),
                'link': item.get('link', ''),
                'description': item.get('description', ''),
                'published_at': item.get('published_at'),
                'author': item.get('author'),
                'guid': item.get('guid'),
                'categories': item.get('categories', []),
                # Provenance linkage
                '_provenance': {
                    'content_hash': content_hash,
                    'fetch_timestamp': fetch_time.isoformat(),
                    'raw_path': str(raw_path)
                }
            }
            
            raw_payload = json.dumps(payload, ensure_ascii=False)
            
            # Parse published timestamp if available
            event_timestamp = None
            if item.get('published_at'):
                try:
                    event_timestamp = Timestamp.from_iso(item['published_at'])
                except (ValueError, TypeError):
                    pass  # Leave as None
            
            yield RawIngestionEvent.create(
                source_id=source_id,
                raw_payload=raw_payload,
                source_confidence=1.0,  # Public RSS assumed reliable
                event_timestamp=event_timestamp,
                source_tier=SourceTier.PUBLIC_RSS,
                raw_payload_path=str(raw_path)
            )
    
    def _get_time(self) -> datetime:
        """Get current time (uses logical clock if available)."""
        if self._clock is not None and hasattr(self._clock, 'now'):
            return self._clock.now()
        return datetime.now(timezone.utc)
    
    def _fetch_raw(self, url: str) -> tuple:
        """
        Fetch raw bytes from URL.
        
        Returns:
            (raw_bytes, http_status, duration_ms) or (None, None, None) on failure
        """
        import urllib.request
        import ssl
        import time
        
        start = time.time()
        
        try:
            # Create SSL context that doesn't verify (some RSS feeds have bad certs)
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            request = urllib.request.Request(
                url,
                headers={'User-Agent': 'NarrativeIntelligence/1.0'}
            )
            
            with urllib.request.urlopen(request, timeout=30, context=ctx) as response:
                raw_bytes = response.read()
                http_status = response.status
                duration = (time.time() - start) * 1000
                return raw_bytes, http_status, duration
                
        except Exception:
            # Network failure - return None to indicate absence
            return None, None, None
    
    def _store_raw_payload(
        self,
        source_id: str,
        raw_bytes: bytes,
        fetch_time: datetime
    ) -> Path:
        """
        Store raw payload verbatim.
        
        Returns path to stored file.
        """
        timestamp_str = fetch_time.strftime('%Y%m%d%H%M%S')
        filename = f"{source_id}_{timestamp_str}.xml"
        raw_path = self._raw_dir / filename
        
        with open(raw_path, 'wb') as f:
            f.write(raw_bytes)
        
        return raw_path
    
    def _parse_rss(self, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Parse RSS XML to item dictionaries.
        
        Very lenient parsing - captures what's available.
        """
        try:
            import feedparser
            feed = feedparser.parse(raw_bytes)
            
            items = []
            for entry in feed.entries:
                item = {
                    'title': getattr(entry, 'title', ''),
                    'link': getattr(entry, 'link', ''),
                    'description': getattr(entry, 'description', getattr(entry, 'summary', '')),
                    'guid': getattr(entry, 'id', getattr(entry, 'link', '')),
                    'author': getattr(entry, 'author', None),
                    'categories': [t.term for t in getattr(entry, 'tags', []) if hasattr(t, 'term')],
                }
                
                # Handle published date
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    from time import mktime
                    dt = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                    item['published_at'] = dt.isoformat()
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    from time import mktime
                    dt = datetime.fromtimestamp(mktime(entry.updated_parsed), tz=timezone.utc)
                    item['published_at'] = dt.isoformat()
                else:
                    item['published_at'] = None
                
                items.append(item)
            
            return items
            
        except Exception:
            # Parse failure - return empty list
            # The raw bytes are already stored, so no data is lost
            return []
    
    def get_all_source_ids(self) -> List[SourceId]:
        """Get all configured source IDs."""
        return [
            SourceId(value=sid, source_type="live_rss")
            for sid in self._source_urls.keys()
        ]
