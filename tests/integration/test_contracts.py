"""
Contract Tests

Tests for request/response schema stability, version validation,
and boundary enforcement between backend and model layers.

AXIOM UNDER TEST:
=================
Model cannot access backend internals beyond the adapter.
All communication through typed contracts only.
"""

import pytest
from dataclasses import fields, FrozenInstanceError
from datetime import datetime, timezone

from adapter.contracts import (
    ModelAnalysisRequest,
    ModelAnalysisResponse,
    NarrativeSnapshotInput,
    FragmentBatchInput,
    ModelAnnotation,
    ModelScore,
    UncertaintyRange,
    ModelVersionInfo,
    InvocationMetadata,
    ModelError,
    ModelErrorCode,
)

from .fixtures import (
    create_request_divergence,
    create_request_unsupported_task,
    create_snapshot_standard,
    create_fragment_batch_standard,
    MODEL_VERSION_V1,
    T1,
)


# =============================================================================
# SCHEMA IMMUTABILITY TESTS
# =============================================================================

class TestContractImmutability:
    """
    All contracts MUST be frozen (immutable).
    
    WHY: Prevents accidental mutation of state during processing.
    """
    
    def test_model_version_is_frozen(self):
        """ModelVersionInfo must be immutable."""
        version = MODEL_VERSION_V1
        with pytest.raises(FrozenInstanceError):
            version.model_version = "modified"
    
    def test_fragment_batch_is_frozen(self):
        """FragmentBatchInput must be immutable."""
        batch = create_fragment_batch_standard()
        with pytest.raises(FrozenInstanceError):
            batch.batch_id = "modified"
    
    def test_snapshot_is_frozen(self):
        """NarrativeSnapshotInput must be immutable."""
        snapshot = create_snapshot_standard()
        with pytest.raises(FrozenInstanceError):
            snapshot.thread_id = "modified"
    
    def test_request_is_frozen(self):
        """ModelAnalysisRequest must be immutable."""
        request = create_request_divergence()
        with pytest.raises(FrozenInstanceError):
            request.request_id = "modified"
    
    def test_annotation_is_frozen(self):
        """ModelAnnotation must be immutable."""
        annotation = ModelAnnotation(
            annotation_id="ann_test",
            annotation_type="test",
            entity_id="entity_1",
            entity_type="thread",
            value="test_value",
            confidence=0.8,
            evidence_ids=("ev1", "ev2")
        )
        with pytest.raises(FrozenInstanceError):
            annotation.confidence = 0.5
    
    def test_score_is_frozen(self):
        """ModelScore must be immutable."""
        score = ModelScore(
            score_type="test_score",
            value=0.75,
            uncertainty=UncertaintyRange(lower=0.6, upper=0.9, confidence_level=0.95),
            entity_id="entity_1",
            entity_type="thread"
        )
        with pytest.raises(FrozenInstanceError):
            score.value = 0.5


# =============================================================================
# VERSION TAG VALIDATION TESTS
# =============================================================================

class TestVersionTagValidation:
    """
    Version tags MUST be present and validated on all contracts.
    
    WHY: Required for replay determinism.
    """
    
    def test_model_version_has_required_fields(self):
        """ModelVersionInfo must have all version identification fields."""
        required = {'model_id', 'model_version', 'weights_hash', 'config_hash', 'created_at'}
        actual = {f.name for f in fields(ModelVersionInfo)}
        assert required.issubset(actual), f"Missing fields: {required - actual}"
    
    def test_invocation_metadata_includes_version(self):
        """InvocationMetadata must include full model version."""
        metadata = InvocationMetadata.create(
            model_version=MODEL_VERSION_V1,
            input_data="test_input",
            random_seed=42
        )
        assert metadata.model_version == MODEL_VERSION_V1
        assert metadata.random_seed == 42
    
    def test_invocation_metadata_has_trace_fields(self):
        """InvocationMetadata must have traceability fields."""
        required = {'invocation_id', 'invoked_at', 'model_version', 'input_hash', 'random_seed'}
        actual = {f.name for f in fields(InvocationMetadata)}
        assert required.issubset(actual), f"Missing fields: {required - actual}"


# =============================================================================
# SCHEMA STABILITY TESTS
# =============================================================================

