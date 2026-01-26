#!/usr/bin/env python3
"""
ML Phase 1 Validation - Embedding Integration
==============================================

Validates that:
1. Embeddings are computed as coordinate transforms
2. Similarity scores are returned WITHOUT thresholds
3. Graceful degradation when model unavailable
4. All fence posts are respected

RUN:
    python tools/validate_embeddings.py
"""

from __future__ import annotations
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.contracts.base import SourceId
from backend.contracts.events import (
    RawIngestionEvent, EmbeddingVector, SimilarityScore
)
from backend.normalization import NormalizationEngine, NormalizationConfig


def test_embedding_contracts():
    """Test that embedding contracts work correctly."""
    print("\n[1] Testing EmbeddingVector contract...")
    
    # Create an embedding vector
    vec = EmbeddingVector.from_list(
        values=[0.1, 0.2, 0.3, 0.4, 0.5],
        model_id="test-model",
        model_version="1.0.0"
    )
    
    assert vec.dimension == 5, "Dimension should be 5"
    assert vec.model_id == "test-model", "Model ID should match"
    assert len(vec.to_list()) == 5, "to_list should return 5 elements"
    
    # Test immutability
    try:
        vec.values = (0.0,)
        print("   FAIL: EmbeddingVector should be immutable")
        return False
    except (AttributeError, TypeError):
        print("   PASS: EmbeddingVector is immutable")
    
    return True


def test_similarity_score_no_threshold():
    """Test that SimilarityScore has no threshold decisions."""
    print("\n[2] Testing SimilarityScore contract...")
    
    score = SimilarityScore(
        value=0.87654321,
        metric="cosine",
        threshold_applied=False
    )
    
    # Verify no threshold is applied
    assert score.threshold_applied == False, "threshold_applied should be False"
    assert score.value == 0.87654321, "Raw value should be preserved"
    
    print("   PASS: SimilarityScore preserves raw value without threshold")
    return True


def test_graceful_degradation():
    """Test that normalization works without embeddings."""
    print("\n[3] Testing graceful degradation...")
    
    # Create engine WITHOUT embeddings
    config = NormalizationConfig(enable_embeddings=False)
    engine = NormalizationEngine(config)
    
    # Create a test event
    source_id = SourceId(value="test_source", source_type="test")
    event = RawIngestionEvent.create(
        source_id=source_id,
        raw_payload='{"payload": "Test content for normalization without ML"}'
    )
    
    # Normalize
    result = engine.normalize(event)
    
    assert result.success, "Normalization should succeed"
    assert result.fragment is not None, "Fragment should be created"
    assert result.fragment.embedding_vector is None, "Embedding should be None when disabled"
    assert result.fragment.nearest_similarity is None, "Similarity should be None when disabled"
    
    print("   PASS: Graceful degradation works")
    return True


def test_embedding_integration():
    """Test that embeddings are computed when enabled."""
    print("\n[4] Testing embedding integration...")
    
    # Create engine WITH embeddings
    config = NormalizationConfig(
        enable_embeddings=True,
        embedding_model_id="all-MiniLM-L6-v2"
    )
    engine = NormalizationEngine(config)
    
    # Check if embedding service is available
    if engine._embedding_service is None:
        print("   SKIP: Embedding model not available (install sentence-transformers)")
        return True  # Not a failure, just a skip
    
    # Create test events
    source_id = SourceId(value="test_source", source_type="test")
    
    event1 = RawIngestionEvent.create(
        source_id=source_id,
        raw_payload='{"payload": "The government announced a new climate policy today."}'
    )
    
    event2 = RawIngestionEvent.create(
        source_id=source_id,
        raw_payload='{"payload": "Climate policy was announced by government officials."}'
    )
    
    event3 = RawIngestionEvent.create(
        source_id=source_id,
        raw_payload='{"payload": "The stock market reached new highs in trading today."}'
    )
    
    # Normalize first event
    result1 = engine.normalize(event1)
    assert result1.success, "First normalization should succeed"
    assert result1.fragment.embedding_vector is not None, "First fragment should have embedding"
    
    print(f"   Fragment 1: embedding dim = {result1.fragment.embedding_vector.dimension}")
    
    # Normalize second event (similar content)
    result2 = engine.normalize(event2)
    assert result2.success, "Second normalization should succeed"
    assert result2.fragment.embedding_vector is not None, "Second fragment should have embedding"
    assert result2.fragment.nearest_similarity is not None, "Should have nearest similarity"
    
    similarity_to_first = result2.fragment.nearest_similarity.value
    print(f"   Fragment 2: similarity to Fragment 1 = {similarity_to_first:.4f}")
    
    # Verify NO THRESHOLD is applied
    assert result2.fragment.nearest_similarity.threshold_applied == False, \
        "No threshold should be applied"
    
    # Normalize third event (different content)
    result3 = engine.normalize(event3)
    assert result3.success, "Third normalization should succeed"
    
    if result3.fragment.nearest_similarity is not None:
        print(f"   Fragment 3: similarity to nearest = {result3.fragment.nearest_similarity.value:.4f}")
    
    print("   PASS: Embedding integration works correctly")
    return True


def test_fence_post_compliance():
    """Verify ML fence posts are respected."""
    print("\n[5] Testing ML fence post compliance...")
    
    # 1. Verify EmbeddingVector doesn't contain interpretation
    vec = EmbeddingVector.from_list([0.1, 0.2], "test", "1.0")
    
    # The vector should ONLY contain raw values, no "semantic meaning"
    assert not hasattr(vec, 'meaning'), "EmbeddingVector should not have 'meaning'"
    assert not hasattr(vec, 'topics'), "EmbeddingVector should not have 'topics'"
    assert not hasattr(vec, 'sentiment'), "EmbeddingVector should not have 'sentiment'"
    
    # 2. Verify SimilarityScore doesn't contain decisions
    score = SimilarityScore(value=0.5, metric="cosine")
    
    assert not hasattr(score, 'is_similar'), "SimilarityScore should not have 'is_similar'"
    assert not hasattr(score, 'is_duplicate'), "SimilarityScore should not have 'is_duplicate'"
    assert not hasattr(score, 'verdict'), "SimilarityScore should not have 'verdict'"
    
    print("   PASS: All ML fence posts are respected")
    return True


def main():
    print("=" * 70)
    print("ML PHASE 1 VALIDATION - EMBEDDING INTEGRATION")
    print("=" * 70)
    
    tests = [
        ("Embedding Contracts", test_embedding_contracts),
        ("Similarity No Threshold", test_similarity_score_no_threshold),
        ("Graceful Degradation", test_graceful_degradation),
        ("Embedding Integration", test_embedding_integration),
        ("Fence Post Compliance", test_fence_post_compliance),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_fn in tests:
        try:
            if test_fn():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   ERROR: {str(e)}")
            failed += 1
    
    print("\n" + "-" * 70)
    print(f"RESULTS: {passed}/{len(tests)} tests passed")
    
    if failed == 0:
        print("\n✓ All ML Phase 1 validations PASSED")
    else:
        print(f"\n✗ {failed} tests FAILED")
    
    print("=" * 70 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
