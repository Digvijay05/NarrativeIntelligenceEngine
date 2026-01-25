"""
Integration Test Fixtures

Versioned, hashable fixtures for deterministic testing.
All fixtures are explicit - no random generation.
"""

from datetime import datetime, timezone
from typing import Tuple
import hashlib

from adapter.contracts import (
    ModelAnalysisRequest,
    NarrativeSnapshotInput,
    FragmentBatchInput,
    ModelVersionInfo,
)


# =============================================================================
# FIXED TIMESTAMPS (deterministic)
# =============================================================================

EPOCH = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
T1 = datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
T2 = datetime(2026, 1, 1, 10, 5, 0, tzinfo=timezone.utc)
T3 = datetime(2026, 1, 1, 10, 10, 0, tzinfo=timezone.utc)


# =============================================================================
# MODEL VERSION FIXTURES
# =============================================================================

MODEL_VERSION_V1 = ModelVersionInfo(
    model_id="narrative_intelligence_model",
    model_version="1.0.0",
    weights_hash="a1b2c3d4e5f6g7h8",
    config_hash="h8g7f6e5d4c3b2a1",
    created_at=EPOCH
)

MODEL_VERSION_V2 = ModelVersionInfo(
    model_id="narrative_intelligence_model",
    model_version="2.0.0",
    weights_hash="x1y2z3w4v5u6t7s8",
    config_hash="s8t7u6v5w4x3y2z1",
    created_at=EPOCH
)


# =============================================================================
# FRAGMENT BATCH FIXTURES
# =============================================================================

def create_fragment_batch_minimal() -> FragmentBatchInput:
    """Single fragment batch for minimal testing."""
    return FragmentBatchInput(
        batch_id="batch_minimal_001",
        fragment_ids=("frag_001",),
        fragment_contents=("This is the first fragment content.",),
        fragment_timestamps=(T1,),
        topic_ids=(("topic_a",),),
        entity_ids=(("entity_x",),),
        source_ids=("source_alpha",)
    )


def create_fragment_batch_standard() -> FragmentBatchInput:
    """Standard 3-fragment batch for most tests."""
    return FragmentBatchInput(
        batch_id="batch_standard_001",
        fragment_ids=("frag_001", "frag_002", "frag_003"),
        fragment_contents=(
            "First fragment: The event began at 10am.",
            "Second fragment: Officials confirmed the incident.",
            "Third fragment: Investigation is ongoing."
        ),
        fragment_timestamps=(T1, T2, T3),
        topic_ids=(
            ("topic_incident", "topic_news"),
            ("topic_incident", "topic_officials"),
            ("topic_incident", "topic_investigation")
        ),
        entity_ids=(
            ("entity_event", "entity_location"),
            ("entity_officials", "entity_event"),
            ("entity_investigation", "entity_event")
        ),
        source_ids=("source_alpha", "source_beta", "source_alpha")
    )


def create_fragment_batch_empty() -> FragmentBatchInput:
    """Empty batch for edge case testing."""
    return FragmentBatchInput(
        batch_id="batch_empty_001",
        fragment_ids=(),
        fragment_contents=(),
        fragment_timestamps=(),
        topic_ids=(),
        entity_ids=(),
        source_ids=()
    )


def create_fragment_batch_with_gaps() -> FragmentBatchInput:
    """Batch with temporal gaps (missing hour between fragments)."""
    t_gap = datetime(2026, 1, 1, 11, 30, 0, tzinfo=timezone.utc)  # 80 min gap
    return FragmentBatchInput(
        batch_id="batch_gapped_001",
        fragment_ids=("frag_001", "frag_002"),
        fragment_contents=(
            "Fragment before gap.",
            "Fragment after gap - context missing."
        ),
        fragment_timestamps=(T1, t_gap),
        topic_ids=(("topic_a",), ("topic_a",)),
        entity_ids=(("entity_x",), ("entity_x",)),
        source_ids=("source_alpha", "source_alpha")
    )


# =============================================================================
# SNAPSHOT FIXTURES
# =============================================================================

