"""
Temporal Contracts

Defines immutable data structures for Phase 3 (Temporal Inference) outputs.
All temporal prediction, uncertainty, and alignment results use these contracts.

CRITICAL: All functions producing these contracts MUST be deterministic.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Optional
from datetime import datetime
from enum import Enum, auto


# =============================================================================
# ENUMS
# =============================================================================

class LifecycleState(Enum):
    """Lifecycle states for narrative threads."""
    EMERGING = "emerging"
    ACTIVE = "active"
    DORMANT = "dormant"
    TERMINATED = "terminated"
    DIVERGED = "diverged"


class PredictionConfidence(Enum):
    """Confidence levels for predictions."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNCERTAIN = "uncertain"


class AlignmentStatus(Enum):
    """Status of temporal alignment."""
    ALIGNED = "aligned"
    PARTIAL = "partial"
    MISALIGNED = "misaligned"
    UNKNOWN = "unknown"


# =============================================================================
# TEMPORAL STATE CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class TemporalState:
    """
    Immutable temporal state of a narrative element.
    
    This is the CORE contract for Phase 3.
    All temporal reasoning operates on these states.
    """
    state_id: str
    entity_id: str
    entity_type: str  # "thread", "fragment", "topic"
    lifecycle: LifecycleState
    timestamp: datetime
    sequence_position: int
    version: str
    
    # Temporal properties
    time_since_last_activity: Optional[float] = None  # seconds
    expected_next_activity: Optional[float] = None  # seconds
    activity_count: int = 0
    
    # References
    previous_state_id: Optional[str] = None
    parent_version: Optional[str] = None


@dataclass(frozen=True)
class StateTransition:
    """Record of a state transition."""
    transition_id: str
    from_state_id: str
    to_state_id: str
    from_lifecycle: LifecycleState
    to_lifecycle: LifecycleState
    trigger: str  # What caused the transition
    timestamp: datetime
    confidence: float


# =============================================================================
# PREDICTION CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class PredictionResult:
    """
    Result of a temporal prediction.
    
    Immutable prediction with confidence and supporting evidence.
    """
    prediction_id: str
    entity_id: str
    prediction_type: str  # "lifecycle", "continuation", "divergence"
    predicted_value: str  # The prediction itself
    confidence: float
    confidence_level: PredictionConfidence
    model_version: str
    timestamp: datetime
    
    # Supporting information
    evidence_ids: Tuple[str, ...] = field(default_factory=tuple)
    alternative_predictions: Tuple[Tuple[str, float], ...] = field(default_factory=tuple)
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class LifecyclePrediction:
    """Prediction of narrative lifecycle state."""
    prediction_id: str
    thread_id: str
    current_state: LifecycleState
    predicted_state: LifecycleState
    transition_probability: float
    time_to_transition: Optional[float]  # seconds
    confidence: float
    model_version: str
    timestamp: datetime


@dataclass(frozen=True)
class ContinuationPrediction:
    """Prediction of expected narrative continuation."""
    prediction_id: str
    thread_id: str
    expected_topic_ids: Tuple[str, ...]
    expected_entity_ids: Tuple[str, ...]
    expected_timeframe: Tuple[float, float]  # (min_seconds, max_seconds)
    probability: float
    model_version: str
    timestamp: datetime


@dataclass(frozen=True)
class DivergencePrediction:
    """Prediction of narrative divergence risk."""
    prediction_id: str
    thread_id: str
    divergence_probability: float
    potential_branches: int
    risk_factors: Tuple[str, ...]
    model_version: str
    timestamp: datetime


# =============================================================================
# UNCERTAINTY CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class UncertaintyEstimate:
    """
    Quantified uncertainty for a prediction.
    
    Provides confidence intervals and probability distributions.
    """
    estimate_id: str
    prediction_id: str
    
    # Point estimate
    mean: float
    
    # Confidence interval
    lower_bound: float
    upper_bound: float
    confidence_level: float  # e.g., 0.95 for 95% CI
    
    # Distribution info
    distribution_type: str  # "normal", "beta", "empirical"
    distribution_params: Tuple[Tuple[str, float], ...]
    
    # Calibration
    is_calibrated: bool
    calibration_score: Optional[float] = None


@dataclass(frozen=True)
class TemporalCoherence:
    """Temporal coherence probability for a sequence."""
    coherence_id: str
    sequence_id: str
    coherence_score: float  # 0.0 to 1.0
    gaps_detected: int
    anomalies_detected: int
    confidence: float
    timestamp: datetime


@dataclass(frozen=True)
class SourceCredibility:
    """Credibility assessment for a source."""
    credibility_id: str
    source_id: str
    credibility_score: float  # 0.0 to 1.0
    consistency_score: float
    accuracy_history: Tuple[float, ...]
    last_updated: datetime


# =============================================================================
# ALIGNMENT CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class AlignmentResult:
    """
    Result of temporal alignment between sources/timelines.
    
    Used for multi-source synchronization.
    """
    alignment_id: str
    source_ids: Tuple[str, ...]
    status: AlignmentStatus
    aligned_timestamps: Tuple[Tuple[str, datetime], ...]  # entity_id -> aligned_time
    offset_corrections: Tuple[Tuple[str, float], ...]  # source_id -> offset_seconds
    confidence: float
    timestamp: datetime


@dataclass(frozen=True)
class TimelineGap:
    """Representation of a gap in a timeline."""
    gap_id: str
    timeline_id: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    gap_type: str  # "missing_data", "silence", "unknown"
    interpolation_available: bool


@dataclass(frozen=True)
class GapFillResult:
    """Result of filling a timeline gap."""
    result_id: str
    gap_id: str
    fill_method: str  # "interpolation", "inference", "none"
    filled_states: Tuple[TemporalState, ...]
    confidence: float
    timestamp: datetime


# =============================================================================
# REPLAY CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class ReplayCheckpoint:
    """
    Checkpoint for deterministic replay.
    
    Stores all state needed to replay from this point.
    """
    checkpoint_id: str
    timestamp: datetime
    sequence_number: int
    state_hash: str  # Hash of all state at this point
    model_versions: Tuple[Tuple[str, str], ...]  # model_type -> version
    random_seed: int
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ReplayResult:
    """Result of replaying from a checkpoint."""
    result_id: str
    checkpoint_id: str
    events_replayed: int
    final_state_hash: str
    matches_original: bool
    timestamp: datetime
    discrepancies: Tuple[str, ...] = field(default_factory=tuple)


# =============================================================================
# VERSION COMPARISON CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class VersionComparison:
    """Comparison between two versions of state."""
    comparison_id: str
    version_a: str
    version_b: str
    entity_id: str
    differences: Tuple[Tuple[str, str, str], ...]  # (field, value_a, value_b)
    similarity_score: float
    timestamp: datetime


@dataclass(frozen=True)
class BranchingConfidence:
    """Confidence tracking for timeline branching."""
    tracking_id: str
    branch_point: datetime
    branch_count: int
    dominant_branch_probability: float
    branch_confidences: Tuple[Tuple[str, float], ...]  # branch_id -> confidence
    timestamp: datetime
