"""
Layer-Specific Contracts

These contracts define the explicit interfaces between layers.
Each layer exposes its contracts here, and other layers consume only these.

REFACTORING JUSTIFICATION:
==========================
Previous code had the following coupling risks:
1. Fragment model was created directly by ingestion layer (coupling)
2. No separation between raw data and normalized data
3. Thread model contained mutable state

This module eliminates those by:
1. Defining immutable event types for each layer transition
2. Separating RawIngestionEvent from NormalizedFragment
3. Making all state transitions explicit and append-only
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import FrozenSet, Optional, Tuple, Sequence
from enum import Enum, auto

from .base import (
    SourceId, FragmentId, ThreadId, VersionId,
    Timestamp, TimeRange, SourceMetadata, ContentSignature,
    ThreadLifecycleState, FragmentRelation, FragmentRelationType,
    CanonicalTopic, CanonicalEntity, Error, ErrorCode, Result,
    SourceTier  # NEW: Source tier classification
)


# =============================================================================
# INGESTION LAYER CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class RawIngestionEvent:
    """
    IMMUTABLE output from ingestion layer.
    
    This is the ONLY type the ingestion layer may produce.
    Contains raw data exactly as received, with capture metadata.
    
    WHAT THIS TYPE MUST NOT CONTAIN:
    - Normalized or canonicalized data
    - Duplicate flags
    - Topic classifications
    - Entity extractions
    - Any interpreted or derived data
    
    SHADOW MODE SUPPORT:
    - source_tier: Classification (MOCK, PUBLIC_RSS) for filtering
    - raw_payload_path: Path to verbatim raw bytes (for RSS: raw XML)
    """
    event_id: str
    source_metadata: SourceMetadata
    raw_payload: str
    raw_payload_hash: str
    ingestion_timestamp: Timestamp
    batch_id: Optional[str] = None
    
    # NEW: Source tier classification (default MOCK for backward compatibility)
    source_tier: SourceTier = SourceTier.MOCK
    
    # NEW: Path to verbatim raw payload file (optional, for provenance)
    raw_payload_path: Optional[str] = None
    
    @staticmethod
    def create(
        source_id: SourceId,
        raw_payload: str,
        source_confidence: float = 1.0,
        event_timestamp: Optional[Timestamp] = None,
        batch_id: Optional[str] = None,
        source_tier: SourceTier = SourceTier.MOCK,
        raw_payload_path: Optional[str] = None
    ) -> RawIngestionEvent:
        """Factory for deterministic event creation."""
        import hashlib
        now = Timestamp.now()
        payload_hash = hashlib.sha256(raw_payload.encode('utf-8')).hexdigest()
        event_id = f"ing_{payload_hash[:16]}_{now.value.timestamp():.0f}"
        
        return RawIngestionEvent(
            event_id=event_id,
            source_metadata=SourceMetadata(
                source_id=source_id,
                source_confidence=source_confidence,
                capture_timestamp=now,
                event_timestamp=event_timestamp
            ),
            raw_payload=raw_payload,
            raw_payload_hash=payload_hash,
            ingestion_timestamp=now,
            batch_id=batch_id,
            source_tier=source_tier,
            raw_payload_path=raw_payload_path
        )


@dataclass(frozen=True)
class IngestionBatch:
    """Immutable batch of ingestion events."""
    batch_id: str
    events: Tuple[RawIngestionEvent, ...]
    created_at: Timestamp
    source_id: SourceId


# =============================================================================
# NORMALIZATION LAYER CONTRACTS
# =============================================================================

class DuplicateStatus(Enum):
    """Explicit duplicate detection status."""
    UNIQUE = "unique"
    EXACT_DUPLICATE = "exact_duplicate"
    NEAR_DUPLICATE = "near_duplicate"
    UNDETERMINED = "undetermined"


class ContradictionStatus(Enum):
    """Explicit contradiction detection status."""
    NO_CONTRADICTION = "no_contradiction"
    CONTRADICTION_DETECTED = "contradiction_detected"
    POTENTIAL_CONTRADICTION = "potential_contradiction"
    UNDETERMINED = "undetermined"


@dataclass(frozen=True)
class DuplicateInfo:
    """Immutable duplicate detection result."""
    status: DuplicateStatus
    original_fragment_id: Optional[FragmentId] = None
    similarity_score: Optional[float] = None


@dataclass(frozen=True)
class ContradictionInfo:
    """
    Immutable contradiction information.
    
    CRITICAL: Contradictions are REPRESENTED, never RESOLVED.
    This type captures the existence of contradiction without adjudicating truth.
    """
    status: ContradictionStatus
    contradicting_fragment_ids: Tuple[FragmentId, ...] = field(default_factory=tuple)
    contradiction_description: Optional[str] = None


@dataclass(frozen=True)
class EmbeddingVector:
    """
    Immutable embedding vector contract.
    
    ML FENCE POST:
    ==============
    This is a COORDINATE TRANSFORM, not semantic understanding.
    The vector is geometry in embedding space, nothing more.
    
    ALLOWED USES:
    - Distance computation (cosine, euclidean)
    - Nearest neighbor search
    - Clustering input
    
    FORBIDDEN USES:
    - "Similarity > X means same meaning" (threshold is inference)
    - Dimension interpretation (no "dimension 5 = politics")
    - Averaging vectors to "summarize" (lossy, hides uncertainty)
    """
    values: Tuple[float, ...]
    model_id: str  # Which model produced this (for reproducibility)
    model_version: str
    
    @property
    def dimension(self) -> int:
        return len(self.values)
    
    def to_list(self) -> list:
        """Convert to list for numpy/torch operations."""
        return list(self.values)
    
    @staticmethod
    def from_list(values: list, model_id: str, model_version: str) -> 'EmbeddingVector':
        """Create from list of floats."""
        return EmbeddingVector(
            values=tuple(values),
            model_id=model_id,
            model_version=model_version
        )


@dataclass(frozen=True)
class SimilarityScore:
    """
    Immutable similarity score - RAW VALUE, no threshold decision.
    
    ML FENCE POST:
    ==============
    This stores the computed similarity WITHOUT interpreting it.
    The caller receives the number; the system does NOT decide
    what the number "means".
    """
    value: float  # Raw cosine similarity (-1 to 1) or distance
    metric: str   # "cosine", "euclidean", "jaccard", etc.
    
    # Explicitly track that this is a RAW score, not a decision
    threshold_applied: bool = False
    

@dataclass(frozen=True)
class NormalizedFragment:
    """
    IMMUTABLE output from normalization layer.
    
    This is the canonical representation of a fragment after normalization.
    Contains all normalization artifacts but NO interpretation or ranking.
    
    WHAT THIS TYPE MUST NOT CONTAIN:
    - Importance scores
    - Truth judgments  
    - Sentiment analysis
    - Causal inferences
    - Predictions about future events
    
    ML EXTENSION:
    - embedding_vector: Coordinate transform (geometry only)
    - embedding_similarity: Raw similarity to other fragments (no threshold)
    """
    fragment_id: FragmentId
    source_event_id: str  # Reference to original RawIngestionEvent
    content_signature: ContentSignature
    normalized_payload: str
    detected_language: Optional[str]
    canonical_topics: Tuple[CanonicalTopic, ...]
    canonical_entities: Tuple[CanonicalEntity, ...]
    duplicate_info: DuplicateInfo
    contradiction_info: ContradictionInfo
    normalization_timestamp: Timestamp
    source_metadata: SourceMetadata
    
    candidate_relations: Tuple[FragmentRelation, ...] = field(default_factory=tuple)  # Explicit relations (e.g. analyst supplied)
    
    # ML COORDINATE TRANSFORM (optional, computed if model available)
    embedding_vector: Optional[EmbeddingVector] = None
    
    # Similarity to most similar prior fragment (raw score, no decision)
    nearest_similarity: Optional[SimilarityScore] = None
    nearest_fragment_id: Optional[FragmentId] = None


@dataclass(frozen=True)
class NormalizationResult:
    """Result of normalizing a raw ingestion event."""
    success: bool
    fragment: Optional[NormalizedFragment] = None
    error: Optional[Error] = None
    processing_time_ms: float = 0.0


# =============================================================================
# CORE NARRATIVE STATE ENGINE CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class ThreadMembership:
    """Immutable record of a fragment's membership in a thread."""
    thread_id: ThreadId
    fragment_id: FragmentId
    joined_at: Timestamp
    membership_confidence: float  # How confident we are in this grouping
    
    def __post_init__(self):
        if not 0.0 <= self.membership_confidence <= 1.0:
            raise ValueError("membership_confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class ThreadStateSnapshot:
    """
    IMMUTABLE snapshot of thread state at a point in time.
    
    This is an APPEND-ONLY record. State transitions create NEW snapshots,
    never mutate existing ones.
    
    WHAT THIS TYPE MUST NOT CONTAIN:
    - Importance rankings
    - Predicted outcomes
    - Sentiment scores
    - Resolution of contradictions
    """
    version_id: VersionId
    thread_id: ThreadId
    lifecycle_state: ThreadLifecycleState
    member_fragment_ids: Tuple[FragmentId, ...]
    canonical_topics: Tuple[CanonicalTopic, ...]
    relations: Tuple[FragmentRelation, ...]
    created_at: Timestamp
    previous_version_id: Optional[str] = None
    
    # Absence tracking (presence/absence are first-class concepts)
    last_activity_timestamp: Optional[Timestamp] = None
    expected_activity_interval_seconds: Optional[int] = None
    absence_detected: bool = False
    
    # Divergence tracking
    diverged_from_version_id: Optional[str] = None
    divergence_reason: Optional[str] = None


@dataclass(frozen=True)
class NarrativeStateEvent:
    """
    IMMUTABLE event emitted by the core narrative state engine.
    
    Every state change produces one of these events. They are the
    primary output of the core engine and input to storage.
    """
    event_id: str
    event_type: str  # thread_created, thread_updated, state_transition, etc.
    thread_id: ThreadId
    timestamp: Timestamp
    new_state_snapshot: ThreadStateSnapshot
    trigger_fragment_id: Optional[FragmentId] = None
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


class ThreadProcessingResult(Enum):
    """Explicit result of processing a fragment into the thread engine."""
    NEW_THREAD_CREATED = "new_thread_created"
    ADDED_TO_EXISTING = "added_to_existing"
    DUPLICATE_SKIPPED = "duplicate_skipped"
    CONTRADICTION_RECORDED = "contradiction_recorded"
    DIVERGENCE_DETECTED = "divergence_detected"
    PROCESSING_FAILED = "processing_failed"


@dataclass(frozen=True)
class FragmentProcessingOutcome:
    """Immutable result of processing a normalized fragment."""
    result: ThreadProcessingResult
    thread_id: Optional[ThreadId] = None
    state_event: Optional[NarrativeStateEvent] = None
    error: Optional[Error] = None


# =============================================================================
# TEMPORAL STORAGE LAYER CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class StorageWriteResult:
    """Immutable result of a storage write operation."""
    success: bool
    version_id: Optional[VersionId] = None
    error: Optional[Error] = None
    write_timestamp: Optional[Timestamp] = None


@dataclass(frozen=True)
class VersionedSnapshot:
    """
    Immutable versioned snapshot from temporal storage.
    
    Supports time-travel queries by maintaining full version history.
    """
    version_id: VersionId
    entity_type: str  # "thread", "fragment", etc.
    entity_id: str
    snapshot_data: ThreadStateSnapshot  # or other snapshot types
    created_at: Timestamp
    lineage: Tuple[str, ...]  # Chain of version IDs back to origin


@dataclass(frozen=True)
class TimelinePoint:
    """Immutable point on a timeline for query results."""
    timestamp: Timestamp
    version_id: VersionId
    entity_id: str
    state_summary: str


@dataclass(frozen=True)
class Timeline:
    """Immutable timeline representation."""
    thread_id: ThreadId
    points: Tuple[TimelinePoint, ...]
    time_range: TimeRange
    total_versions: int


# =============================================================================
# QUERY LAYER CONTRACTS
# =============================================================================

class QueryType(Enum):
    """Explicit query types."""
    TIMELINE = "timeline"
    THREAD_STATE = "thread_state"
    FRAGMENT_TRACE = "fragment_trace"
    COMPARISON = "comparison"
    SEARCH = "search"
    REWIND = "rewind"
    SIMILARITY = "similarity"
    TOPOLOGY = "topology"
    ALIGNMENT = "alignment"


@dataclass(frozen=True)
class QueryRequest:
    """
    Immutable query request.
    
    All parameters are explicit - no implicit defaults that could
    lead to non-deterministic behavior.
    """
    query_id: str
    query_type: QueryType
    time_range: Optional[TimeRange] = None
    thread_id: Optional[ThreadId] = None
    fragment_id: Optional[FragmentId] = None
    target_timestamp: Optional[Timestamp] = None
    comparison_thread_id: Optional[ThreadId] = None  # NEW: For alignment/comparison
    max_results: int = 100
    offset: int = 0


@dataclass(frozen=True)
class QueryError:
    """Explicit query error with full context."""
    error_code: ErrorCode
    message: str
    query_id: str
    timestamp: Timestamp


@dataclass(frozen=True)
class QueryResult:
    """
    IMMUTABLE query result.
    
    Contains explicit success/failure state, never implicit.
    Empty results are distinct from errors.
    """
    query_id: str
    query_type: QueryType
    success: bool
    result_count: int
    results: Tuple[object, ...]
    error: Optional[QueryError] = None
    execution_time_ms: float = 0.0
    
    @staticmethod
    def empty(query_id: str, query_type: QueryType, execution_time_ms: float) -> QueryResult:
        """Create an empty but successful result."""
        return QueryResult(
            query_id=query_id,
            query_type=query_type,
            success=True,
            result_count=0,
            results=(),
            execution_time_ms=execution_time_ms
        )
    
    @staticmethod
    def failed(query_id: str, query_type: QueryType, error: QueryError) -> QueryResult:
        """Create a failed result with explicit error."""
        return QueryResult(
            query_id=query_id,
            query_type=query_type,
            success=False,
            result_count=0,
            results=(),
            error=error
        )


# =============================================================================
# OBSERVABILITY LAYER CONTRACTS
# =============================================================================

class AuditEventType(Enum):
    """Explicit audit event types."""
    INGESTION = "ingestion"
    NORMALIZATION = "normalization"
    STATE_CHANGE = "state_change"
    QUERY = "query"
    ERROR = "error"
    SYSTEM = "system"


@dataclass(frozen=True)
class AuditLogEntry:
    """Immutable audit log entry."""
    entry_id: str
    event_type: AuditEventType
    timestamp: Timestamp
    layer: str  # Which layer generated this
    action: str
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    parent_entry_id: Optional[str] = None  # For lineage tracking


@dataclass(frozen=True)
class MetricPoint:
    """Immutable metric data point."""
    metric_name: str
    value: float
    timestamp: Timestamp
    labels: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReplayCheckpoint:
    """
    Immutable checkpoint for replay capability.
    
    Contains all information needed to rebuild state from this point.
    """
    checkpoint_id: str
    timestamp: Timestamp
    layer: str
    sequence_number: int
    state_hash: str  # Hash of all state at this point for verification