def create_snapshot_standard() -> NarrativeSnapshotInput:
    """Standard snapshot for most tests."""
    return NarrativeSnapshotInput(
        snapshot_id="snap_standard_001",
        snapshot_version="v1",
        captured_at=T1,
        thread_id="thread_main_001",
        thread_lifecycle="active",
        thread_topics=("topic_incident", "topic_news"),
        fragments=create_fragment_batch_standard(),
        existing_annotations=()
    )


def create_snapshot_empty() -> NarrativeSnapshotInput:
    """Empty snapshot for edge case testing."""
    return NarrativeSnapshotInput(
        snapshot_id="snap_empty_001",
        snapshot_version="v1",
        captured_at=T1,
        thread_id="thread_empty_001",
        thread_lifecycle="emerging",
        thread_topics=(),
        fragments=create_fragment_batch_empty(),
        existing_annotations=()
    )


def create_snapshot_with_gaps() -> NarrativeSnapshotInput:
    """Snapshot with temporal gaps."""
    return NarrativeSnapshotInput(
        snapshot_id="snap_gapped_001",
        snapshot_version="v1",
        captured_at=T1,
        thread_id="thread_gapped_001",
        thread_lifecycle="active",
        thread_topics=("topic_a",),
        fragments=create_fragment_batch_with_gaps(),
        existing_annotations=()
    )


# =============================================================================
# REQUEST FIXTURES
# =============================================================================

def create_request_divergence() -> ModelAnalysisRequest:
    """Request for divergence scoring."""
    return ModelAnalysisRequest(
        request_id="req_divergence_001",
        request_type="divergence_scoring",
        snapshot=create_snapshot_standard(),
        random_seed=42
    )


def create_request_contradiction() -> ModelAnalysisRequest:
    """Request for contradiction detection."""
    return ModelAnalysisRequest(
        request_id="req_contradiction_001",
        request_type="contradiction_detection",
        snapshot=create_snapshot_standard(),
        random_seed=42
    )


def create_request_coherence() -> ModelAnalysisRequest:
    """Request for coherence analysis."""
    return ModelAnalysisRequest(
        request_id="req_coherence_001",
        request_type="coherence_analysis",
        snapshot=create_snapshot_standard(),
        random_seed=42
    )


def create_request_lifecycle() -> ModelAnalysisRequest:
    """Request for lifecycle prediction."""
    return ModelAnalysisRequest(
        request_id="req_lifecycle_001",
        request_type="lifecycle_prediction",
        snapshot=create_snapshot_standard(),
        random_seed=42
    )


def create_request_empty_snapshot() -> ModelAnalysisRequest:
    """Request with empty snapshot."""
    return ModelAnalysisRequest(
        request_id="req_empty_001",
        request_type="divergence_scoring",
        snapshot=create_snapshot_empty(),
        random_seed=42
    )


def create_request_with_gaps() -> ModelAnalysisRequest:
    """Request with gapped timeline."""
    return ModelAnalysisRequest(
        request_id="req_gapped_001",
        request_type="coherence_analysis",
        snapshot=create_snapshot_with_gaps(),
        random_seed=42
    )


def create_request_unsupported_task() -> ModelAnalysisRequest:
    """Request with unsupported task type."""
    return ModelAnalysisRequest(
        request_id="req_unsupported_001",
        request_type="sentiment_analysis",  # Not supported
        snapshot=create_snapshot_standard(),
        random_seed=42
    )


# =============================================================================
# HASH UTILITIES
# =============================================================================

def hash_response(response) -> str:
    """
    Compute deterministic hash of response for replay comparison.
    
    Excludes timestamps that vary between runs.
    Includes all content that must be deterministic.
    """
    content = (
        f"success={response.success}|"
        f"request_id={response.request_id}|"
        f"annotations={len(response.annotations)}|"
        f"scores={len(response.scores)}|"
    )
    
    # Hash annotation content
    for ann in sorted(response.annotations, key=lambda a: a.annotation_id):
        content += f"ann:{ann.annotation_type}:{ann.entity_id}:{ann.value}:{ann.confidence}|"
    
    # Hash score content
    for score in sorted(response.scores, key=lambda s: (s.score_type, s.entity_id)):
        content += f"score:{score.score_type}:{score.entity_id}:{score.value:.6f}|"
    
    return hashlib.sha256(content.encode()).hexdigest()
