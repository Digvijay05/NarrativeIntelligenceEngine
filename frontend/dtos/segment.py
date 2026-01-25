"""
Timeline Segment DTO

Read-only segment of a narrative timeline.

PROHIBITED OPERATIONS:
======================
- Frontend MUST NOT merge segments
- Frontend MUST NOT interpolate time
- Frontend MUST NOT infer continuity
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
from datetime import datetime

from .core import (
    DTOVersion, ContinuityState, SilenceType, 
    AvailabilityState, OrderingBasis
)


@dataclass(frozen=True)
class TimeWindowDTO:
    """
    A time window with explicit bounds.
    
    NO INTERPOLATION:
    =================
    Bounds are exactly as provided by backend.
    """
    start: Optional[datetime]
    start_inclusive: bool
    
    end: Optional[datetime]
    end_inclusive: bool
    
    # Explicit markers
    is_point_in_time: bool  # Single moment, not range
    is_unbounded_start: bool
    is_unbounded_end: bool


@dataclass(frozen=True)
class SilenceIndicatorDTO:
    """
    Silence indicator from backend.
    
    EXPLICIT TYPING:
    ================
    Type is backend-provided, not inferred.
    """
    silence_type: SilenceType
    time_window: TimeWindowDTO
    expected: bool  # Was this silence expected?
    source_id: Optional[str]  # If silence is source-specific
    explicit: bool  # Backend explicitly marked this


@dataclass(frozen=True)
class TimelineSegmentDTO:
    """
    Timeline segment for frontend display.
    
    READ-ONLY CONTRACT:
    ===================
    - Immutable
    - No segment merging
    - No time interpolation
    - No continuity inference
    
    PROHIBITED:
    ===========
    - merged_from: List[str]
    - interpolated: bool
    - inferred_gap: bool
    - likely_continuous: bool
    - importance: float
    """
    # Version
    dto_version: DTOVersion
    
    # Identity
    segment_id: str
    thread_id: str  # Parent thread reference
    
    # Time window (exact, not interpolated)
    time_window: TimeWindowDTO
    
    # Continuity state (backend-defined only)
    continuity_to_previous: ContinuityState
    continuity_to_next: ContinuityState
    
    # Silence indicators (explicit)
    silence_indicators: Tuple[SilenceIndicatorDTO, ...]
    
    # Fragment references (IDs only, no payload joins)
    fragment_ids: Tuple[str, ...]
    
    # Ordering (backend-controlled)
    ordering_basis: OrderingBasis
    order_position: int
    
    # Availability
    availability: AvailabilityState
    fragment_count: int  # Count only, no aggregation
    
    # Metadata
    created_at: datetime
    
    def __post_init__(self):
        if self.dto_version != DTOVersion.current():
            raise ValueError(f"Unknown DTO version: {self.dto_version}")
