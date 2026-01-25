"""
Core DTO Types

Foundational enums and version types for all DTOs.

VERSIONING REQUIREMENT:
=======================
Every DTO includes a version field.
Frontend MUST fail fast on unknown versions.
"""

from __future__ import annotations
from enum import Enum
from dataclasses import dataclass
from typing import Final


# =============================================================================
# VERSION CONSTANTS
# =============================================================================

class DTOVersion(Enum):
    """
    DTO schema versions.
    
    Frontend MUST reject unknown versions.
    """
    V1 = "v1"
    
    @classmethod
    def current(cls) -> 'DTOVersion':
        return cls.V1


# Current version for type checking
CURRENT_DTO_VERSION: Final[DTOVersion] = DTOVersion.V1


# =============================================================================
# AVAILABILITY STATES (Explicit Absence)
# =============================================================================

class AvailabilityState(Enum):
    """
    Availability of a piece of data.
    
    EXPLICIT ABSENCE:
    =================
    Missing data MUST be flagged, never guessed.
    """
    PRESENT = "present"           # Data is available
    REDACTED = "redacted"         # Data exists but is hidden
    MISSING = "missing"           # Data expected but not found
    NEVER_EXISTED = "never_existed"  # Data was never expected
    UNKNOWN = "unknown"           # System cannot determine state
    
    # PROHIBITED: There is no "inferred" or "computed" state


# =============================================================================
# CONTINUITY STATES (Backend-Defined Only)
# =============================================================================

class ContinuityState(Enum):
    """
    Continuity between segments.
    
    BACKEND-DEFINED ONLY:
    =====================
    Frontend MUST NOT infer continuity from adjacency.
    """
    CONTINUOUS = "continuous"           # Explicit continuation
    EXPLICIT_GAP = "explicit_gap"       # Known discontinuity
    UNKNOWN_GAP = "unknown_gap"         # Possible gap, not confirmed
    PARALLEL = "parallel"               # Parallel timeline, not sequential
    
    # PROHIBITED: There is no "likely_continuous" or "probably_gap"


# =============================================================================
# LIFECYCLE STATES (Backend-Owned)
# =============================================================================

class LifecycleState(Enum):
    """
    Thread lifecycle state.
    
    BACKEND-OWNED:
    ==============
    Frontend displays this value, never computes it.
    """
    EMERGING = "emerging"       # Thread is forming
    ACTIVE = "active"           # Thread is currently active
    DORMANT = "dormant"         # Thread is inactive
    CONCLUDED = "concluded"     # Thread has ended
    MERGED = "merged"           # Thread merged into another
    UNKNOWN = "unknown"         # State cannot be determined
    
    # PROHIBITED: No "trending", "important", "main" etc.


# =============================================================================
# SILENCE TYPES (Explicit Markers)
# =============================================================================

class SilenceType(Enum):
    """
    Types of silence in a timeline.
    
    EXPLICIT MARKERS:
    =================
    Silence must be explicitly typed, not inferred.
    """
    EXPECTED = "expected"               # Normal gap (e.g., overnight)
    UNEXPECTED = "unexpected"           # Surprising silence
    PUBLICATION_GAP = "publication_gap" # Source stopped publishing
    REDACTION = "redaction"             # Content removed
    UNKNOWN = "unknown"                 # Cannot determine type
    
    # PROHIBITED: No "suspicious" or "noteworthy" silence


# =============================================================================
# DIVERGENCE FLAGS (Backend-Provided Only)
# =============================================================================

class DivergenceFlag(Enum):
    """
    Divergence markers from model layer.
    
    MODEL-PROVIDED ONLY:
    ====================
    These come from model overlays, never computed in frontend.
    """
    CONTRADICTION_DETECTED = "contradiction_detected"
    VERSION_CONFLICT = "version_conflict"
    SOURCE_DISAGREEMENT = "source_disagreement"
    TIMELINE_FORK = "timeline_fork"
    NONE = "none"
    
    # PROHIBITED: No computed divergence flags


# =============================================================================
# ORDERING HINT (Backend-Controlled)
# =============================================================================

class OrderingBasis(Enum):
    """
    Basis for item ordering.
    
    BACKEND-CONTROLLED:
    ===================
    Frontend displays in provided order.
    Reordering beyond this is PROHIBITED.
    """
    CHRONOLOGICAL = "chronological"       # Time-based
    REVERSE_CHRONOLOGICAL = "reverse_chronological"
    BACKEND_RANKED = "backend_ranked"     # Backend-determined ranking
    INSERTION_ORDER = "insertion_order"   # Order of ingestion
    UNORDERED = "unordered"               # No meaningful order
    
    # PROHIBITED: No "importance", "relevance", "trending" ordering
