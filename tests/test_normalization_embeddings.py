"""
Normalization Integration Tests (Embeddings)
============================================

Integration tests for the normalization layer with ML embeddings enabled.

ML FENCE POST VERIFICATION:
===========================
These tests verify that the normalization engine:
1. Correctly integrates the embedding service
2. Adds embedding vectors to NormalizedFragment (immutable contract)
3. Tracks nearest neighbors without making decisions
4. Logs embedding metadata to audit trail
"""

import pytest
import json
import time
from unittest.mock import Mock, patch, MagicMock

from backend.normalization import NormalizationEngine, NormalizationConfig
from backend.contracts.events import RawIngestionEvent, NormalizedFragment, EmbeddingVector
from backend.contracts.base import SourceId, Timestamp, SourceTier

# Mock data for testing
MOCK_PAYLOAD = """
Climate change is accelerating due to carbon emissions. 
Global temperatures are rising at an unprecedented rate.
"""

MOCK_PAYLOAD_2 = """
Greenhouse gases from fossil fuels contribute to global warming.
Environmental policy reform is needed immediately.
"""

MOCK_PAYLOAD_UNRELATED = """
The stock market closed higher today led by tech shares.
Investors remain optimistic about quarterly earnings.
"""


def create_raw_event(payload: str) -> RawIngestionEvent:
    """Helper to create a raw event."""
    return RawIngestionEvent.create(
        source_id=SourceId(value="test_source", source_type="mock"),
        raw_payload=payload
    )


class TestNormalizationWithEmbeddings:
    """Test normalization engine with embeddings enabled."""
    
    def test_normalize_with_embeddings_enabled(self):
        """Standard normalization should produce embedding vector when enabled."""
        config = NormalizationConfig(enable_embeddings=True)
        engine = NormalizationEngine(config)
        
        # Skip if model not available
        if engine._embedding_service is None or not engine._embedding_service.is_available():
            pytest.skip("sentence-transformers not available")
            
        event = create_raw_event(MOCK_PAYLOAD)
        result = engine.normalize(event)
        
        assert result.success
        assert result.fragment is not None
        
        # Verify embedding presence
        fragment = result.fragment
        assert fragment.embedding_vector is not None
        assert isinstance(fragment.embedding_vector, EmbeddingVector)
        assert fragment.embedding_vector.dimension > 0
        
        # Verify model metadata tracking
        assert fragment.embedding_vector.model_id == config.embedding_model_id

    def test_normalize_with_embeddings_disabled(self):
        """Normalization should NOT produce embedding vector when disabled."""
        config = NormalizationConfig(enable_embeddings=False)
        engine = NormalizationEngine(config)
        
        event = create_raw_event(MOCK_PAYLOAD)
        result = engine.normalize(event)
        
        assert result.success
        assert result.fragment is not None
        
        # Verify embedding absence
        assert result.fragment.embedding_vector is None

    def test_nearest_neighbor_tracking(self):
        """Second fragment should track nearest neighbor (the first one)."""
        config = NormalizationConfig(enable_embeddings=True)
        engine = NormalizationEngine(config)
        
        if engine._embedding_service is None or not engine._embedding_service.is_available():
            pytest.skip("sentence-transformers not available")
            
        # Process first fragment
        event1 = create_raw_event(MOCK_PAYLOAD)
        result1 = engine.normalize(event1)
        assert result1.success
        frag1_id = result1.fragment.fragment_id
        
        # Process second fragment (similar topic)
        event2 = create_raw_event(MOCK_PAYLOAD_2)
        result2 = engine.normalize(event2)
        assert result2.success
        
        # Verify neighbor tracking
        frag2 = result2.fragment
        assert frag2.nearest_fragment_id.value == frag1_id.value
        assert frag2.nearest_similarity is not None
        
        # Verify raw score is captured
        assert abs(frag2.nearest_similarity.value) <= 1.0
        assert frag2.nearest_similarity.threshold_applied is False

    def test_embedding_index_population(self):
        """Embedding index should grow as fragments are processed."""
        config = NormalizationConfig(enable_embeddings=True)
        engine = NormalizationEngine(config)
        
        if engine._embedding_service is None or not engine._embedding_service.is_available():
            pytest.skip("sentence-transformers not available")
            
        initial_size = engine._embedding_service.get_index_size()
        
        # Process fragments
        engine.normalize(create_raw_event(MOCK_PAYLOAD))
        engine.normalize(create_raw_event(MOCK_PAYLOAD_2))
        
        final_size = engine._embedding_service.get_index_size()
        
        # Should have added 2 embeddings (assuming they are unique)
        assert final_size == initial_size + 2

    def test_audit_logging_includes_embedding_metadata(self):
        """Audit logs should capture embedding dimensions and decisions."""
        config = NormalizationConfig(enable_embeddings=True)
        engine = NormalizationEngine(config)
        
        if engine._embedding_service is None or not engine._embedding_service.is_available():
            pytest.skip("sentence-transformers not available")
            
        engine.normalize(create_raw_event(MOCK_PAYLOAD))
        
        # Check audit log
        logs = engine.get_audit_log()
        normalization_log = [l for l in logs if l.action == "fragment_normalized"][-1]
        
        # Verify metadata keys
        metadata = dict(normalization_log.metadata)
        assert "has_embedding" in metadata
        assert metadata["has_embedding"] == "true"
        assert "embedding_dim" in metadata


class TestGracefulDegradationIntegration:
    """Test system behavior when ML components fail."""
    
    def test_continues_without_ml_when_model_fails(self):
        """Engine continues to work (just without embeddings) if model fails."""
        
        # Mock init failure
        with patch('backend.normalization.NormalizationEngine._init_embedding_service') as mock_init:
            mock_init.side_effect = ImportError("Simulated dependency missing")
            
            config = NormalizationConfig(enable_embeddings=True)
            engine = NormalizationEngine(config)
            
            # Should have handled error and set service to None
            assert engine._embedding_service is None
            
            # Should still normalize correctly
            event = create_raw_event(MOCK_PAYLOAD)
            result = engine.normalize(event)
            
            assert result.success
            assert result.fragment.embedding_vector is None
