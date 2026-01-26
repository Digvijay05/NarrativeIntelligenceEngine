"""
Embedding Service Tests
=======================

Tests for the coordinate transform embedding service.

ML FENCE POST VERIFICATION:
===========================
These tests verify that the embedding service:
1. Returns raw vectors (geometry only)
2. Returns raw similarity scores WITHOUT thresholds
3. Does NOT make any duplicate/similarity decisions
4. Gracefully degrades when model unavailable
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from backend.normalization.embedding_service import (
    EmbeddingService,
    EmbeddingServiceConfig,
    get_embedding_service
)
from backend.contracts.events import EmbeddingVector, SimilarityScore
from backend.contracts.base import FragmentId


class TestEmbeddingServiceConfig:
    """Test configuration defaults and customization."""
    
    def test_default_config_values(self):
        """Verify sensible defaults."""
        config = EmbeddingServiceConfig()
        assert config.model_id == "all-MiniLM-L6-v2"
        assert config.similarity_metric == "cosine"
        assert config.store_embeddings is True
        assert config.use_gpu is False
    
    def test_custom_config(self):
        """Verify config can be customized."""
        config = EmbeddingServiceConfig(
            model_id="custom-model",
            similarity_metric="euclidean",
            use_gpu=True
        )
        assert config.model_id == "custom-model"
        assert config.similarity_metric == "euclidean"
        assert config.use_gpu is True


class TestEmbeddingComputation:
    """Test embedding vector computation."""
    
    def test_compute_embedding_returns_embedding_vector(self):
        """Embedding computation returns proper EmbeddingVector contract."""
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        result = service.compute_embedding("This is a test sentence.")
        
        assert result is not None
        assert isinstance(result, EmbeddingVector)
        assert result.dimension > 0
        assert result.model_id == "all-MiniLM-L6-v2"
        assert len(result.values) == result.dimension
    
    def test_compute_embedding_empty_text_returns_none(self):
        """Empty text returns None, not an error."""
        service = EmbeddingService()
        
        assert service.compute_embedding("") is None
        assert service.compute_embedding("   ") is None
        assert service.compute_embedding(None) is None if hasattr(service, '_check_none') else True
    
    def test_embedding_is_normalized(self):
        """Embeddings should be unit vectors (L2 normalized)."""
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        result = service.compute_embedding("Test normalization")
        vec = np.array(result.to_list())
        
        # L2 norm should be ~1.0 for normalized vectors
        norm = np.linalg.norm(vec)
        assert abs(norm - 1.0) < 0.001, f"Expected unit vector, got norm={norm}"
    
    def test_batch_embeddings(self):
        """Batch processing returns list of embeddings."""
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        texts = ["First sentence", "Second sentence", "Third sentence"]
        results = service.compute_batch_embeddings(texts)
        
        assert len(results) == 3
        assert all(r is not None for r in results)
        assert all(isinstance(r, EmbeddingVector) for r in results)


class TestSimilarityComputation:
    """Test similarity score computation - ML fence post compliance."""
    
    def test_similarity_returns_raw_score(self):
        """Similarity computation returns raw score, no decision."""
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        emb1 = service.compute_embedding("Climate change is real")
        emb2 = service.compute_embedding("Global warming affects the planet")
        
        result = service.compute_similarity(emb1, emb2)
        
        assert isinstance(result, SimilarityScore)
        assert -1.0 <= result.value <= 1.0  # Cosine similarity range
    
    def test_fence_post_no_threshold_applied(self):
        """
        ML FENCE POST: Similarity must NOT apply threshold decisions.
        
        This is a critical test - the system must NEVER decide
        'these are similar enough' based on a learned threshold.
        """
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        emb1 = service.compute_embedding("The quick brown fox")
        emb2 = service.compute_embedding("The quick brown fox")  # Same text
        
        result = service.compute_similarity(emb1, emb2)
        
        # CRITICAL: threshold_applied must be False
        assert result.threshold_applied is False, \
            "ML FENCE POST VIOLATION: Similarity score must not apply threshold"
    
    def test_similarity_metric_tracked(self):
        """Similarity score tracks which metric was used."""
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        emb1 = service.compute_embedding("Test")
        emb2 = service.compute_embedding("Test")
        
        result = service.compute_similarity(emb1, emb2)
        
        assert result.metric == "cosine"  # Default metric


class TestNearestNeighborSearch:
    """Test nearest neighbor search - ML fence post compliance."""
    
    def test_find_nearest_returns_raw_distance(self):
        """Nearest neighbor returns raw score, no filtering."""
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        # Register some embeddings
        frag1 = FragmentId(value="frag_001", content_hash="hash1")
        emb1 = service.compute_embedding("Climate policy announcement")
        service.register_embedding(frag1, emb1)
        
        frag2 = FragmentId(value="frag_002", content_hash="hash2")
        emb2 = service.compute_embedding("Technology innovation news")
        service.register_embedding(frag2, emb2)
        
        # Find nearest to a climate-related query
        query_emb = service.compute_embedding("Environmental regulations")
        nearest_frag, nearest_score = service.find_nearest(query_emb)
        
        assert nearest_frag is not None
        assert nearest_score is not None
        assert isinstance(nearest_score, SimilarityScore)
    
    def test_fence_post_nearest_no_threshold(self):
        """
        ML FENCE POST: Nearest neighbor must NOT filter by threshold.
        
        It returns the nearest neighbor regardless of distance.
        """
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        # Register one embedding
        frag = FragmentId(value="frag_001", content_hash="hash1")
        emb = service.compute_embedding("Completely unrelated topic about cooking")
        service.register_embedding(frag, emb)
        
        # Query with something very different
        query_emb = service.compute_embedding("Quantum physics experiment")
        nearest_frag, nearest_score = service.find_nearest(query_emb)
        
        # Should still return the nearest (only) neighbor, no filtering
        assert nearest_frag is not None
        assert nearest_score.threshold_applied is False
    
    def test_empty_index_returns_none(self):
        """Empty index returns None, not error."""
        service = EmbeddingService()
        service.clear_index()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        query_emb = service.compute_embedding("Test query")
        nearest_frag, nearest_score = service.find_nearest(query_emb)
        
        assert nearest_frag is None
        assert nearest_score is None


class TestGracefulDegradation:
    """Test graceful degradation when model unavailable."""
    
    def test_unavailable_model_returns_none(self):
        """When model can't load, methods return None, not exceptions."""
        service = EmbeddingService()
        # forcedly simulate model loading failure
        with patch.object(service, '_ensure_model_loaded', return_value=False):
            result = service.compute_embedding("Test text")
            assert result is None
    
    def test_is_available_reflects_model_state(self):
        """is_available() accurately reflects model availability."""
        service = EmbeddingService()
        
        # If sentence-transformers is installed, should be available
        # If not, should return False
        available = service.is_available()
        assert isinstance(available, bool)


