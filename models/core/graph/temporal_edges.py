"""
Temporal Edge Manager

Manages temporal properties of knowledge graph edges.

BOUNDARY ENFORCEMENT:
- Updates edge temporal properties
- NO temporal prediction (that's Phase 3)
- Computes decay weights based on time only
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import math

from ...contracts.model_contracts import (
    GraphEdge, EdgeType, TemporalEdgeProperties
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class TemporalEdgeConfig:
    """Configuration for temporal edge management."""
    decay_rate: float = 0.1  # Decay rate per day
    activation_threshold: int = 3  # Minimum activations to be "active"
    dormancy_days: int = 14  # Days without activity to become dormant


# =============================================================================
# TEMPORAL EDGE MANAGER
# =============================================================================

class TemporalEdgeManager:
    """
    Manage temporal properties of knowledge graph edges.
    
    BOUNDARY ENFORCEMENT:
    - Computes temporal decay based on time elapsed
    - Tracks activation counts
    - NO prediction, NO inference
    """
    
    def __init__(self, config: Optional[TemporalEdgeConfig] = None):
        self._config = config or TemporalEdgeConfig()
        self._edge_properties: Dict[str, TemporalEdgeProperties] = {}
        self._activation_counts: Dict[str, int] = {}
        self._last_activations: Dict[str, datetime] = {}
    
    def compute_decay(
        self,
        edge: GraphEdge,
        current_time: Optional[datetime] = None
    ) -> float:
        """
        Compute temporal decay for an edge.
        
        Returns decay factor (0.0 to 1.0).
        """
        now = current_time or datetime.now()
        
        # Time since edge creation
        time_diff = (now - edge.timestamp).total_seconds()
        days_elapsed = time_diff / 86400
        
        # Exponential decay
        decay = math.exp(-self._config.decay_rate * days_elapsed)
        
        return max(0.0, min(1.0, decay))
    
    def apply_decay(
        self,
        edges: List[GraphEdge],
        current_time: Optional[datetime] = None
    ) -> List[GraphEdge]:
        """
        Apply temporal decay to a list of edges.
        
        Returns new edges with updated temporal_decay values.
        (Creates new immutable edges, doesn't mutate.)
        """
        now = current_time or datetime.now()
        decayed_edges = []
        
        for edge in edges:
            decay = self.compute_decay(edge, now)
            
            # Create new edge with updated decay
            new_edge = GraphEdge(
                edge_id=edge.edge_id,
                source_node_id=edge.source_node_id,
                target_node_id=edge.target_node_id,
                edge_type=edge.edge_type,
                weight=edge.weight * decay,
                temporal_decay=decay,
                confidence=edge.confidence,
                timestamp=edge.timestamp,
                properties=edge.properties
            )
            decayed_edges.append(new_edge)
        
        return decayed_edges
    
    def record_activation(
        self,
        edge_id: str,
        activation_time: Optional[datetime] = None
    ):
        """Record an edge activation (when the edge is used/referenced)."""
        now = activation_time or datetime.now()
        
        self._activation_counts[edge_id] = \
            self._activation_counts.get(edge_id, 0) + 1
        self._last_activations[edge_id] = now
    
    def get_lifecycle_stage(
        self,
        edge_id: str,
        current_time: Optional[datetime] = None
    ) -> str:
        """
        Get the lifecycle stage of an edge.
        
        Returns: "emerging", "active", "dormant", or "unknown"
        """
        now = current_time or datetime.now()
        
        activation_count = self._activation_counts.get(edge_id, 0)
        last_activation = self._last_activations.get(edge_id)
        
        if activation_count == 0:
            return "unknown"
        
        if activation_count < self._config.activation_threshold:
            return "emerging"
        
        if last_activation:
            days_since = (now - last_activation).total_seconds() / 86400
            if days_since > self._config.dormancy_days:
                return "dormant"
        
        return "active"
    
    def get_properties(
        self,
        edge_id: str,
        current_time: Optional[datetime] = None
    ) -> TemporalEdgeProperties:
        """Get full temporal properties for an edge."""
        now = current_time or datetime.now()
        
        lifecycle = self.get_lifecycle_stage(edge_id, now)
        activation_count = self._activation_counts.get(edge_id, 0)
        last_activation = self._last_activations.get(edge_id, now)
        
        return TemporalEdgeProperties(
            lifecycle_stage=lifecycle,
            decay_rate=self._config.decay_rate,
            last_activation=last_activation,
            activation_count=activation_count,
            state_transition_probability=0.0  # Would be computed by Phase 3
        )
    
    def prune_dormant_edges(
        self,
        edges: List[GraphEdge],
        current_time: Optional[datetime] = None,
        decay_threshold: float = 0.1
    ) -> List[GraphEdge]:
        """
        Filter out edges that have decayed below threshold.
        
        Returns list of edges that are still active enough.
        """
        now = current_time or datetime.now()
        active_edges = []
        
        for edge in edges:
            decay = self.compute_decay(edge, now)
            if decay >= decay_threshold:
                active_edges.append(edge)
        
        return active_edges
