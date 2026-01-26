"""
State Access Layer

Responsibility:
Read-only access to Backend Narrative State.
These contracts mirror the backend's immutable state but are optimized for frontend consumption.

PRINCIPLES:
1. Immutable (Frozen)
2. No Business Logic
3. No Rendering Logic
"""

from .core import (
    DTOVersion, AvailabilityState, ContinuityState, LifecycleState,
    SilenceType, DivergenceFlag, OrderingBasis
)
from .thread import (
    NarrativeThreadDTO, TemporalBoundsDTO, PresenceMarkerDTO, OverlayRefDTO
)
from .segment import (
    TimelineSegmentDTO, TimeWindowDTO, SilenceIndicatorDTO
)
from .fragment import (
    EvidenceFragmentDTO, TimestampDTO
)
from .overlay import (
    ModelOverlayRefDTO, ScoreRefDTO, AnnotationRefDTO
)
from .envelope import (
    ThreadListEnvelope, SegmentListEnvelope, FragmentListEnvelope,
    QueryMetadataDTO, PaginationDTO
)

__all__ = [
    'DTOVersion', 'AvailabilityState', 'ContinuityState', 'LifecycleState',
    'SilenceType', 'DivergenceFlag', 'OrderingBasis',
    'NarrativeThreadDTO', 'TemporalBoundsDTO', 'PresenceMarkerDTO', 'OverlayRefDTO',
    'TimelineSegmentDTO', 'TimeWindowDTO', 'SilenceIndicatorDTO',
    'EvidenceFragmentDTO', 'TimestampDTO',
    'ModelOverlayRefDTO', 'ScoreRefDTO', 'AnnotationRefDTO',
    'ThreadListEnvelope', 'SegmentListEnvelope', 'FragmentListEnvelope',
    'QueryMetadataDTO', 'PaginationDTO'
]
