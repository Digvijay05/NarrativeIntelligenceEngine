"""
Temporal Alignment Engine Tests
===============================

Tests for the temporal alignment engine (DTW).

ML FENCE POST VERIFICATION:
===========================
These tests verify that the alignment engine:
1. Correctly aligns temporally shifted signals (time warping)
2. Computes geometric distance only
3. Does NOT judge completeness or authority
4. Gracefully degrades if tslearn missing
"""

import pytest
import numpy as np
from unittest.mock import patch

from backend.core.alignment import TemporalAlignmentEngine, AlignmentResult

class TestTemporalAlignmentEngine:
    
    def test_alignment_identical_signals(self):
        """Identical signals should have zero distance and diagonal path."""
        engine = TemporalAlignmentEngine()
        if not engine.is_available():
            pytest.skip("tslearn not available")
            
        signal = [0.0, 1.0, 2.0, 1.0, 0.0]
        result = engine.compute_alignment(signal, signal)
        
        assert result.is_valid
        assert result.distance == 0.0
        # Path should be diagonal (0,0), (1,1)...
        for i in range(len(signal)):
            assert (i, i) in result.path

    def test_alignment_shifted_signals(self):
        """
        DTW should recognize same shape with temporal shift.
        
        Signal A: 0, 1, 0
        Signal B: 0, 0, 1, 0 (delayed start)
        
        Distance should be small (shape matched), unlike Euclidean distance.
        """
        engine = TemporalAlignmentEngine()
        if not engine.is_available():
            pytest.skip("tslearn not available")
            
        sig_a = [0.0, 1.0, 0.0]
        sig_b = [0.0, 0.0, 1.0, 0.0]
        
        result = engine.compute_alignment(sig_a, sig_b)
        
        assert result.is_valid
        assert result.distance < 1.0  # Should be very close to 0 if aligned well
        
        # Verify alignment path maps the peak (index 1 in A to index 2 in B)
        # Note: DTW path is list of (i, j)
        path_dict = dict(result.path) # Maps index in A to index in B (if 1-to-1)
        # Since one index in A can map to multiple in B, we search properties
        
        # Check that peak of A (index 1) maps to peak of B (index 2)
        # The path works backwards often or contains ranges, just checking existence
        assert (1, 2) in result.path

    def test_distance_metric(self):
        """Verify distance computation works independently."""
        engine = TemporalAlignmentEngine()
        if not engine.is_available():
            pytest.skip("tslearn not available")
            
        sig_a = [0.0, 1.0]
        sig_b = [0.0, 2.0]
        
        # Euclidean-ish distance expected
        dist = engine.compute_distance(sig_a, sig_b)
        assert dist > 0.0

    def test_fence_post_no_ranking(self):
        """
        ML FENCE POST: API must not expose ranking or judgment.
        
        The result contains only distance and path, no 'score' or 'confidence'
        that implies truth value.
        """
        engine = TemporalAlignmentEngine()
        
        result = engine.compute_alignment([0, 1], [0, 1])
        
        assert hasattr(result, "distance")
        assert hasattr(result, "path")
        assert not hasattr(result, "completeness_score")
        assert not hasattr(result, "authority_score")
        assert not hasattr(result, "better_timeline")

    def test_graceful_degradation(self):
        """Should handle missing library gracefully."""
        # Force availability to False
        engine = TemporalAlignmentEngine()
        engine._available = False
        
        result = engine.compute_alignment([0, 1], [0, 1])
        assert not result.is_valid
        assert "not available" in result.error_message
        
        dist = engine.compute_distance([0, 1], [0, 1])
        assert dist == -1.0
