"""
Frontend DTO Package

Read-only, immutable Data Transfer Objects for frontend consumption.

EPISTEMIC BOUNDARY ENFORCEMENT:
================================
1. All DTOs are frozen (immutable)
2. All DTOs are versioned
3. Frontend receives ONLY these types, never internal entities
4. Missing data is EXPLICIT, never inferred
"""

from .core import (
    DTOVersion,
    AvailabilityState,
    ContinuityState,
    LifecycleState,
    SilenceType,
    DivergenceFlag,
    OrderingBasis,
)

from .thread import NarrativeThreadDTO, TemporalBoundsDTO, PresenceMarkerDTO, OverlayRefDTO
from .segment import TimelineSegmentDTO, TimeWindowDTO, SilenceIndicatorDTO
from .fragment import EvidenceFragmentDTO, TimestampDTO
from .overlay import ModelOverlayRefDTO, ScoreRefDTO, AnnotationRefDTO
from .envelope import ResponseEnvelope, QueryMetadataDTO, PaginationDTO

__all__ = [
    # Enums
    'DTOVersion',
    'AvailabilityState',
    'ContinuityState',
    'LifecycleState',
    'SilenceType',
    'DivergenceFlag',
    'OrderingBasis',
    # Thread
    'NarrativeThreadDTO',
    'TemporalBoundsDTO',
    'PresenceMarkerDTO',
    'OverlayRefDTO',
    # Segment
    'TimelineSegmentDTO',
    'TimeWindowDTO',
    'SilenceIndicatorDTO',
    # Fragment
    'EvidenceFragmentDTO',
    'TimestampDTO',
    # Overlay
    'ModelOverlayRefDTO',
    'ScoreRefDTO',
    'AnnotationRefDTO',
    # Envelope
    'ResponseEnvelope',
    'QueryMetadataDTO',
    'PaginationDTO',
]