class TestSchemaStability:
    """
    Request/response schemas must be stable.
    
    WHY: Changes break replay compatibility.
    """
    
    def test_request_schema_fields(self):
        """ModelAnalysisRequest must have expected fields."""
        expected = {'request_id', 'request_type', 'snapshot', 'model_version_required', 'random_seed'}
        actual = {f.name for f in fields(ModelAnalysisRequest)}
        assert expected == actual, f"Schema changed. Expected: {expected}, Got: {actual}"
    
    def test_response_schema_fields(self):
        """ModelAnalysisResponse must have expected fields."""
        expected = {
            'response_id', 'request_id', 'success', 'invocation',
            'annotations', 'scores', 'error', 'processing_time_ms'
        }
        actual = {f.name for f in fields(ModelAnalysisResponse)}
        assert expected == actual, f"Schema changed. Expected: {expected}, Got: {actual}"
    
    def test_snapshot_schema_fields(self):
        """NarrativeSnapshotInput must have expected fields."""
        expected = {
            'snapshot_id', 'snapshot_version', 'captured_at', 'thread_id',
            'thread_lifecycle', 'thread_topics', 'fragments', 'existing_annotations'
        }
        actual = {f.name for f in fields(NarrativeSnapshotInput)}
        assert expected == actual, f"Schema changed. Expected: {expected}, Got: {actual}"
    
    def test_error_schema_fields(self):
        """ModelError must have expected fields."""
        expected = {
            'error_code', 'message', 'invocation_id', 'occurred_at',
            'retry_allowed', 'retry_after_seconds', 'input_hash', 'model_version'
        }
        actual = {f.name for f in fields(ModelError)}
        assert expected == actual, f"Schema changed. Expected: {expected}, Got: {actual}"


# =============================================================================
# VALIDATION TESTS
# =============================================================================

class TestContractValidation:
    """
    Contracts must validate their inputs.
    
    WHY: Invalid data must fail explicitly.
    """
    
    def test_uncertainty_range_validates_bounds(self):
        """UncertaintyRange must validate lower <= upper."""
        with pytest.raises(ValueError):
            UncertaintyRange(lower=0.9, upper=0.5, confidence_level=0.95)
    
    def test_uncertainty_range_validates_range(self):
        """UncertaintyRange must be within [0, 1]."""
        with pytest.raises(ValueError):
            UncertaintyRange(lower=-0.1, upper=0.5, confidence_level=0.95)
        
        with pytest.raises(ValueError):
            UncertaintyRange(lower=0.5, upper=1.5, confidence_level=0.95)
    
    def test_annotation_validates_confidence(self):
        """ModelAnnotation must validate confidence in [0, 1]."""
        with pytest.raises(ValueError):
            ModelAnnotation(
                annotation_id="ann_test",
                annotation_type="test",
                entity_id="entity_1",
                entity_type="thread",
                value="test",
                confidence=1.5,  # Invalid
                evidence_ids=()
            )


# =============================================================================
# ERROR CODE COMPLETENESS TESTS
# =============================================================================

class TestErrorCodeCompleteness:
    """
    Error codes must cover all failure modes.
    
    WHY: No silent fallbacks allowed.
    """
    
    def test_required_error_codes_exist(self):
        """Required error codes must be defined."""
        required = {
            'TIMEOUT',
            'INSUFFICIENT_DATA',
            'MODEL_REFUSAL',
            'VERSION_MISMATCH',
            'INTERNAL_ERROR',
            'INVALID_INPUT',
            'REPLAY_FAILED',
        }
        actual = {e.name for e in ModelErrorCode}
        assert required.issubset(actual), f"Missing error codes: {required - actual}"
    
    def test_error_codes_are_string_values(self):
        """Error codes must have string values for serialization."""
        for code in ModelErrorCode:
            assert isinstance(code.value, str), f"{code.name} has non-string value"


# =============================================================================
# CONTENT HASH DETERMINISM TESTS
# =============================================================================

class TestContentHashDeterminism:
    """
    Content hashes must be deterministic.
    
    WHY: Required for replay verification.
    """
    
    def test_fragment_batch_hash_is_deterministic(self):
        """FragmentBatchInput.content_hash() must be deterministic."""
        batch1 = create_fragment_batch_standard()
        batch2 = create_fragment_batch_standard()
        
        assert batch1.content_hash() == batch2.content_hash()
    
    def test_snapshot_hash_is_deterministic(self):
        """NarrativeSnapshotInput.content_hash() must be deterministic."""
        snapshot1 = create_snapshot_standard()
        snapshot2 = create_snapshot_standard()
        
        assert snapshot1.content_hash() == snapshot2.content_hash()
    
    def test_different_content_produces_different_hash(self):
        """Different content must produce different hashes."""
        batch1 = create_fragment_batch_standard()
        batch2 = FragmentBatchInput(
            batch_id="batch_different",
            fragment_ids=("frag_999",),
            fragment_contents=("Different content entirely.",),
            fragment_timestamps=(T1,),
            topic_ids=(("topic_z",),),
            entity_ids=(("entity_z",),),
            source_ids=("source_z",)
        )
        
        assert batch1.content_hash() != batch2.content_hash()
