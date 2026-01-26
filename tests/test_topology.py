"""
Topology Engine Tests
=====================

Tests for the graph topology engine.

ML FENCE POST VERIFICATION:
===========================
These tests verify that the topology engine:
1. correctly builds graphs from fragments and relations
2. Identifies connected components (structural clustering)
3. Computes only geometric metrics (density, diameter)
4. Does NOT expose any ranking or centrality metrics
"""

import pytest
import networkx as nx
from datetime import datetime

from backend.core.topology import TopologyEngine, GraphMetrics
from backend.contracts.base import FragmentId, Timestamp
from backend.contracts.events import FragmentRelation, FragmentRelationType

def create_fragment_id(id_val: str) -> FragmentId:
    return FragmentId(value=id_val, content_hash=f"hash_{id_val}")

def create_relation(source: str, target: str) -> FragmentRelation:
    return FragmentRelation(
        source_fragment_id=create_fragment_id(source),
        target_fragment_id=create_fragment_id(target),
        relation_type=FragmentRelationType.CONTINUATION,
        confidence=1.0,
        detected_at=Timestamp.now()
    )

class TestTopologyEngine:
    
    def test_build_graph_correctness(self):
        """Graph should accurately reflect nodes and edges."""
        engine = TopologyEngine()
        
        fragments = (
            create_fragment_id("A"),
            create_fragment_id("B"),
            create_fragment_id("C")
        )
        
        relations = (
            create_relation("A", "B"),
            create_relation("B", "C")
        )
        
        engine.build_graph(fragments, relations)
        
        metrics = engine.compute_metrics()
        assert metrics.node_count == 3
        assert metrics.edge_count == 2
        assert metrics.is_connected is True
        
    def test_connected_components(self):
        """Disjoint subgraphs should be identified as separate components."""
        engine = TopologyEngine()
        
        fragments = (
            create_fragment_id("A"),
            create_fragment_id("B"),
            create_fragment_id("X"),
            create_fragment_id("Y")
        )
        
        # Two separate chains: A-B and X-Y
        relations = (
            create_relation("A", "B"),
            create_relation("X", "Y")
        )
        
        engine.build_graph(fragments, relations)
        
        components = engine.get_connected_components()
        assert len(components) == 2
        
        # Verify component contents
        flat_components = [sorted(list(c)) for c in components]
        # Sort to ensure deterministic comparison regardless of order
        flat_components.sort(key=lambda x: x[0])
        
        assert flat_components[0] == ["A", "B"]
        assert flat_components[1] == ["X", "Y"]

    def test_metrics_calculation(self):
        """Geometric metrics should be computed correctly."""
        engine = TopologyEngine()
        
        # Triangle A-B-C-A
        fragments = (
            create_fragment_id("A"),
            create_fragment_id("B"),
            create_fragment_id("C")
        )
        relations = (
            create_relation("A", "B"),
            create_relation("B", "C"),
            create_relation("C", "A")
        )
        engine.build_graph(fragments, relations)
        
        metrics = engine.compute_metrics()
        
        assert metrics.node_count == 3
        assert metrics.edge_count == 3
        assert metrics.density == 1.0  # Fully connected
        assert metrics.diameter == 1   # Every node connected to every other
        
    def test_fence_post_no_ranking(self):
        """
        ML FENCE POST: API must not expose centrality or ranking.
        
        We verify that the public API does not return sorted lists based on importance
        or computed centrality scores.
        """
        engine = TopologyEngine()
        
        # Star topology: A is center, B, C, D connected to A
        fragments = (
            create_fragment_id("A"),
            create_fragment_id("B"),
            create_fragment_id("C"),
            create_fragment_id("D")
        )
        relations = (
            create_relation("A", "B"),
            create_relation("A", "C"),
            create_relation("A", "D")
        )
        engine.build_graph(fragments, relations)
        
        # 1. Metrics should not contain centrality
        metrics = engine.compute_metrics()
        assert not hasattr(metrics, "centrality")
        assert not hasattr(metrics, "pagerank")
        assert not hasattr(metrics, "importance")
        
        # 2. Components return sets (unordered), not lists (ranked)
        components = engine.get_connected_components()
        assert isinstance(components[0], set)
        
    def test_no_semantic_inference(self):
        """
        ML FENCE POST: Relations are treated as pure structure.
        
        The engine does not interpret 'confidence' or different relation types
        differently for topology. A connection is a connection.
        """
        engine = TopologyEngine()
        
        fragments = (create_fragment_id("A"), create_fragment_id("B"))
        
        # Even a 'contradiction' relation is a structural link
        relations = (
            FragmentRelation(
                source_fragment_id=create_fragment_id("A"),
                target_fragment_id=create_fragment_id("B"),
                relation_type=FragmentRelationType.CONTRADICTION, # Semantic meaning
                confidence=0.5, # Low confidence
                detected_at=Timestamp.now()
            ),
        )
        
        engine.build_graph(fragments, relations)
        metrics = engine.compute_metrics()
        
        # It's still one connected component
        assert metrics.is_connected is True
        assert metrics.edge_count == 1