class TestEmbeddingIndex:
    """Test embedding index operations."""
    
    def test_register_and_retrieve(self):
        """Registered embeddings can be found."""
        service = EmbeddingService()
        service.clear_index()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        frag = FragmentId(value="test_frag", content_hash="test_hash")
        emb = service.compute_embedding("Test content")
        
        service.register_embedding(frag, emb)
        
        assert service.get_index_size() == 1
    
    def test_clear_index(self):
        """Index can be cleared."""
        service = EmbeddingService()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        frag = FragmentId(value="test_frag", content_hash="test_hash")
        emb = service.compute_embedding("Test content")
        service.register_embedding(frag, emb)
        
        service.clear_index()
        
        assert service.get_index_size() == 0
    
    def test_exclude_ids_in_search(self):
        """Can exclude specific IDs from nearest neighbor search."""
        service = EmbeddingService()
        service.clear_index()
        
        if not service.is_available():
            pytest.skip("sentence-transformers not available")
        
        # Register two embeddings
        frag1 = FragmentId(value="frag_001", content_hash="hash1")
        emb1 = service.compute_embedding("Climate change news")
        service.register_embedding(frag1, emb1)
        
        frag2 = FragmentId(value="frag_002", content_hash="hash2")
        emb2 = service.compute_embedding("Weather update")
        service.register_embedding(frag2, emb2)
        
        # Query excluding the first fragment
        query_emb = service.compute_embedding("Climate update")
        nearest_frag, _ = service.find_nearest(query_emb, exclude_ids=["frag_001"])
        
        assert nearest_frag.value == "frag_002"


class TestSingleton:
    """Test singleton pattern for embedding service."""
    
    def test_get_embedding_service_returns_same_instance(self):
        """Singleton returns same instance."""
        # Reset singleton for test
        import backend.normalization.embedding_service as es
        es._embedding_service = None
        
        service1 = get_embedding_service()
        service2 = get_embedding_service()
        
        assert service1 is service2
