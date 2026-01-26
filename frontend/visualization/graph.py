"""
Graph Visualization Contracts

Responsibility:
Deterministic transformation of Entity Relations into Renderable Graph Views.
"""

from dataclasses import dataclass
from typing import Tuple, List, Optional
from frontend.state import AvailabilityState

@dataclass(frozen=True)
class GraphNode:
    """Renderable graph node."""
    node_id: str
    x: float
    y: float
    radius: float
    color: str
    label: str
    entity_type: str
    is_focal_point: bool

@dataclass(frozen=True)
class GraphEdge:
    """Renderable graph edge."""
    edge_id: str
    source_id: str
    target_id: str
    thickness: float
    style: str # solid, dashed, dotted
    label: Optional[str]

@dataclass(frozen=True)
class NetworkGraphView:
    """
    Pre-layouted network graph.
    Layout must be stable.
    """
    view_id: str
    nodes: Tuple[GraphNode, ...]
    edges: Tuple[GraphEdge, ...]
    availability: AvailabilityState
