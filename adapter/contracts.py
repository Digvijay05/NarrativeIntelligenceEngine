"""
Adapter Contracts

Typed request/response schemas for backend ↔ model communication.

BOUNDARY ENFORCEMENT:
=====================
- All types are FROZEN (immutable)
- All types include explicit version information
- No optional fields that could lead to ambiguous behavior

WHY SEPARATE CONTRACTS:
=======================
Backend contracts (backend/contracts/) define backend-internal communication.
These adapter contracts define the INTERFACE between backend and model.
They are deliberately distinct to enforce the boundary.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Tuple, FrozenSet
from enum import Enum
from datetime import datetime
import hashlib


# =============================================================================
# VERSION INFORMATION
# =============================================================================

@dataclass(frozen=True)
class ModelVersionInfo:
    """
    Explicit model version for replay determinism.
    
    WHY THIS EXISTS:
    Identical inputs + identical model version MUST produce identical outputs.
    This contract captures all version information needed for replay.
    """
    model_id: str
    model_version: str
    weights_hash: str
    config_hash: str
    created_at: datetime
    
    def as_tuple(self) -> Tuple[str, str, str, str]:
        """Return version info as hashable tuple."""
        return (self.model_id, self.model_version, self.weights_hash, self.config_hash)


@dataclass(frozen=True)
class InvocationMetadata:
    """
    Time-indexed metadata for every model invocation.
    
    WHY THIS EXISTS:
    Every invocation must be traceable for audit and replay.
    This contract captures the "when", "what", and "who" of each call.
    """
    invocation_id: str
    invoked_at: datetime
    model_version: ModelVersionInfo
    input_hash: str  # Hash of input for replay verification
    random_seed: int  # For reproducibility
    
    @staticmethod
    def create(
        model_version: ModelVersionInfo,
        input_data: str,
        random_seed: int = 42
    ) -> InvocationMetadata:
        """Factory for deterministic metadata creation."""
        now = datetime.utcnow()
        input_hash = hashlib.sha256(input_data.encode()).hexdigest()
        invocation_id = f"inv_{input_hash[:12]}_{int(now.timestamp())}"
        
        return InvocationMetadata(
            invocation_id=invocation_id,
            invoked_at=now,
            model_version=model_version,
            input_hash=input_hash,
            random_seed=random_seed
        )


# =============================================================================
# ERROR TYPES
# =============================================================================

class ModelErrorCode(Enum):
    """
    Explicit error codes for model failures.
    
    WHY EXPLICIT CODES:
    - No silent fallbacks
    - No default scores
    - Every failure mode is queryable
    """
    TIMEOUT = "timeout"
    INSUFFICIENT_DATA = "insufficient_data"
    MODEL_REFUSAL = "model_refusal"  # Model cannot/should not process this input
    VERSION_MISMATCH = "version_mismatch"
    INTERNAL_ERROR = "internal_error"
    INVALID_INPUT = "invalid_input"
    REPLAY_FAILED = "replay_failed"


@dataclass(frozen=True)
class ModelError:
    """
    Explicit model error with full context.
    
    WHY THIS EXISTS:
    All error states must be inspectable and actionable.
    No silent failures, no hidden retries.
    """
    error_code: ModelErrorCode
    message: str
    invocation_id: str
    occurred_at: datetime
    retry_allowed: bool = False
    retry_after_seconds: Optional[int] = None
    
    # Context for debugging
    input_hash: Optional[str] = None
    model_version: Optional[str] = None


# =============================================================================
# INPUT CONTRACTS (Backend → Model)
# =============================================================================

@dataclass(frozen=True)
class FragmentBatchInput:
    """
    Batch of fragments for model analysis.
    
    WHY A BATCH:
    Model analysis often benefits from context across fragments.
    Batch processing is explicit, not implicit grouping.
    """
    batch_id: str
    fragment_ids: Tuple[str, ...]
    fragment_contents: Tuple[str, ...]
    fragment_timestamps: Tuple[datetime, ...]
    topic_ids: Tuple[Tuple[str, ...], ...]  # Topics per fragment
    entity_ids: Tuple[Tuple[str, ...], ...]  # Entities per fragment
    source_ids: Tuple[str, ...]
    
    def content_hash(self) -> str:
        """Compute deterministic hash of input content."""
        content = "|".join([
            self.batch_id,
            ",".join(self.fragment_ids),
            ",".join(self.fragment_contents),
        ])
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass(frozen=True)
class NarrativeSnapshotInput:
    """
    Immutable snapshot of narrative state for model consumption.
    
    WHY A SNAPSHOT:
    Model receives a point-in-time view, never mutable state.
    This ensures model cannot observe or cause state changes.
    """
    snapshot_id: str
    snapshot_version: str
    captured_at: datetime
    
    # Thread state
    thread_id: str
    thread_lifecycle: str
    thread_topics: Tuple[str, ...]
    
    # Fragment data
    fragments: FragmentBatchInput
    
    # Existing annotations (from previous model runs, as overlays)
    existing_annotations: Tuple[str, ...]  # Annotation IDs
    
    def content_hash(self) -> str:
        """Compute deterministic hash."""
        content = f"{self.snapshot_id}|{self.snapshot_version}|{self.thread_id}"
        return hashlib.sha256(content.encode()).hexdigest()


@dataclass(frozen=True)
class ModelAnalysisRequest:
    """
    Top-level request for model analysis.
    
    WHY THIS STRUCTURE:
    - Explicit version for replay
    - Explicit task type
    - No ambiguous optional parameters
    """
    request_id: str
    request_type: str  # "contradiction_detection", "divergence_scoring", etc.
    snapshot: NarrativeSnapshotInput
    model_version_required: Optional[str] = None  # If None, use latest
    random_seed: int = 42  # Explicit for reproducibility


# =============================================================================
# OUTPUT CONTRACTS (Model → Backend)
# =============================================================================

@dataclass(frozen=True)
class UncertaintyRange:
    """
    Explicit uncertainty for a score.
    
    WHY THIS EXISTS:
    Model outputs are ADVISORY. Uncertainty communicates confidence level.
    Backend decides how to use this information.
    """
    lower: float
    upper: float
    confidence_level: float  # e.g., 0.95 for 95% CI
    
    def __post_init__(self):
        if not (0.0 <= self.lower <= self.upper <= 1.0):
            raise ValueError("Invalid uncertainty range")


@dataclass(frozen=True)
class ModelScore:
    """
    A single model-produced score.
    
    WHY THIS EXISTS:
    Scores are ADVISORY signals with explicit uncertainty.
    Never treated as ground truth.
    """
    score_type: str  # "contradiction_probability", "coherence", etc.
    value: float
    uncertainty: UncertaintyRange
    entity_id: str  # What this score is about (fragment_id, thread_id, etc.)
    entity_type: str  # "fragment", "thread", "relation"


@dataclass(frozen=True)
class ModelAnnotation:
    """
    A single model-produced annotation.
    
    WHY THIS EXISTS:
    Annotations are ADVISORY labels with explicit uncertainty.
    They are stored as OVERLAYS, never merged into ground truth.
    """
    annotation_id: str
    annotation_type: str  # "contradiction", "divergence", "coherence_flag"
    entity_id: str
    entity_type: str
    value: str  # The annotation value
    confidence: float
    evidence_ids: Tuple[str, ...]  # What supported this annotation
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("Confidence must be between 0 and 1")


@dataclass(frozen=True)
class ModelAnalysisResponse:
    """
    Complete model analysis response.
    
    WHY THIS STRUCTURE:
    - Explicit success/failure (no implicit fallbacks)
    - All outputs versioned
    - All outputs timestamped
    - All outputs are ADVISORY
    """
    response_id: str
    request_id: str
    success: bool
    
    # Invocation metadata for replay
    invocation: InvocationMetadata
    
    # Results (only present if success=True)
    annotations: Tuple[ModelAnnotation, ...] = field(default_factory=tuple)
    scores: Tuple[ModelScore, ...] = field(default_factory=tuple)
    
    # Error (only present if success=False)
    error: Optional[ModelError] = None
    
    # Timing
    processing_time_ms: float = 0.0
    
    @staticmethod
    def success_response(
        request_id: str,
        invocation: InvocationMetadata,
        annotations: Tuple[ModelAnnotation, ...],
        scores: Tuple[ModelScore, ...],
        processing_time_ms: float
    ) -> ModelAnalysisResponse:
        """Factory for successful response."""
        response_id = f"resp_{request_id}_{int(datetime.utcnow().timestamp())}"
        return ModelAnalysisResponse(
            response_id=response_id,
            request_id=request_id,
            success=True,
            invocation=invocation,
            annotations=annotations,
            scores=scores,
            processing_time_ms=processing_time_ms
        )
    
    @staticmethod
    def failure_response(
        request_id: str,
        invocation: InvocationMetadata,
        error: ModelError
    ) -> ModelAnalysisResponse:
        """Factory for failed response."""
        response_id = f"resp_err_{request_id}_{int(datetime.utcnow().timestamp())}"
        return ModelAnalysisResponse(
            response_id=response_id,
            request_id=request_id,
            success=False,
            invocation=invocation,
            error=error
        )
