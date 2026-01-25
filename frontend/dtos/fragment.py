"""
Evidence Fragment DTO

Read-only representation of a fragment for frontend display.

PROHIBITED:
===========
- Semantic interpretation
- Payload content (only hash + availability)
- Computed relevance
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
from datetime import datetime

from .core import DTOVersion, AvailabilityState


@dataclass(frozen=True)
class TimestampDTO:
    """
    Timestamp with explicit precision.
    
    EXPLICIT PRECISION:
    ===================
    Precision is backend-defined, not assumed.
    """
    timestamp: datetime
    precision: str  # "second", "minute", "hour", "day", "approximate"
    is_approximate: bool
    source: str  # "published", "fetched", "inferred_by_backend"


@dataclass(frozen=True)
class EvidenceFragmentDTO:
    """
    Evidence fragment for frontend display.
    
    READ-ONLY CONTRACT:
    ===================
    - Fragment ID only (opaque)
    - Source ID only (opaque)
    - Payload hash (not content)
    - Availability state (explicit)
    
    PROHIBITED:
    ===========
    - content: str (semantic content)
    - summary: str (computed summary)
    - relevance: float (computed score)
    - importance: float
    - keywords: List[str] (extracted)
    - sentiment: str (computed)
    - topics: List[str] (derived)
    """
    # Version
    dto_version: DTOVersion
    
    # Identity (opaque to frontend)
    fragment_id: str
    source_id: str
    
    # Timestamps (explicit, not interpreted)
    published_at: Optional[TimestampDTO]
    fetched_at: TimestampDTO
    
    # Content reference (hash only, no content)
    payload_hash: str
    
    # Availability (explicit)
    availability: AvailabilityState
    
    # Size (for display purposes only)
    byte_size: Optional[int]
    word_count: Optional[int]  # Backend-computed, not frontend
    
    # Display hint (backend-controlled)
    display_label: Optional[str]
    
    # Parent references
    segment_id: Optional[str]
    thread_id: Optional[str]
    
    # Ordering
    order_position: int
    
    def __post_init__(self):
        if self.dto_version != DTOVersion.current():
            raise ValueError(f"Unknown DTO version: {self.dto_version}")
