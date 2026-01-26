"""
Response Envelope

Wrapper for all API responses to frontend.

ENVELOPE CONTRACT:
==================
- Always versioned
- Always timestamped
- Includes explicit availability
- No implicit defaults
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional, TypeVar, Generic
from datetime import datetime

from .core import DTOVersion, AvailabilityState, OrderingBasis


T = TypeVar('T')


@dataclass(frozen=True)
class PaginationDTO:
    """
    Pagination state from backend.
    
    BACKEND-CONTROLLED:
    ===================
    Frontend cannot compute pagination.
    """
    total_count: Optional[int]  # None if unknown
    returned_count: int
    offset: int
    has_more: bool
    next_cursor: Optional[str]
    prev_cursor: Optional[str]


@dataclass(frozen=True)
class QueryMetadataDTO:
    """
    Metadata about the query that produced this response.
    
    TRANSPARENCY:
    =============
    Frontend knows exactly what was queried.
    """
    query_id: str
    requested_at: datetime
    responded_at: datetime
    processing_time_ms: float
    
    # What was requested
    requested_version: DTOVersion
    
    # What was returned
    actual_version: DTOVersion


@dataclass(frozen=True)
class ResponseEnvelope(Generic[T]):
    """
    Envelope for all frontend responses.
    
    UNIVERSAL CONTRACT:
    ===================
    Every response is wrapped in this envelope.
    Frontend can rely on this structure.
    
    PROHIBITED BEHAVIOR:
    ====================
    - Frontend cannot unwrap and re-process
    - Frontend cannot merge multiple envelopes
    - Frontend cannot cache and compare
    """
    # Version
    dto_version: DTOVersion
    
    # Response identity
    response_id: str
    
    # Query metadata
    query: QueryMetadataDTO
    
    # Payload
    data: T
    
    # Availability
    data_availability: AvailabilityState
    
    # Ordering (if applicable)
    ordering_basis: Optional[OrderingBasis]
    
    # Pagination (if applicable)
    pagination: Optional[PaginationDTO]
    
    # Warnings (explicit issues)
    warnings: Tuple[str, ...]
    
    # Freshness (backend-defined)
    data_as_of: datetime
    is_stale: bool  # Backend decides staleness
    
    def __post_init__(self):
        if self.dto_version != DTOVersion.current():
            raise ValueError(f"Unknown DTO version: {self.dto_version}")


# =============================================================================
# SPECIFIC ENVELOPE TYPES
# =============================================================================

@dataclass(frozen=True)
class ThreadListEnvelope:
    """Envelope for thread list responses."""
    dto_version: DTOVersion
    response_id: str
    query: QueryMetadataDTO
    threads: Tuple  # Tuple[NarrativeThreadDTO, ...]
    ordering_basis: OrderingBasis
    pagination: Optional[PaginationDTO]
    data_availability: AvailabilityState
    data_as_of: datetime
    is_stale: bool
    warnings: Tuple[str, ...]
    
    def __post_init__(self):
        if self.dto_version != DTOVersion.current():
            raise ValueError(f"Unknown DTO version: {self.dto_version}")


@dataclass(frozen=True)
class SegmentListEnvelope:
    """Envelope for segment list responses."""
    dto_version: DTOVersion
    response_id: str
    query: QueryMetadataDTO
    segments: Tuple  # Tuple[TimelineSegmentDTO, ...]
    thread_id: str
    ordering_basis: OrderingBasis
    pagination: Optional[PaginationDTO]
    data_availability: AvailabilityState
    data_as_of: datetime
    is_stale: bool
    warnings: Tuple[str, ...]
    
    def __post_init__(self):
        if self.dto_version != DTOVersion.current():
            raise ValueError(f"Unknown DTO version: {self.dto_version}")


@dataclass(frozen=True)
class FragmentListEnvelope:
    """Envelope for fragment list responses."""
    dto_version: DTOVersion
    response_id: str
    query: QueryMetadataDTO
    fragments: Tuple  # Tuple[EvidenceFragmentDTO, ...]
    segment_id: Optional[str]
    thread_id: Optional[str]
    ordering_basis: OrderingBasis
    pagination: Optional[PaginationDTO]
    data_availability: AvailabilityState
    data_as_of: datetime
    is_stale: bool
    warnings: Tuple[str, ...]
    
    def __post_init__(self):
        if self.dto_version != DTOVersion.current():
            raise ValueError(f"Unknown DTO version: {self.dto_version}")
