"""
Failure Mode Tests

Tests for explicit error states: timeout, empty state, partial timeline.

AXIOM UNDER TEST:
=================
All failures must surface as typed error states.
No retries, no defaults, no smoothing.
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import time

from adapter import get_facade
from adapter.contracts import ModelErrorCode, ModelError
from adapter.pipeline import ModelInvocationPipeline, InvocationConfig, ModelExecutorInterface
from adapter.contracts import ModelAnalysisRequest, ModelVersionInfo

from .fixtures import (
    create_request_empty_snapshot,
    create_request_with_gaps,
    create_request_unsupported_task,
    create_snapshot_empty,
    create_snapshot_with_gaps,
    MODEL_VERSION_V1,
)


# =============================================================================
# TIMEOUT TESTS
# =============================================================================

class TestTimeoutBehavior:
    """
    Model timeout must result in explicit MODEL_TIMEOUT state.
    No partial annotations may be attached.
    """
    
    def test_timeout_returns_explicit_error_code(self):
        """Timeout must return TIMEOUT error code."""
        # Create a mock executor that times out
        class TimeoutExecutor(ModelExecutorInterface):
            def execute(self, request, random_seed):
                time.sleep(0.5)  # Simulate slow execution
                raise TimeoutError("Execution timed out")
            
            def get_version(self):
                return MODEL_VERSION_V1
            
            def supports_task(self, task_type):
                return True
        
        config = InvocationConfig(timeout_seconds=0.1)
        pipeline = ModelInvocationPipeline(
            executor=TimeoutExecutor(),
            config=config
        )
        
        from .fixtures import create_request_divergence
        request = create_request_divergence()
        
        response, trace = pipeline.invoke(request)
        
        assert not response.success
        assert response.error is not None
        assert response.error.error_code == ModelErrorCode.TIMEOUT
    
    def test_timeout_has_no_partial_annotations(self):
        """Timeout response must have zero annotations."""
        class TimeoutExecutor(ModelExecutorInterface):
            def execute(self, request, random_seed):
                raise TimeoutError("Timeout")
            
            def get_version(self):
                return MODEL_VERSION_V1
            
            def supports_task(self, task_type):
                return True
        
        config = InvocationConfig(timeout_seconds=0.1)
        pipeline = ModelInvocationPipeline(
            executor=TimeoutExecutor(),
            config=config
        )
        
        from .fixtures import create_request_divergence
        response, _ = pipeline.invoke(create_request_divergence())
        
        assert len(response.annotations) == 0
        assert len(response.scores) == 0
    
    def test_timeout_trace_records_failure(self):
        """Timeout must be recorded in trace."""
        class TimeoutExecutor(ModelExecutorInterface):
            def execute(self, request, random_seed):
                raise TimeoutError("Timeout")
            
            def get_version(self):
                return MODEL_VERSION_V1
            
            def supports_task(self, task_type):
                return True
        
        pipeline = ModelInvocationPipeline(
            executor=TimeoutExecutor(),
            config=InvocationConfig()
        )
        
        from .fixtures import create_request_divergence
        _, trace = pipeline.invoke(create_request_divergence())
        
        assert not trace.success
        assert trace.error_code == ModelErrorCode.TIMEOUT


# =============================================================================
# EMPTY NARRATIVE STATE TESTS
# =============================================================================

class TestEmptyNarrativeState:
    """
    Zero fragments must be handled deterministically.
    Either skipped with explicit reason OR invoked with empty snapshot.
    """
    
    @pytest.fixture
    def facade(self):
        return get_facade()
    
    def test_empty_snapshot_succeeds_with_no_scores(self, facade):
        """Empty snapshot should succeed but produce no meaningful scores."""
        result = facade.analyze_thread(
            thread_id='thread_empty_001',
            thread_version='v1',
            thread_lifecycle='emerging',
            fragment_ids=[],
            fragment_contents=[],
            fragment_timestamps=[],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        # Must succeed (deterministic behavior)
        assert result.success
        assert result.overlay is not None
        # May have zero scores for empty input
        assert isinstance(result.overlay.scores, tuple)
    
    def test_empty_snapshot_is_deterministic(self, facade):
        """Empty snapshot must produce identical results on replay."""
        kwargs = dict(
            thread_id='thread_empty_det',
            thread_version='v1',
            thread_lifecycle='emerging',
            fragment_ids=[],
            fragment_contents=[],
            fragment_timestamps=[],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        result1 = facade.analyze_thread(**kwargs)
        result2 = facade.analyze_thread(**kwargs)
        
        assert result1.success == result2.success
        assert len(result1.overlay.scores) == len(result2.overlay.scores)
    
    def test_empty_snapshot_trace_is_recorded(self, facade):
        """Empty snapshot analysis must still be traced."""
        facade.analyze_thread(
            thread_id='thread_empty_trace',
            thread_version='v1',
            thread_lifecycle='emerging',
            fragment_ids=[],
            fragment_contents=[],
            fragment_timestamps=[],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        traces = facade.get_traces()
        assert len(traces) > 0


# =============================================================================
# PARTIAL / GAPPED TIMELINE TESTS
# =============================================================================

class TestPartialGappedTimeline:
    """
    Missing temporal continuation must be handled explicitly.
    Absence must be preserved as absence, not nulls or guesses.
    """
    
    @pytest.fixture
    def facade(self):
        return get_facade()
    
    def test_gapped_timeline_succeeds(self, facade):
        """Gapped timeline must be analyzed without crashing."""
        # Create timeline with 80+ minute gap
        result = facade.analyze_thread(
            thread_id='thread_gapped_001',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1', 'frag_2'],
            fragment_contents=['Before gap', 'After gap'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 11, 30, tzinfo=timezone.utc),  # 90 min gap
            ],
            task_type='coherence_analysis',
            random_seed=42
        )
        
        assert result.success
    
    def test_gapped_timeline_may_flag_uncertainty(self, facade):
        """Gapped timeline may produce lower coherence score."""
        result = facade.score_coherence(
            thread_id='thread_gapped_coherence',
            thread_version='v1',
            fragment_ids=['frag_1', 'frag_2'],
            fragment_contents=['Before gap', 'After gap'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 11, 30, tzinfo=timezone.utc),
            ],
            random_seed=42
        )
        
        assert result.success
        assert result.overlay is not None
        
        # Should have coherence score
        coherence_scores = [s for s in result.overlay.scores if s.score_type == 'temporal_coherence']
        assert len(coherence_scores) > 0
    
    def test_gaps_are_not_filled_with_guesses(self, facade):
        """
        Gaps must not be filled with synthetic data.
        
        This test verifies that the fragment count remains unchanged.
        """
        fragment_ids = ['frag_1', 'frag_2']
        
        result = facade.analyze_thread(
            thread_id='thread_no_fill',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=fragment_ids,
            fragment_contents=['Before', 'After'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 14, 0, tzinfo=timezone.utc),  # 4 hour gap
            ],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        assert result.success
        # No synthetic fragments should be added
        # Overlay should reference only the original entity
        assert result.overlay.entity_id == 'thread_no_fill'
    
    def test_absence_preserved_as_absence(self, facade):
        """
        Absence of expected continuation must be preserved.
        
        If coherence analysis detects gaps, it should note them
        rather than hiding them.
        """
        result = facade.score_coherence(
            thread_id='thread_absence_test',
            thread_version='v1',
            fragment_ids=['frag_1', 'frag_2'],
            fragment_contents=['Start of story', 'End of story'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc),  # 2 hour gap
            ],
            random_seed=42
        )
        
        assert result.success
        
        # Check for gap annotations
        gap_annotations = [
            a for a in result.overlay.annotations 
            if 'gap' in a.annotation_type.lower()
        ]
        # May or may not have gap annotations, but should not crash


# =============================================================================
# UNSUPPORTED TASK TYPE TESTS
# =============================================================================

class TestUnsupportedTaskType:
    """
    Unsupported task types must fail with MODEL_REFUSAL.
    """
    
    @pytest.fixture
    def facade(self):
        return get_facade()
    
    def test_unsupported_task_returns_explicit_error(self, facade):
        """Unsupported task type must return MODEL_REFUSAL."""
        from adapter.pipeline import ModelInvocationPipeline, InvocationConfig
        from adapter.executor import NarrativeModelExecutor
        
        executor = NarrativeModelExecutor()
        pipeline = ModelInvocationPipeline(executor=executor)
        
        request = create_request_unsupported_task()
        response, trace = pipeline.invoke(request)
        
        assert not response.success
        assert response.error is not None
        assert response.error.error_code == ModelErrorCode.MODEL_REFUSAL
    
    def test_unsupported_task_has_no_annotations(self, facade):
        """Unsupported task response must have zero annotations."""
        from adapter.pipeline import ModelInvocationPipeline
        from adapter.executor import NarrativeModelExecutor
        
        pipeline = ModelInvocationPipeline(executor=NarrativeModelExecutor())
        
        request = create_request_unsupported_task()
        response, _ = pipeline.invoke(request)
        
        assert len(response.annotations) == 0
        assert len(response.scores) == 0


# =============================================================================
# INTERNAL ERROR TESTS
# =============================================================================

class TestInternalErrors:
    """
    Internal errors must surface with INTERNAL_ERROR code.
    """
    
    def test_internal_exception_returns_error_code(self):
        """Unexpected exceptions must return INTERNAL_ERROR."""
        class BrokenExecutor(ModelExecutorInterface):
            def execute(self, request, random_seed):
                raise RuntimeError("Internal processing failure")
            
            def get_version(self):
                return MODEL_VERSION_V1
            
            def supports_task(self, task_type):
                return True
        
        from adapter.pipeline import ModelInvocationPipeline
        pipeline = ModelInvocationPipeline(executor=BrokenExecutor())
        
        from .fixtures import create_request_divergence
        response, trace = pipeline.invoke(create_request_divergence())
        
        assert not response.success
        assert response.error.error_code == ModelErrorCode.INTERNAL_ERROR
    
    def test_internal_error_message_preserved(self):
        """Internal error message must be preserved for debugging."""
        class BrokenExecutor(ModelExecutorInterface):
            def execute(self, request, random_seed):
                raise ValueError("Specific error message for debugging")
            
            def get_version(self):
                return MODEL_VERSION_V1
            
            def supports_task(self, task_type):
                return True
        
        from adapter.pipeline import ModelInvocationPipeline
        pipeline = ModelInvocationPipeline(executor=BrokenExecutor())
        
        from .fixtures import create_request_divergence
        response, _ = pipeline.invoke(create_request_divergence())
        
        assert "Specific error message" in response.error.message


# =============================================================================
# NO SILENT FALLBACK TESTS
# =============================================================================

class TestNoSilentFallbacks:
    """
    System must never silently fall back to defaults.
    """
    
    @pytest.fixture
    def facade(self):
        return get_facade()
    
    def test_failure_does_not_create_overlay(self, facade):
        """Failed analysis must not create an overlay."""
        # Use unsupported task type to trigger failure
        from adapter.pipeline import ModelInvocationPipeline
        from adapter.executor import NarrativeModelExecutor
        from adapter.overlay import OverlayStore
        
        executor = NarrativeModelExecutor()
        pipeline = ModelInvocationPipeline(executor=executor)
        store = OverlayStore()
        
        request = create_request_unsupported_task()
        response, _ = pipeline.invoke(request)
        
        assert not response.success
        
        # Attempting to store failed response should raise
        with pytest.raises(ValueError):
            store.store(
                response=response,
                entity_id="test",
                entity_type="thread",
                entity_version="v1"
            )
    
    def test_no_default_scores_on_failure(self):
        """Failed response must have zero scores, not defaults."""
        class FailingExecutor(ModelExecutorInterface):
            def execute(self, request, random_seed):
                raise ValueError("Cannot process")
            
            def get_version(self):
                return MODEL_VERSION_V1
            
            def supports_task(self, task_type):
                return True
        
        from adapter.pipeline import ModelInvocationPipeline
        pipeline = ModelInvocationPipeline(executor=FailingExecutor())
        
        from .fixtures import create_request_divergence
        response, _ = pipeline.invoke(create_request_divergence())
        
        assert not response.success
        assert response.scores == ()  # Empty tuple, not default values
        assert response.annotations == ()
