"""
Knowledge Graph Builder

Constructs knowledge graphs from annotated fragments.

BOUNDARY ENFORCEMENT:
- Consumes AnnotatedFragment
- Produces KnowledgeGraphSnapshot
- NO temporal prediction, NO inference
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import hashlib

from ...contracts.data_contracts import AnnotatedFragment
from ...contracts.model_contracts import (
    GraphNode, GraphEdge, KnowledgeGraphSnapshot,
    NodeType, EdgeType
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class GraphConfig:
    """Configuration for knowledge graph construction."""
    min_cooccurrence_count: int = 2
    edge_confidence_threshold: float = 0.5
    enable_validation_chains: bool = True


# =============================================================================
# NODE BUILDERS
# =============================================================================

class NodeBuilder:
    """Build nodes for the knowledge graph."""
    
    def create_entity_node(
        self,
        entity_id: str,
        label: str,
        source_fragment_id: str
    ) -> GraphNode:
        """Create a node for an entity."""
        return GraphNode(
            node_id=f"node_ent_{entity_id}",
            node_type=NodeType.ENTITY,
            label=label,
            properties=(
                ("source_fragment", source_fragment_id),
            ),
            created_at=datetime.now()
        )
    
    def create_topic_node(
        self,
        topic_id: str
    ) -> GraphNode:
        """Create a node for a topic."""
        return GraphNode(
            node_id=f"node_top_{topic_id}",
            node_type=NodeType.TOPIC,
            label=topic_id.replace('_', ' ').title(),
            properties=(),
            created_at=datetime.now()
        )
    
    def create_fragment_node(
        self,
        fragment: AnnotatedFragment
    ) -> GraphNode:
        """Create a node for a fragment."""
        return GraphNode(
            node_id=f"node_frag_{fragment.fragment_id}",
            node_type=NodeType.FRAGMENT,
            label=fragment.fragment_id[:16],
            properties=(
                ("quality", fragment.preprocessed_fragment.quality.value),
                ("is_duplicate", str(fragment.is_duplicate)),
            ),
            embedding_id=fragment.preprocessed_fragment.semantic_features.embedding.embedding_id if hasattr(fragment.preprocessed_fragment.semantic_features.embedding, 'embedding_id') else None,
            created_at=datetime.now()
        )


# =============================================================================
# EDGE BUILDERS
# =============================================================================

class EdgeBuilder:
    """Build edges for the knowledge graph."""
    
    def __init__(self):
        self._edge_counter = 0
    
    def create_cooccurrence_edge(
        self,
        source_id: str,
        target_id: str,
        count: int,
        confidence: float
    ) -> GraphEdge:
        """Create a co-occurrence edge."""
        self._edge_counter += 1
        
        edge_hash = hashlib.sha256(
            f"{source_id}|{target_id}|cooccur".encode()
        ).hexdigest()[:12]
        
        return GraphEdge(
            edge_id=f"edge_{edge_hash}",
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=EdgeType.CO_OCCURRENCE,
            weight=float(count),
            temporal_decay=1.0,
            confidence=confidence,
            timestamp=datetime.now(),
            properties=(("count", str(count)),)
        )
    
    def create_reference_edge(
        self,
        source_id: str,
        target_id: str,
        confidence: float
    ) -> GraphEdge:
        """Create a reference edge."""
        self._edge_counter += 1
        
        edge_hash = hashlib.sha256(
            f"{source_id}|{target_id}|ref".encode()
        ).hexdigest()[:12]
        
        return GraphEdge(
            edge_id=f"edge_{edge_hash}",
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=EdgeType.REFERENCE,
            weight=1.0,
            temporal_decay=1.0,
            confidence=confidence,
            timestamp=datetime.now()
        )
    
    def create_contradiction_edge(
        self,
        source_id: str,
        target_id: str,
        confidence: float
    ) -> GraphEdge:
        """Create a contradiction edge."""
        edge_hash = hashlib.sha256(
            f"{source_id}|{target_id}|contra".encode()
        ).hexdigest()[:12]
        
        return GraphEdge(
            edge_id=f"edge_{edge_hash}",
            source_node_id=source_id,
            target_node_id=target_id,
            edge_type=EdgeType.CONTRADICTION,
            weight=1.0,
            temporal_decay=1.0,
            confidence=confidence,
            timestamp=datetime.now()
        )


# =============================================================================
# KNOWLEDGE GRAPH BUILDER
# =============================================================================

class KnowledgeGraphBuilder:
    """
    Build knowledge graphs from annotated fragments.
    
    BOUNDARY ENFORCEMENT:
    - Consumes AnnotatedFragment
    - Produces KnowledgeGraphSnapshot
    - NO temporal prediction, NO inference
    """
    
    def __init__(self, config: Optional[GraphConfig] = None):
        self._config = config or GraphConfig()
        self._node_builder = NodeBuilder()
        self._edge_builder = EdgeBuilder()
        self._version_counter = 0
    
    def build_graph(
        self,
        fragments: List[AnnotatedFragment],
        parent_snapshot_id: Optional[str] = None
    ) -> KnowledgeGraphSnapshot:
        """
        Build a knowledge graph from annotated fragments.
        
        Returns an immutable KnowledgeGraphSnapshot.
        """
        nodes: Dict[str, GraphNode] = {}
        edges: List[GraphEdge] = []
        
        # Track co-occurrences
        entity_cooccurrences: Dict[Tuple[str, str], int] = {}
        topic_entity_links: Dict[Tuple[str, str], int] = {}
        
        # Build nodes and track relationships
        for fragment in fragments:
            # Create fragment node
            frag_node = self._node_builder.create_fragment_node(fragment)
            nodes[frag_node.node_id] = frag_node
            
            # Create topic nodes and link to fragment
            for topic_id in fragment.preprocessed_fragment.semantic_features.topic_ids:
                topic_node_id = f"node_top_{topic_id}"
                
                if topic_node_id not in nodes:
                    topic_node = self._node_builder.create_topic_node(topic_id)
                    nodes[topic_node_id] = topic_node
                
                # Link fragment to topic
                edges.append(self._edge_builder.create_reference_edge(
                    source_id=frag_node.node_id,
                    target_id=topic_node_id,
                    confidence=1.0
                ))
            
            # Create entity nodes
            for entity_id in fragment.preprocessed_fragment.semantic_features.entity_ids:
                entity_node_id = f"node_ent_{entity_id}"
                
                if entity_node_id not in nodes:
                    entity_node = self._node_builder.create_entity_node(
                        entity_id=entity_id,
                        label=entity_id[:12],
                        source_fragment_id=fragment.fragment_id
                    )
                    nodes[entity_node_id] = entity_node
                
                # Link fragment to entity
                edges.append(self._edge_builder.create_reference_edge(
                    source_id=frag_node.node_id,
                    target_id=entity_node_id,
                    confidence=1.0
                ))
            
            # Track entity co-occurrences
            entity_ids = list(fragment.preprocessed_fragment.semantic_features.entity_ids)
            for i, eid1 in enumerate(entity_ids):
                for eid2 in entity_ids[i+1:]:
                    key = tuple(sorted([eid1, eid2]))
                    entity_cooccurrences[key] = entity_cooccurrences.get(key, 0) + 1
            
            # Add contradiction edges
            for contra_id in fragment.contradiction_targets:
                edges.append(self._edge_builder.create_contradiction_edge(
                    source_id=frag_node.node_id,
                    target_id=f"node_frag_{contra_id}",
                    confidence=0.8
                ))
        
        # Add co-occurrence edges
        for (eid1, eid2), count in entity_cooccurrences.items():
            if count >= self._config.min_cooccurrence_count:
                edges.append(self._edge_builder.create_cooccurrence_edge(
                    source_id=f"node_ent_{eid1}",
                    target_id=f"node_ent_{eid2}",
                    count=count,
                    confidence=min(1.0, count / 10.0)
                ))
        
        # Create snapshot
        self._version_counter += 1
        version = f"kg_v{self._version_counter}"
        
        snapshot_id = hashlib.sha256(
            f"{version}|{len(nodes)}|{len(edges)}".encode()
        ).hexdigest()[:16]
        
        return KnowledgeGraphSnapshot(
            snapshot_id=f"kgs_{snapshot_id}",
            version=version,
            nodes=tuple(nodes.values()),
            edges=tuple(edges),
            node_count=len(nodes),
            edge_count=len(edges),
            created_at=datetime.now(),
            parent_snapshot_id=parent_snapshot_id
        )
    
    def merge_graphs(
        self,
        graph_a: KnowledgeGraphSnapshot,
        graph_b: KnowledgeGraphSnapshot
    ) -> KnowledgeGraphSnapshot:
        """
        Merge two knowledge graph snapshots.
        
        Returns a new merged snapshot.
        """
        # Combine nodes (dedup by node_id)
        all_nodes = {n.node_id: n for n in graph_a.nodes}
        for node in graph_b.nodes:
            if node.node_id not in all_nodes:
                all_nodes[node.node_id] = node
        
        # Combine edges (dedup by edge_id)
        all_edges = {e.edge_id: e for e in graph_a.edges}
        for edge in graph_b.edges:
            if edge.edge_id not in all_edges:
                all_edges[edge.edge_id] = edge
        
        self._version_counter += 1
        version = f"kg_merged_v{self._version_counter}"
        
        snapshot_id = hashlib.sha256(
            f"{graph_a.snapshot_id}|{graph_b.snapshot_id}".encode()
        ).hexdigest()[:16]
        
        return KnowledgeGraphSnapshot(
            snapshot_id=f"kgs_{snapshot_id}",
            version=version,
            nodes=tuple(all_nodes.values()),
            edges=tuple(all_edges.values()),
            node_count=len(all_nodes),
            edge_count=len(all_edges),
            created_at=datetime.now(),
            parent_snapshot_id=graph_a.snapshot_id,
            metadata=(
                ("merged_from_a", graph_a.snapshot_id),
                ("merged_from_b", graph_b.snapshot_id),
            )
        )
