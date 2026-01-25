"""
Replay Invariant Tests

Tests for determinism: identical inputs + version = identical outputs.

AXIOM UNDER TEST:
=================
Given identical backend inputs and identical model version + hash,
outputs MUST be byte-identical.
"""

import pytest
from datetime import datetime, timezone

from adapter import get_facade
from adapter.contracts import ModelVersionInfo

from .fixtures import (
    create_request_divergence,
    create_request_contradiction,
    create_request_coherence,
    create_request_lifecycle,
    create_snapshot_standard,
    hash_response,
    MODEL_VERSION_V1,
    MODEL_VERSION_V2,
)


# =============================================================================
# DETERMINISM TESTS
# =============================================================================

class TestReplayDeterminism:
    """
    Same input + same seed + same version = identical output.
    
    This is the core invariant for replay safety.
    """
    
    @pytest.fixture
    def facade(self):
        """Create fresh facade for each test."""
        return get_facade()
    
    def test_divergence_scoring_is_deterministic(self, facade):
        """Divergence scoring must produce identical results on replay."""
        # Run 1
        result1 = facade.analyze_thread(
            thread_id='thread_replay_001',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1', 'frag_2', 'frag_3'],
            fragment_contents=['Content A', 'Content B', 'Content C'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 10, 10, tzinfo=timezone.utc),
            ],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        # Run 2 (identical inputs)
        result2 = facade.analyze_thread(
            thread_id='thread_replay_001',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1', 'frag_2', 'frag_3'],
            fragment_contents=['Content A', 'Content B', 'Content C'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 10, 10, tzinfo=timezone.utc),
            ],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        assert result1.success == result2.success
        assert result1.overlay is not None
        assert result2.overlay is not None
        
        # Compare score values (must be identical)
        scores1 = result1.overlay.scores
        scores2 = result2.overlay.scores
        
        assert len(scores1) == len(scores2)
        for s1, s2 in zip(scores1, scores2):
            assert s1.score_type == s2.score_type
            assert s1.value == s2.value
            assert s1.entity_id == s2.entity_id
    
    def test_coherence_analysis_is_deterministic(self, facade):
        """Coherence analysis must produce identical results on replay."""
        kwargs = dict(
            thread_id='thread_coherence_001',
            thread_version='v1',
            fragment_ids=['frag_1', 'frag_2'],
            fragment_contents=['First', 'Second'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc),
            ],
            random_seed=42
        )
        
        result1 = facade.score_coherence(**kwargs)
        result2 = facade.score_coherence(**kwargs)
        
        assert result1.success == result2.success
        
        # Scores must be identical
        for s1, s2 in zip(result1.overlay.scores, result2.overlay.scores):
            assert s1.value == s2.value
    
    def test_lifecycle_prediction_is_deterministic(self, facade):
        """Lifecycle prediction must produce identical results on replay."""
        kwargs = dict(
            thread_id='thread_lifecycle_001',
            thread_version='v1',
            thread_lifecycle='emerging',
            fragment_ids=['frag_1'],
            fragment_contents=['Initial content'],
            fragment_timestamps=[datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)],
            random_seed=42
        )
        
        result1 = facade.predict_lifecycle(**kwargs)
        result2 = facade.predict_lifecycle(**kwargs)
        
        assert result1.success == result2.success
        
        # Annotations must be identical
        ann1 = result1.overlay.annotations
        ann2 = result2.overlay.annotations
        
        assert len(ann1) == len(ann2)
        for a1, a2 in zip(ann1, ann2):
            assert a1.annotation_type == a2.annotation_type
            assert a1.value == a2.value
    
    def test_different_seed_may_differ(self, facade):
        """
        Different random seeds MAY produce different outputs.
        
        This is allowed but both must be traceable.
        """
        base_kwargs = dict(
            thread_id='thread_seed_test',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1', 'frag_2', 'frag_3', 'frag_4', 'frag_5'],
            fragment_contents=['A', 'B', 'C', 'D', 'E'],
            fragment_timestamps=[
                datetime(2026, 1, 1, i, 0, tzinfo=timezone.utc)
                for i in range(5)
            ],
            task_type='divergence_scoring'
        )
        
        result_seed_42 = facade.analyze_thread(**base_kwargs, random_seed=42)
        result_seed_99 = facade.analyze_thread(**base_kwargs, random_seed=99)
        
        # Both must succeed and be traceable
        assert result_seed_42.success
        assert result_seed_99.success
        assert result_seed_42.trace_id != result_seed_99.trace_id


# =============================================================================
# CROSS-TIME REPLAY TESTS
# =============================================================================

class TestCrossTimeReplay:
    """
    Replaying from a checkpoint must produce identical results.
    """
    
    @pytest.fixture
    def facade(self):
        return get_facade()
    
    def test_overlay_can_be_retrieved(self, facade):
        """Stored overlays must be retrievable for replay comparison."""
        # Create overlay
        result = facade.analyze_thread(
            thread_id='thread_overlay_001',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1', 'frag_2'],
            fragment_contents=['Content 1', 'Content 2'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc),
            ],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        assert result.success
        stored_overlay = result.overlay
        
        # Retrieve overlay
        retrieved = facade.get_latest_overlay('thread_overlay_001')
        
        assert retrieved is not None
        assert retrieved.overlay_id == stored_overlay.overlay_id
        assert retrieved.model_version == stored_overlay.model_version
    
    def test_overlay_history_preserved(self, facade):
        """Multiple overlays must be preserved in history."""
        import time
        import uuid
        thread_id = f'thread_history_{uuid.uuid4().hex[:8]}'
        
        # Create multiple overlays with small delays
        for i in range(3):
            facade.analyze_thread(
                thread_id=thread_id,
                thread_version=f'v{i+1}',
                thread_lifecycle='active',
                fragment_ids=[f'frag_{i}'],
                fragment_contents=[f'Content {i}'],
                fragment_timestamps=[datetime(2026, 1, 1, 10+i, 0, tzinfo=timezone.utc)],
                task_type='divergence_scoring',
                random_seed=42
            )
            time.sleep(0.01)  # Ensure unique timestamps
        
        # Get history
        history = facade.get_overlay_history(thread_id)
        
        assert len(history) == 3
        # All versions present
        versions = {o.entity_version for o in history}
        assert versions == {'v1', 'v2', 'v3'}


# =============================================================================
# VERSION MISMATCH TRACEABILITY TESTS
# =============================================================================

class TestVersionMismatchTraceability:
    """
    Different model versions may produce different outputs,
    but both must be traceable to their version.
    """
    
    @pytest.fixture
    def facade(self):
        return get_facade()
    
    def test_overlay_includes_model_version(self, facade):
        """Every overlay must include model version for traceability."""
        result = facade.analyze_thread(
            thread_id='thread_version_001',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1'],
            fragment_contents=['Content'],
            fragment_timestamps=[datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        assert result.success
        overlay = result.overlay
        
        # Must have version info
        assert overlay.model_version is not None
        assert overlay.model_weights_hash is not None
        assert len(overlay.model_version) > 0
        assert len(overlay.model_weights_hash) > 0
    
    def test_trace_includes_version(self, facade):
        """Every trace must include model version."""
        facade.analyze_thread(
            thread_id='thread_trace_version',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1'],
            fragment_contents=['Content'],
            fragment_timestamps=[datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        traces = facade.get_traces()
        assert len(traces) > 0
        
        latest_trace = traces[-1]
        assert latest_trace.model_version is not None
        assert latest_trace.model_version.model_version is not None
