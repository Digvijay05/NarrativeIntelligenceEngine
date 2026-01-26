"""
RSS Normalizer
==============

Converts raw RSS items to EvidenceFragments with explicit logging.

GUARANTEES:
- Every item is either normalized, dropped, or marked malformed
- Duplicates are detected and logged
- No semantic processing (no summaries, no sentiment)
- All decisions are traceable
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Set, Optional, Tuple
from pathlib import Path
import hashlib
import json
from html.parser import HTMLParser

from backend.contracts.evidence import EvidenceFragment, MissingDataReason


@dataclass(frozen=True)
class DroppedItem:
    """Record of an item that was dropped during normalization."""
    item_id: str
    source_id: str
    reason: str
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            'item_id': self.item_id,
            'source_id': self.source_id,
            'reason': self.reason,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass(frozen=True)
class DuplicateItem:
    """Record of a duplicate item detected."""
    item_id: str
    source_id: str
    existing_fragment_id: str
    content_hash: str
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            'item_id': self.item_id,
            'source_id': self.source_id,
            'existing_fragment_id': self.existing_fragment_id,
            'content_hash': self.content_hash,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass(frozen=True)
class MalformedItem:
    """Record of a malformed item."""
    item_id: str
    source_id: str
    error: str
    raw_content_sample: str  # First 200 chars for debugging
    timestamp: datetime
    
    def to_dict(self) -> dict:
        return {
            'item_id': self.item_id,
            'source_id': self.source_id,
            'error': self.error,
            'raw_content_sample': self.raw_content_sample,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class NormalizationReport:
    """
    Complete report of normalization phase.
    
    TRACEABLE:
    Every input item results in exactly one of:
    - A fragment in `fragments`
    - An entry in `dropped_items`
    - An entry in `duplicate_items`
    - An entry in `malformed_items`
    """
    processed_count: int = 0
    fragments: List[EvidenceFragment] = field(default_factory=list)
    dropped_items: List[DroppedItem] = field(default_factory=list)
    duplicate_items: List[DuplicateItem] = field(default_factory=list)
    malformed_items: List[MalformedItem] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    @property
    def success_count(self) -> int:
        return len(self.fragments)
    
    @property
    def dropped_count(self) -> int:
        return len(self.dropped_items)
    
    @property
    def duplicate_count(self) -> int:
        return len(self.duplicate_items)
    
    @property
    def malformed_count(self) -> int:
        return len(self.malformed_items)
    
    def to_dict(self) -> dict:
        return {
            'processed_count': self.processed_count,
            'success_count': self.success_count,
            'dropped_count': self.dropped_count,
            'duplicate_count': self.duplicate_count,
            'malformed_count': self.malformed_count,
            'fragments': [f.to_dict() for f in self.fragments],
            'dropped_items': [d.to_dict() for d in self.dropped_items],
            'duplicate_items': [d.to_dict() for d in self.duplicate_items],
            'malformed_items': [m.to_dict() for m in self.malformed_items],
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None
        }


class RSSNormalizer:
    """
    Normalizes RSS items to EvidenceFragments.
    
    NO SEMANTIC PROCESSING:
    - Does not summarize
    - Does not analyze sentiment
    - Does not rank
    - Does not infer
    
    EXPLICIT LOGGING:
    - Every decision is recorded
    - Every drop has a reason
    - Every duplicate is tracked
    """
    
    def __init__(self, raw_storage_path: Path):
        self._raw_storage_path = Path(raw_storage_path)
        self._seen_hashes: Dict[str, str] = {}  # hash -> fragment_id
        self._seen_links: Set[str] = set()
    
    def normalize_batch(
        self,
        items: List[dict],
        ingest_timestamp: datetime
    ) -> NormalizationReport:
        """
        Normalize a batch of RSS items.
        
        Args:
            items: List of RSS item dictionaries
            ingest_timestamp: When these items were fetched
            
        Returns:
            NormalizationReport with all fragments and issues
        """
        report = NormalizationReport(
            processed_count=len(items),
            started_at=ingest_timestamp
        )
        
        for item in items:
            try:
                result = self._normalize_item(item, ingest_timestamp)
                
                if isinstance(result, EvidenceFragment):
                    report.fragments.append(result)
                elif isinstance(result, DroppedItem):
                    report.dropped_items.append(result)
                elif isinstance(result, DuplicateItem):
                    report.duplicate_items.append(result)
                elif isinstance(result, MalformedItem):
                    report.malformed_items.append(result)
                    
            except Exception as e:
                # Catch-all for unexpected errors
                item_id = item.get('item_id', item.get('link', 'unknown'))
                source_id = item.get('source_id', 'unknown')
                raw_sample = str(item)[:200]
                
                report.malformed_items.append(MalformedItem(
                    item_id=item_id,
                    source_id=source_id,
                    error=f"Unexpected error: {str(e)}",
                    raw_content_sample=raw_sample,
                    timestamp=ingest_timestamp
                ))
        
        report.completed_at = ingest_timestamp
        return report
    
    def _normalize_item(
        self,
        item: dict,
        ingest_timestamp: datetime
    ) -> EvidenceFragment | DroppedItem | DuplicateItem | MalformedItem:
        """
        Normalize a single RSS item.
        
        Returns one of:
        - EvidenceFragment if successful
        - DroppedItem if missing required fields
        - DuplicateItem if already seen
        - MalformedItem if parsing failed
        """
        item_id = item.get('item_id', '')
        source_id = item.get('source_id', 'unknown')
        
        # Check required fields
        title = item.get('title', '').strip()
        link = item.get('link', '').strip()
        
        if not title:
            return DroppedItem(
                item_id=item_id,
                source_id=source_id,
                reason="Missing required field: title",
                timestamp=ingest_timestamp
            )
        
        if not link:
            return DroppedItem(
                item_id=item_id,
                source_id=source_id,
                reason="Missing required field: link",
                timestamp=ingest_timestamp
            )
        
        # Check for duplicate by link
        if link in self._seen_links:
            # Find the existing fragment
            existing_id = self._find_fragment_by_link(link)
            return DuplicateItem(
                item_id=item_id,
                source_id=source_id,
                existing_fragment_id=existing_id or "unknown",
                content_hash=hashlib.sha256(link.encode()).hexdigest()[:16],
                timestamp=ingest_timestamp
            )
        
        # Get description
        description = item.get('description', '') or ''
        
        # Compute content hash for deduplication
        content_for_hash = f"{title}|{link}|{description}"
        content_hash = hashlib.sha256(content_for_hash.encode()).hexdigest()
        
        # Check for duplicate by content hash
        if content_hash in self._seen_hashes:
            return DuplicateItem(
                item_id=item_id,
                source_id=source_id,
                existing_fragment_id=self._seen_hashes[content_hash],
                content_hash=content_hash[:16],
                timestamp=ingest_timestamp
            )
        
        # Parse event timestamp (published_at)
        event_timestamp = None
        published_at = item.get('published_at')
        if published_at:
            if isinstance(published_at, datetime):
                event_timestamp = published_at
            elif isinstance(published_at, str):
                try:
                    event_timestamp = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                except ValueError:
                    pass  # Will be None, which is explicit
        
        # Get raw payload path
        raw_payload_path = item.get('raw_payload_path', '')
        payload_hash = item.get('payload_hash', content_hash[:32])
        
        # Get optional fields
        author = item.get('author')
        categories = tuple(item.get('categories', []))
        guid = item.get('guid')
        
        # Extract hyperlinks from description (and content if available)
        # Note: 'content' is sometimes under 'content:encoded' or just 'content' depending on feed
        hyperlinks = self._extract_hyperlinks(description)
        # TODO: checking for 'content' or 'content_encoded' in item would be good if available in item dict

        
        # Create fragment
        fragment = EvidenceFragment.create(
            source_id=source_id,
            title=title,
            link=link,
            description=description,
            raw_payload_path=raw_payload_path,
            payload_hash=payload_hash,
            ingest_timestamp=ingest_timestamp,
            event_timestamp=event_timestamp,
            author=author,
            hyperlinks=hyperlinks,
            categories=categories,
            guid=guid
        )
        
        # Track for deduplication
        self._seen_hashes[content_hash] = fragment.fragment_id
        self._seen_links.add(link)
        
        return fragment
    
    def _find_fragment_by_link(self, link: str) -> Optional[str]:
        """Find fragment ID by link."""
        # Simple implementation - in production would use index
        for hash_val, frag_id in self._seen_hashes.items():
            if link in hash_val:
                return frag_id
        return None
    
    def reset(self) -> None:
        """Reset deduplication state."""
        self._seen_hashes.clear()
        self._seen_links.clear()
    
    def get_stats(self) -> dict:
        """Get normalizer statistics."""
        return {
            'unique_hashes': len(self._seen_hashes),
            'unique_links': len(self._seen_links)
        }

    def _extract_hyperlinks(self, html_content: str) -> Tuple[str, ...]:
        """Extract all hrefs from HTML content using standard library."""
        if not html_content:
            return ()
        
        links = []
        
        class LinkExtractor(HTMLParser):
            def handle_starttag(self, tag, attrs):
                if tag == 'a':
                    for name, value in attrs:
                        if name == 'href' and value:
                            links.append(value)
                            
        try:
            parser = LinkExtractor()
            parser.feed(html_content)
        except Exception:
            # RSS content can be messy; fail safe
            pass
            
        return tuple(links)
