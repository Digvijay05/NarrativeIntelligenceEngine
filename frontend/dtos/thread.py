"""
Narrative Thread DTO

Read-only representation of a narrative thread for frontend display.

PROHIBITED FIELDS:
==================
- importance / weight / ranking
- computed_* anything
- main_thread / primary flag
- derived_* anything
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional, FrozenSet
from datetime import datetime

from .core import (
    DTOVersion, LifecycleState, DivergenceFlag, 
    AvailabilityState, OrderingBasis
)


@dataclass(frozen=True)
class TemporalBoundsDTO:
    """
    Time bounds of a thread.
    
    EXPLICIT UNKNOWNS:
    ==================
    Each bound can be known or explicitly unknown.
    """
    start_timestamp: Optional[datetime]
    start_known: bool  # True if start is confirmed, False if estimated
    
    end_timestamp: Optional[datetime]
    end_known: bool  # True if end is confirmed, False if ongoing/estimated
    
    # Explicit marker for unbounded
    is_unbounded: bool


@dataclass(frozen=True)
class PresenceMarkerDTO:
    """
    Explicit presence/absence marker.
    
    NO INFERENCE:
    =============
    Frontend displays these markers, never derives them.
    """
    marker_type: str  # "expected", "present", "absent", "silent"
    time_window_start: Optional[datetime]
    time_window_end: Optional[datetime]
    source_id: Optional[str]
    explicit: bool  # True if backend explicitly set this, not inferred


@dataclass(frozen=True)
class OverlayRefDTO:
    """
    Reference to a model overlay.
    
    REFERENCE ONLY:
    ===============
    Contains IDs and metadata, not the actual overlay content.
    """
    overlay_id: str
    overlay_type: str
    model_version: str
    created_at: datetime
    availability: AvailabilityState


@dataclass(frozen=True)
class NarrativeThreadDTO:
    """
    Narrative thread for frontend display.
    
    READ-ONLY CONTRACT:
    ===================
    - All fields are immutable
    - No computed fields
    - No importance/ranking
    - Display exactly as provided
    
    PROHIBITED:
    ===========
    - importance: float
    - weight: float
    - is_main: bool
    - computed_status: str
    - derived_summary: str
    - topic_relevance: float
    """
    # Version (required for contract)
    dto_version: DTOVersion
    
    # Identity (opaque to frontend)
    thread_id: str
    thread_version: str
    
    # Backend-defined state (display only)
    lifecycle_state: LifecycleState
    
    # Temporal bounds (explicit)
    temporal_bounds: TemporalBoundsDTO
    
    # Presence markers (explicit, not inferred)
    presence_markers: Tuple[PresenceMarkerDTO, ...]
    
    # Divergence flags (model-provided)
    divergence_flags: Tuple[DivergenceFlag, ...]
    
    # Model overlay references (IDs only)
    overlay_refs: Tuple[OverlayRefDTO, ...]
    
    # Topic references (IDs only, no payload)
    topic_ids: Tuple[str, ...]
    
    # Segment references (IDs only)
    segment_ids: Tuple[str, ...]
    
    # Display metadata (backend-controlled)
    display_label: Optional[str]  # Backend-provided label only
    ordering_basis: OrderingBasis
    order_position: int  # Position in backend-provided ordering
    
    # Availability
    availability: AvailabilityState
    
    # Timestamps
    first_seen_at: datetime
    last_updated_at: datetime
    
    def __post_init__(self):
        """Validate DTO version."""
        if self.dto_version != DTOVersion.current():
            raise ValueError(
                f"Unknown DTO version: {self.dto_version}. "
                f"Expected: {DTOVersion.current()}"
            )
