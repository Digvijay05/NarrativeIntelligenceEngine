"""
Base Contracts and Shared Types

These are the foundational types used across all layers.
All types here are IMMUTABLE and represent pure data.
No behavior, no side effects, no dependencies.

BOUNDARY ENFORCEMENT:
=====================
- This module is READ-ONLY from all layers
- Layers may import types but MUST NOT modify this module
- All types are frozen dataclasses for immutability guarantee
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import FrozenSet, Optional, Tuple
from enum import Enum, auto
import hashlib


# =============================================================================
# ERROR STATES (Explicit, never silent)
# =============================================================================

class ErrorCode(Enum):
    """
    Explicit error codes for deterministic error handling.
    No silent fallbacks - every error state is enumerated.
    """
    # Ingestion errors
    INVALID_SOURCE_ID = auto()
    INVALID_TIMESTAMP = auto()
    EMPTY_PAYLOAD = auto()
    MALFORMED_PAYLOAD = auto()
    SOURCE_UNREACHABLE = auto()
    
    # Normalization errors
    CANONICALIZATION_FAILED = auto()
    DUPLICATE_DETECTION_AMBIGUOUS = auto()
    ENTITY_RESOLUTION_FAILED = auto()
    
    # Core engine errors
    THREAD_NOT_FOUND = auto()
    INVALID_STATE_TRANSITION = auto()
    TEMPORAL_AMBIGUITY = auto()
    STRUCTURAL_INCONSISTENCY = auto()
    INSUFFICIENT_DATA = auto()
    
    # Storage errors
    VERSION_CONFLICT = auto()
    SNAPSHOT_NOT_FOUND = auto()
    TIMELINE_CORRUPTION = auto()
    
    # Query errors
    INVALID_TIME_RANGE = auto()
    QUERY_TIMEOUT = auto()
    RESULT_SET_TOO_LARGE = auto()


@dataclass(frozen=True)
class Error:
    """
    Immutable error representation with full context.
    Errors are data, not exceptions - they can be stored and queried.
    """
    code: ErrorCode
    message: str
    timestamp: datetime
    context: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    
    def with_context(self, key: str, value: str) -> Error:
        """Return new Error with additional context (immutable)."""
        return Error(
            code=self.code,
            message=self.message,
            timestamp=self.timestamp,
            context=self.context + ((key, value),)
        )


@dataclass(frozen=True)
class Result:
    """
    Generic result type for operations that can fail.
    Either contains a value OR an error, never both.
    """
    value: Optional[object] = None
    error: Optional[Error] = None
    
    @property
    def is_success(self) -> bool:
        return self.error is None
    
    @property
    def is_failure(self) -> bool:
        return self.error is not None
    
    @staticmethod
    def success(value: object) -> Result:
        return Result(value=value, error=None)
    
    @staticmethod
    def failure(error: Error) -> Result:
        return Result(value=None, error=error)


# =============================================================================
# IDENTITY TYPES (Immutable, hash-verified)
# =============================================================================

@dataclass(frozen=True)
class SourceId:
    """Immutable source identifier with type classification."""
    value: str
    source_type: str
    
    def __post_init__(self):
        if not self.value or not isinstance(self.value, str):
            raise ValueError("SourceId value must be a non-empty string")
        if not self.source_type or not isinstance(self.source_type, str):
            raise ValueError("source_type must be a non-empty string")


@dataclass(frozen=True) 
class FragmentId:
    """
    Immutable fragment identifier.
    Generated from content hash to ensure deterministic identity.
    """
    value: str
    content_hash: str
    
    @staticmethod
    def generate(source_id: str, timestamp: datetime, payload: str) -> FragmentId:
        """Generate deterministic fragment ID from content."""
        content = f"{source_id}|{timestamp.isoformat()}|{payload}"
        content_hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
        fragment_id = f"frag_{content_hash[:16]}"
        return FragmentId(value=fragment_id, content_hash=content_hash)


@dataclass(frozen=True)
class ThreadId:
    """Immutable thread identifier."""
    value: str
    
    @staticmethod
    def generate(seed: str) -> ThreadId:
        """Generate deterministic thread ID from seed."""
        thread_hash = hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]
        return ThreadId(value=f"thread_{thread_hash}")


@dataclass(frozen=True)
class VersionId:
    """Immutable version identifier for temporal snapshots."""
    value: str
    sequence: int
    parent_version: Optional[str] = None
    
    @staticmethod
    def generate(entity_id: str, sequence: int, parent: Optional[str] = None) -> VersionId:
        """Generate deterministic version ID."""
        version_seed = f"{entity_id}|{sequence}|{parent or 'root'}"
        version_hash = hashlib.sha256(version_seed.encode('utf-8')).hexdigest()[:12]
        return VersionId(
            value=f"v_{version_hash}",
            sequence=sequence,
            parent_version=parent
        )


# =============================================================================
# TEMPORAL TYPES (Immutable, explicit semantics)
# =============================================================================

@dataclass(frozen=True)
class Timestamp:
    """
    Immutable timestamp with explicit semantics.
    All timestamps are UTC, never local time.
    """
    value: datetime
    
    def __post_init__(self):
        # Ensure UTC timezone
        if self.value.tzinfo is None:
            object.__setattr__(self, 'value', self.value.replace(tzinfo=timezone.utc))
    
    @staticmethod
    def now() -> Timestamp:
        return Timestamp(value=datetime.now(timezone.utc))
    
    @staticmethod
    def from_iso(iso_string: str) -> Timestamp:
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return Timestamp(value=dt)
    
    def to_iso(self) -> str:
        return self.value.isoformat()


@dataclass(frozen=True)
class TimeRange:
    """Immutable time range for queries."""
    start: Timestamp
    end: Timestamp
    
    def __post_init__(self):
        if self.start.value > self.end.value:
            raise ValueError("TimeRange start must be before or equal to end")
    
    def contains(self, timestamp: Timestamp) -> bool:
        return self.start.value <= timestamp.value <= self.end.value


# =============================================================================
# METADATA TYPES (Immutable, explicit)
# =============================================================================

@dataclass(frozen=True)
class SourceMetadata:
    """
    Immutable source metadata captured at ingestion time.
    This metadata is NEVER modified after capture.
    """
    source_id: SourceId
    source_confidence: float  # 0.0 to 1.0, subjective source reliability
    capture_timestamp: Timestamp  # When we captured it
    event_timestamp: Optional[Timestamp]  # When the event occurred (if known)
    raw_metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    
    def __post_init__(self):
        if not 0.0 <= self.source_confidence <= 1.0:
            raise ValueError("source_confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class ContentSignature:
    """
    Immutable content signature for integrity verification.
    Used for deduplication and audit trails.
    """
    payload_hash: str
    payload_length: int
    detected_language: Optional[str] = None
    
    @staticmethod
    def compute(payload: str, language: Optional[str] = None) -> ContentSignature:
        """Compute signature from payload content."""
        return ContentSignature(
            payload_hash=hashlib.sha256(payload.encode('utf-8')).hexdigest(),
            payload_length=len(payload),
            detected_language=language
        )


# =============================================================================
# LIFECYCLE STATES (Explicit, no implicit transitions)
# =============================================================================

class ThreadLifecycleState(Enum):
    """
    Explicit thread lifecycle states.
    Transitions are deterministic and auditable.
    """
    EMERGING = "emerging"        # Initial state, accumulating fragments
    ACTIVE = "active"            # Ongoing, receiving regular updates
    DORMANT = "dormant"          # No recent activity, but not terminated
    TERMINATED = "terminated"    # Explicitly ended, no further updates expected
    DIVERGED = "diverged"        # Split into multiple incompatible paths


class FragmentRelationType(Enum):
    """
    Explicit fragment relationship types.
    No implicit relationships - all must be explicitly tagged.
    """
    CONTINUATION = "continuation"    # Continues same narrative
    CONTRADICTION = "contradiction"  # Contradicts existing fragment
    PARALLEL = "parallel"            # Related but independent
    REFERENCE = "reference"          # References another fragment
    UNRELATED = "unrelated"          # No detected relationship


@dataclass(frozen=True)
class FragmentRelation:
    """Immutable relationship between two fragments."""
    source_fragment_id: FragmentId
    target_fragment_id: FragmentId
    relation_type: FragmentRelationType
    confidence: float  # 0.0 to 1.0
    detected_at: Timestamp
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


# =============================================================================
# TOPIC AND ENTITY TYPES (Immutable)
# =============================================================================

@dataclass(frozen=True)
class CanonicalTopic:
    """Immutable canonical topic representation."""
    topic_id: str
    canonical_name: str
    aliases: FrozenSet[str] = field(default_factory=frozenset)


@dataclass(frozen=True)
class CanonicalEntity:
    """Immutable canonical entity representation."""
    entity_id: str
    canonical_name: str
    entity_type: str
    aliases: FrozenSet[str] = field(default_factory=frozenset)
