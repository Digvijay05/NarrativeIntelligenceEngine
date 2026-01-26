"""
Topology Integration Tests
==========================

Tests for the integration of TopologyEngine into NarrativeStateEngine.

Verifies:
1. NarrativeStateEngine uses TopologyEngine
2. Structural divergence (graph splits) triggers DIVERGENCE_DETECTED
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from backend.core import NarrativeStateEngine, ThreadProcessingResult
from backend.contracts.events import (
    NormalizedFragment, DuplicateInfo, DuplicateStatus,
    ContradictionInfo, ContradictionStatus, ThreadStateSnapshot
)
from backend.contracts.base import (
    FragmentId, ThreadLifecycleState, Timestamp, ContentSignature,
    SourceMetadata, SourceId
)

def create_fragment(id_val: str, payload="test") -> NormalizedFragment:
    """Helper to create a basic fragment."""
    return NormalizedFragment(
        fragment_id=FragmentId(value=id_val, content_hash=f"hash_{id_val}"),
        source_event_id="evt_1",
        content_signature=ContentSignature(
            payload_hash=f"hash_{id_val}",
            payload_length=len(payload),
            detected_language="en"
        ),
        normalized_payload=payload,
        detected_language="en",
        canonical_topics=(),
        canonical_entities=(),
        duplicate_info=DuplicateInfo(status=DuplicateStatus.UNIQUE),
        contradiction_info=ContradictionInfo(status=ContradictionStatus.NO_CONTRADICTION),
        normalization_timestamp=Timestamp.now(),
        source_metadata=SourceMetadata(
            source_id=SourceId(value="test_src", source_type="mock"),
            source_confidence=1.0,
            capture_timestamp=Timestamp.now(),
            event_timestamp=None
        )
    )

class TestTopologyIntegration:
    
    def test_structural_divergence_detection(self):
        """
        Verify that if the topology engine detects a split, 
        the narrative engine returns DIVERGENCE_DETECTED.
        """
        # Initialize engine
        engine = NarrativeStateEngine()
        
        # 1. Create a thread with fragment A
        frag_a = create_fragment("frag_A")
        result_a = engine.process_fragment(frag_a)
        thread_id = result_a.thread_id
        
        assert result_a.result == ThreadProcessingResult.NEW_THREAD_CREATED
        
        # 2. Add fragment B (connected to A via logic, e.g. same topic/time)
        # For this test, we mock the ThreadMatcher to force it into the same thread
        # so we can test the topology check logic
        frag_b = create_fragment("frag_B")
        
        # Mock thread matcher to return our thread
        with patch.object(engine._thread_matcher, 'find_matching_thread', return_value=thread_id):
            # Also mock topology engine to simulate a split
            # We simulate that adding B results in 2 disjoint components [A] and [B]
            # (i.e. no relation exists between them despite being in same thread object)
            with patch.object(engine._topology_engine, 'detect_structural_divergence', return_value=[{"A"}, {"B"}]):
                
                result_b = engine.process_fragment(frag_b)
                
                # Should detect divergence
                assert result_b.result == ThreadProcessingResult.DIVERGENCE_DETECTED
                assert result_b.state_event.event_type == "divergence_detected"
                assert "Structural divergence" in result_b.state_event.new_state_snapshot.divergence_reason

    def test_no_divergence_when_connected(self):
        """
        Verify that perfectly connected graph does NOT trigger divergence.
        """
        engine = NarrativeStateEngine()
        
        frag_a = create_fragment("frag_A")
        result_a = engine.process_fragment(frag_a)
        thread_id = result_a.thread_id
        
        frag_b = create_fragment("frag_B")
        
        with patch.object(engine._thread_matcher, 'find_matching_thread', return_value=thread_id):
            # Mock topology to return empty list (no divergence/splits)
            with patch.object(engine._topology_engine, 'detect_structural_divergence', return_value=[]):
                
                result_b = engine.process_fragment(frag_b)
                
                # Should be added normally
                assert result_b.result == ThreadProcessingResult.ADDED_TO_EXISTING
                assert result_b.state_event.event_type == "thread_updated"
