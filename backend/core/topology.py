"""
Topology Engine
===============

Structural analysis of narrative threads using graph topology.

ML FENCE POST:
==============
This engine computes TOPOLOGY (geometry), not IMPORTANCE (judgment).

ALLOWED:
- Graph construction options
- Connected components (clustering)
- Path finding (traceability)
- Structural metrics (density, diameter)
- Cycle detection

FORBIDDEN:
- Centrality measures (PageRank, Betweenness) - implies ranking
- Influence scoring - implies agency
- Community detection based on semantics (use structural only)
"""

from __future__ import annotations
from typing import Dict, List, Set, Tuple, Optional, Any
from dataclasses import dataclass
import networkx as nx

from ..contracts.base import FragmentId
from ..contracts.events import FragmentRelation, FragmentRelationType


@dataclass(frozen=True)
class GraphMetrics:
    """Immutable structural metrics for a graph or subgraph."""
    node_count: int
    edge_count: int
    density: float
    is_connected: bool
    connected_components_count: int
    diameter: Optional[int] = None  # Only for connected graphs
    
    # ML FENCE POST: No centrality or importance scores here


class TopologyEngine:
    """
    Engine for structural analysis of narrative graphs.
    
    Wraps NetworkX to explicitly allow only forensic/geometric operations
    and ban interpretive/ranking operations.
    """
    
    def __init__(self):
        # Internal graph representation (undirected by default)
        self._graph = nx.Graph()
    
    def build_graph(
        self,
        fragment_ids: Tuple[FragmentId, ...],
        relations: Tuple[FragmentRelation, ...]
    ) -> None:
        """
        Build graph from fragments and relations.
        
        Replaces internal graph state.
        """
        self._graph = nx.Graph()
        
        # Add nodes
        for fragment_id in fragment_ids:
            self._graph.add_node(fragment_id.value)
            
        # Add edges
        for relation in relations:
            # We treat all relations as structural connections
            # Constraint: We explicitly ignore 'confidence' for topology
            # Topology is binary: connected or not
            self._graph.add_edge(
                relation.source_fragment_id.value,
                relation.target_fragment_id.value,
                relation_type=relation.relation_type.value
            )
            
    def get_connected_components(self) -> List[Set[str]]:
        """
        Identify disjoint subgraphs (structural clusters).
        
        Returns list of sets of fragment IDs.
        No sorting or ranking of components (returned in arbitrary order).
        """
        if not self._graph:
            return []
            
        return [set(c) for c in nx.connected_components(self._graph)]
    
    def detect_structural_divergence(
        self,
        known_thread_ids: Set[str]
    ) -> List[Set[str]]:
        """
        Detect if graph has split into more components than expected.
        
        Returns components that represent potential divergences.
        """
        components = self.get_connected_components()
        
        # If we have more components than threads, we have divergence
        if len(components) > max(1, len(known_thread_ids)):
            return components
            
        return []

    def compute_metrics(self) -> GraphMetrics:
        """
        Compute purely structural metrics.
        
        ML FENCE POST:
        - Density: Allowed (geometry)
        - Connectedness: Allowed (topology)
        - Diameter: Allowed (longest path)
        - Centrality: FORBIDDEN (ranking)
        """
        if not self._graph:
            return GraphMetrics(0, 0, 0.0, False, 0, None)
            
        is_connected = nx.is_connected(self._graph)
        
        diameter = None
        if is_connected and len(self._graph) > 1:
            try:
                diameter = nx.diameter(self._graph)
            except Exception:
                diameter = None
        
        return GraphMetrics(
            node_count=self._graph.number_of_nodes(),
            edge_count=self._graph.number_of_edges(),
            density=nx.density(self._graph),
            is_connected=is_connected,
            connected_components_count=nx.number_connected_components(self._graph),
            diameter=diameter
        )
    
    def get_shortest_path(self, start_id: str, end_id: str) -> Optional[List[str]]:
        """
        Find shortest path between two fragments.
        
        Allowed as a purely geometric trace operation.
        Does NOT imply "narrative flow" or causality.
        """
        try:
            return nx.shortest_path(self._graph, source=start_id, target=end_id)
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None
            
    def clear(self):
        """Clear functionality."""
        self._graph.clear()
