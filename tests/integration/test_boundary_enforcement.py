"""
Boundary Enforcement Tests

Tests that model cannot mutate backend state and
backend treats model output as advisory only.

AXIOM UNDER TEST:
=================
One-way authority: Backend state is canonical.
Model output is advisory only.
"""

import pytest
from datetime import datetime, timezone

from adapter import get_facade
from adapter.overlay import ModelOverlay, OverlayStore


# =============================================================================
# MODEL CANNOT MUTATE BACKEND STATE
# =============================================================================

class TestModelCannotMutateBackend:
    """
    Model output must never mutate backend state.
    All outputs are overlays.
    """
    
    @pytest.fixture
    def facade(self):
        return get_facade()
    
    def test_overlay_is_separate_from_entity(self, facade):
        """Overlay must not be part of the entity it describes."""
        result = facade.analyze_thread(
            thread_id='thread_boundary_001',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1'],
            fragment_contents=['Content'],
            fragment_timestamps=[datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        overlay = result.overlay
        
        # Overlay references entity but is not the entity
        assert overlay.entity_id == 'thread_boundary_001'
        assert overlay.entity_type == 'thread'
        
        # Overlay has its own ID
        assert overlay.overlay_id != overlay.entity_id
        assert overlay.overlay_id.startswith('overlay_')
    
    def test_overlay_preserves_entity_version(self, facade):
        """Overlay must preserve the entity version it analyzed."""
        result = facade.analyze_thread(
            thread_id='thread_version_preserve',
            thread_version='v42',
            thread_lifecycle='active',
            fragment_ids=['frag_1'],
            fragment_contents=['Content'],
            fragment_timestamps=[datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        assert result.overlay.entity_version == 'v42'
    
    def test_multiple_overlays_dont_conflict(self, facade):
        """Multiple overlays on same entity must co-exist."""
        import time
        thread_id = 'thread_multi_overlay'
        
        # Create first overlay
        result1 = facade.analyze_thread(
            thread_id=thread_id,
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1'],
            fragment_contents=['Initial content'],
            fragment_timestamps=[datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        # Small delay to ensure different timestamps
        time.sleep(0.01)
        
        # Create second overlay (different analysis)
        result2 = facade.analyze_thread(
            thread_id=thread_id,
            thread_version='v2',
            thread_lifecycle='active',
            fragment_ids=['frag_1', 'frag_2'],
            fragment_contents=['Initial', 'Updated'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 11, 0, tzinfo=timezone.utc),
            ],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        # Both overlays exist
        history = facade.get_overlay_history(thread_id)
        assert len(history) >= 2
        
        # They have different IDs (due to different invocation timestamps)
        assert result1.overlay.overlay_id != result2.overlay.overlay_id


# =============================================================================
# OVERLAY STRUCTURE TESTS
# =============================================================================

class TestOverlayStructure:
    """
    Overlays must have the correct structure for advisory use.
    """
    
    @pytest.fixture
    def facade(self):
        return get_facade()
    
    def test_overlay_contains_model_metadata(self, facade):
        """Overlay must contain model version and invocation info."""
        result = facade.analyze_thread(
            thread_id='thread_metadata',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1'],
            fragment_contents=['Content'],
            fragment_timestamps=[datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        overlay = result.overlay
        
        # Must have model metadata
        assert overlay.model_version is not None
        assert overlay.model_weights_hash is not None
        assert overlay.invocation_id is not None
    
    def test_scores_have_uncertainty(self, facade):
        """All scores must include uncertainty ranges."""
        result = facade.analyze_thread(
            thread_id='thread_uncertainty',
            thread_version='v1',
            thread_lifecycle='active',
            fragment_ids=['frag_1', 'frag_2'],
            fragment_contents=['First', 'Second'],
            fragment_timestamps=[
                datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
                datetime(2026, 1, 1, 10, 5, tzinfo=timezone.utc),
            ],
            task_type='divergence_scoring',
            random_seed=42
        )
        
        for score in result.overlay.scores:
            assert score.uncertainty is not None
            assert score.uncertainty.lower <= score.value <= score.uncertainty.upper
            assert score.uncertainty.confidence_level > 0
    
    def test_annotations_have_confidence(self, facade):
        """All annotations must include confidence scores."""
        result = facade.predict_lifecycle(
            thread_id='thread_ann_conf',
            thread_version='v1',
            thread_lifecycle='emerging',
            fragment_ids=['frag_1'],
            fragment_contents=['Content'],
            fragment_timestamps=[datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc)],
            random_seed=42
        )
        
        for ann in result.overlay.annotations:
            assert 0.0 <= ann.confidence <= 1.0


# =============================================================================
# OVERLAY SUPERSESSION TESTS  
# =============================================================================

class TestOverlaySupersession:
    """
    New overlays may supersede old ones but must not delete them.
    """
    
    def test_supersedes_preserves_old_overlay(self):
        """New overlay must reference but not delete superseded overlay."""
        store = OverlayStore()
        
        from adapter.contracts import (
            ModelAnalysisResponse, InvocationMetadata, ModelVersionInfo
        )
        from datetime import datetime
        
        version = ModelVersionInfo(
            model_id="test",
            model_version="1.0.0",
            weights_hash="abc123",
            config_hash="def456",
            created_at=datetime.utcnow()
        )
        
        invocation = InvocationMetadata.create(
            model_version=version,
            input_data="test",
            random_seed=42
        )
        
        response1 = ModelAnalysisResponse.success_response(
            request_id="req1",
            invocation=invocation,
            annotations=(),
            scores=(),
            processing_time_ms=10.0
        )
        
        response2 = ModelAnalysisResponse.success_response(
            request_id="req2",
            invocation=invocation,
            annotations=(),
            scores=(),
            processing_time_ms=10.0
        )
        
        # Store first overlay
        overlay1 = store.store(
            response=response1,
            entity_id="test_entity",
            entity_type="thread",
            entity_version="v1"
        )
        
        # Store second overlay (supersedes first)
        overlay2 = store.store(
            response=response2,
            entity_id="test_entity",
            entity_type="thread",
            entity_version="v2"
        )
        
        # Second overlay references first
        assert overlay2.supersedes_overlay_id == overlay1.overlay_id
        
        # First overlay still retrievable
        history = store.get_history("test_entity")
        overlay_ids = [o.overlay_id for o in history]
        assert overlay1.overlay_id in overlay_ids
        assert overlay2.overlay_id in overlay_ids
