"""
Evidence Fragment Contract
==========================

Normalized evidence from RSS with NO semantic processing.

CONSTRAINTS:
- No summaries
- No sentiment
- No ranking  
- No inference
- Missing data is EXPLICIT (never None without reason)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Tuple
from enum import Enum
import hashlib


class MissingDataReason(Enum):
    """Explicit reasons for missing data."""
    NOT_PROVIDED = "not_provided"        # Source didn't include it
    PARSE_FAILED = "parse_failed"        # Couldn't extract from source
    INVALID_FORMAT = "invalid_format"    # Present but malformed
    REDACTED = "redacted"                # Intentionally removed


@dataclass(frozen=True)
class MissingField:
    """Explicit representation of missing data."""
    reason: MissingDataReason
    details: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'missing': True,
            'reason': self.reason.value,
            'details': self.details
        }


@dataclass(frozen=True)
class EvidenceFragment:
    """
    Normalized evidence from RSS.
    
    NO SEMANTIC PROCESSING:
    =======================
    - No summaries computed
    - No sentiment analyzed
    - No ranking applied
    - No truth adjudication
    - No inference made
    
    SURFACE DATA ONLY:
    ==================
    - Title as-is from source
    - Link as-is
    - Description hash (not content - too large)
    - Timestamps with explicit semantics
    """
    # Identity
    fragment_id: str
    source_id: str
    
    # Temporal (explicit semantics)
    event_timestamp: Optional[datetime]      # When it happened (published_at from RSS)
    ingest_timestamp: datetime               # When we fetched it
    
    # Integrity
    payload_hash: str                        # SHA-256 of raw payload
    raw_payload_path: str                    # Reference to stored raw bytes
    
    # Surface content (no interpretation)
    title: str
    link: str
    description_hash: str                    # SHA-256 of description, not content
    
    # Optional fields with explicit missing handling
    author: Optional[str] = None
    author_missing_reason: Optional[MissingDataReason] = None
    
    categories: Tuple[str, ...] = field(default_factory=tuple)
    
    guid: Optional[str] = None
    
    hyperlinks: Tuple[str, ...] = field(default_factory=tuple)
    
    # Normalization metadata
    normalized_at: Optional[datetime] = None
    normalization_version: str = "1.0"
    
    @classmethod
    def create(
        cls,
        source_id: str,
        title: str,
        link: str,
        description: str,
        raw_payload_path: str,
        payload_hash: str,
        ingest_timestamp: datetime,
        event_timestamp: Optional[datetime] = None,
        author: Optional[str] = None,
        hyperlinks: Tuple[str, ...] = (),
        categories: Tuple[str, ...] = (),
        guid: Optional[str] = None
    ) -> 'EvidenceFragment':
        """
        Create fragment with deterministic ID generation.
        
        ID is derived from content hash for deduplication.
        """
        # Generate deterministic fragment ID
        id_seed = f"{source_id}:{link}:{payload_hash}"
        fragment_id = f"frag_{hashlib.sha256(id_seed.encode()).hexdigest()[:16]}"
        
        # Hash description
        desc_hash = hashlib.sha256(description.encode()).hexdigest()
        
        # Determine missing reason for author
        author_missing = None
        if author is None:
            author_missing = MissingDataReason.NOT_PROVIDED
        
        return cls(
            fragment_id=fragment_id,
            source_id=source_id,
            event_timestamp=event_timestamp,
            ingest_timestamp=ingest_timestamp,
            payload_hash=payload_hash,
            raw_payload_path=raw_payload_path,
            title=title,
            link=link,
            description_hash=desc_hash,
            author=author,
            author_missing_reason=author_missing,
            hyperlinks=hyperlinks,
            categories=categories,
            guid=guid,
            normalized_at=ingest_timestamp,
        )
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            'fragment_id': self.fragment_id,
            'source_id': self.source_id,
            'event_timestamp': self.event_timestamp.isoformat() if self.event_timestamp else None,
            'ingest_timestamp': self.ingest_timestamp.isoformat(),
            'payload_hash': self.payload_hash,
            'raw_payload_path': self.raw_payload_path,
            'title': self.title,
            'link': self.link,
            'description_hash': self.description_hash,
            'author': self.author,
            'author_missing_reason': self.author_missing_reason.value if self.author_missing_reason else None,
            'hyperlinks': list(self.hyperlinks),
            'categories': list(self.categories),
            'guid': self.guid,
            'normalized_at': self.normalized_at.isoformat() if self.normalized_at else None,
            'normalization_version': self.normalization_version
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EvidenceFragment':
        """Reconstruct from dictionary."""
        return cls(
            fragment_id=data['fragment_id'],
            source_id=data['source_id'],
            event_timestamp=datetime.fromisoformat(data['event_timestamp']) if data.get('event_timestamp') else None,
            ingest_timestamp=datetime.fromisoformat(data['ingest_timestamp']),
            payload_hash=data['payload_hash'],
            raw_payload_path=data['raw_payload_path'],
            title=data['title'],
            link=data['link'],
            description_hash=data['description_hash'],
            author=data.get('author'),
            author_missing_reason=MissingDataReason(data['author_missing_reason']) if data.get('author_missing_reason') else None,
            hyperlinks=tuple(data.get('hyperlinks', [])),
            categories=tuple(data.get('categories', [])),
            guid=data.get('guid'),
            normalized_at=datetime.fromisoformat(data['normalized_at']) if data.get('normalized_at') else None,
            normalization_version=data.get('normalization_version', '1.0')
        )
