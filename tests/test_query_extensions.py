"""
Query Extensions Tests
======================

Tests for L5 QueryEngine extensions: Similarity, Topology, Alignment.

Verifies:
1. New handlers are registered
2. Correct delegation to L3 engines
3. Error handling for missing inputs
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass, field
from typing import Tuple, Optional

from backend.query import QueryEngine, QueryType
from backend.contracts.events import (
    QueryRequest, QueryResult, ErrorCode, 
    NormalizedFragment, DuplicateInfo, DuplicateStatus,
    ContradictionInfo, ContradictionStatus, ThreadStateSnapshot, Timeline, TimelinePoint
)
from backend.contracts.base import (
    FragmentId, ThreadId, VersionId, Timestamp, TimeRange,
    FragmentRelation, FragmentRelationType
)

# Helpers for mocking
def make_id(val):
    return FragmentId(value=val, content_hash=f"hash_{val}")

def make_thread_id(val):
    return ThreadId(value=val)

class TestQueryExtensions:
    
    @pytest.fixture
    def mock_storage(self):
        storage = MagicMock()
        storage.backend = MagicMock()
        return storage

    @pytest.fixture
    def engine(self, mock_storage):
        return QueryEngine(storage=mock_storage)

    def test_handler_registration(self, engine):
        """Verify all new handlers are registered."""
        assert QueryType.SIMILARITY in engine._handlers
        assert QueryType.TOPOLOGY in engine._handlers
        assert QueryType.ALIGNMENT in engine._handlers

    def test_similarity_query(self, engine, mock_storage):
        """Verify similarity query delegates to EmbeddingService."""
        req = QueryRequest(
            query_id="q1",
            query_type=QueryType.SIMILARITY,
            fragment_id=make_id("frag_a")
        )
        
        # Mock storage returns fragments
        frag_a = MagicMock(spec=NormalizedFragment)
        frag_a.fragment_id = make_id("frag_a")
        frag_a.embedding_vector = MagicMock()
        
        frag_b = MagicMock(spec=NormalizedFragment)
        frag_b.fragment_id = make_id("frag_b")
        frag_b.embedding_vector = MagicMock()
        
        mock_storage.backend.get_fragment.side_effect = lambda fid: frag_a if fid.value == "frag_a" else frag_b
        mock_storage.backend.get_all_fragment_ids.return_value = [make_id("frag_a"), make_id("frag_b")]
        
        # Mock EmbeddingService
        with patch("backend.normalization.embedding_service.EmbeddingService") as MockService:
            service_instance = MockService.return_value
            # Mock high similarity
            score = MagicMock()
            score.value = 0.9
            service_instance.compute_similarity.return_value = score
            
            result = engine.execute(req)
            
            assert result.success
            assert result.result_count == 1
            # Check results contain (frag_b, score)
            assert result.results[0][0] == frag_b
    
    def test_topology_query(self, engine, mock_storage):
        """Verify topology query delegates to TopologyEngine."""
        req = QueryRequest(
            query_id="q2",
            query_type=QueryType.TOPOLOGY,
            thread_id=make_thread_id("t1")
        )
        
        # Mock snapshot
        snapshot = MagicMock(spec=ThreadStateSnapshot)
        snapshot.member_fragment_ids = (make_id("a"), make_id("b"))
        snapshot.relations = ()
        
        mock_storage.backend.get_latest_snapshot.return_value = snapshot
        
        # Mock TopologyEngine
        with patch("backend.core.topology.TopologyEngine") as MockTopo:
            mock_instance = MockTopo.return_value
            mock_metrics = MagicMock()
            mock_instance.compute_metrics.return_value = mock_metrics
            mock_instance.get_connected_components.return_value = [{"a", "b"}]
            
            result = engine.execute(req)
            
            assert result.success
            assert result.results[0] == (mock_metrics, [{"a", "b"}])
            mock_instance.build_graph.assert_called()

    def test_alignment_query_success(self, engine, mock_storage):
        """Verify alignment query delegates to AlignmentEngine."""
        req = QueryRequest(
            query_id="q3",
            query_type=QueryType.ALIGNMENT,
            thread_id=make_thread_id("t1"),
            comparison_thread_id=make_thread_id("t2")
        )
        
        # Mock timelines (Timeline object mocks)
        pt1 = TimelinePoint(Timestamp.now(), VersionId("v1", 1, None), "ent1", "state")
        assert pt1.timestamp is not None, "Timestamp is None!"
        assert pt1.timestamp.value is not None, "Timestamp.value is None!"
        
        timeline = Timeline(make_thread_id("t1"), (pt1,), TimeRange(None, None), 1)
            
        mock_storage.get_thread_timeline.return_value = timeline
        
        # Mock AlignmentEngine
        with patch("backend.core.alignment.TemporalAlignmentEngine") as MockAlign:
            instance = MockAlign.return_value
            mock_result = MagicMock()
            instance.compute_alignment.return_value = mock_result
            
            result = engine.execute(req)
            
            assert result.success, f"Query failed: {result.error}"
            assert result.results[0] == mock_result
            instance.compute_alignment.assert_called()

    def test_alignment_query_missing_comparison_id(self, engine):
        """Verify alignment fails without comparison_thread_id."""
        req = QueryRequest(
            query_id="q4",
            query_type=QueryType.ALIGNMENT,
            thread_id=make_thread_id("t1"),
            comparison_thread_id=None # Missing
        )
        
        result = engine.execute(req)
        assert not result.success
        assert result.error.error_code == ErrorCode.INSUFFICIENT_DATA
