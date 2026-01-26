"""
Topology Visualizer (Phase 5)
=============================

Visualizes structural fragility (Narrative Load) by identifying critical edges.
Purely analytical: NO inference, NO repair.

Capabilities:
1. Reconstruct graph from ThreadStateSnapshot.
2. Detect Bridges (Edges whose removal increases component count).
3. Identify Redundant Edges (Cycles).
4. Render Mermaid diagrams with style encoding for criticality.
"""

import networkx as nx
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass

from backend.contracts.events import ThreadStateSnapshot, FragmentRelationType

@dataclass
class EdgeAnalysis:
    """Analysis of a single edge's structural role."""
    source: str
    target: str
    relation_type: str
    is_critical: bool  # True if Bridge
    component_split_count: int # How many components if removed (2+ = Critical)

class TopologyVisualizer:
    """
    Visualizes narrative topology and criticality.
    """
    
    def __init__(self, snapshot: ThreadStateSnapshot):
        self.snapshot = snapshot
        self.graph = self._build_graph()
        
    def _build_graph(self) -> nx.Graph:
        """Reconstruct NetworkX graph from snapshot."""
        G = nx.Graph()
        
        # Add nodes
        for frag_id in self.snapshot.member_fragment_ids:
            G.add_node(frag_id.value)
            
        # Add edges
        for rel in self.snapshot.relations:
            G.add_edge(
                rel.source_fragment_id.value,
                rel.target_fragment_id.value,
                relation_type=rel.relation_type.value
            )
            
        return G
    
    def analyze_criticality(self) -> List[EdgeAnalysis]:
        """
        Identify critical (bridge) vs redundant edges.
        Method: Remove edge -> Check connected components count.
        """
        analysis = []
        base_components = nx.number_connected_components(self.graph)
        
        # We iterate over the edges in the snapshot to preserve relation metadata
        # (NetworkX edge iteration might lose the specific relation object/type if not careful)
        for rel in self.snapshot.relations:
            u, v = rel.source_fragment_id.value, rel.target_fragment_id.value
            
            # Temporarily remove edge
            if self.graph.has_edge(u, v):
                self.graph.remove_edge(u, v)
                new_components = nx.number_connected_components(self.graph)
                self.graph.add_edge(u, v, relation_type=rel.relation_type.value)
                
                is_critical = new_components > base_components
                
                analysis.append(EdgeAnalysis(
                    source=u,
                    target=v,
                    relation_type=rel.relation_type.name,
                    is_critical=is_critical,
                    component_split_count=new_components
                ))
                
        return analysis

    def generate_mermaid(self, content_map: Dict[str, str] = None) -> str:
        """
        Generate Mermaid diagram highlighting structural load.
        Critical Edges = Red/Thick
        Redundant Edges = Blue/Dashed
        """
        analysis = self.analyze_criticality()
        
        lines = ["graph TD"]
        
        # Style definitions
        lines.append("    classDef critical stroke:#ff0000,stroke-width:4px;")
        lines.append("    classDef redundant stroke:#0000ff,stroke-dasharray: 5 5;")
        lines.append("    classDef node default fill:#fff,stroke:#333,stroke-width:1px;")
        
        # Nodes (with label truncation)
        for node in self.graph.nodes():
            label = node[-6:] # Short ID
            if content_map:
                # Try to get title or shorter text
                text = content_map.get(node, "")
                if text:
                    # simplistic truncation
                    label = f"{node[-4:]}: {text[:20]}..."
            lines.append(f'    {node}["{label}"]')
            
        # Edges
        for i, edge in enumerate(analysis):
            # Mermaid link styles
            # Critical: === (Thick) - but mermaid strictly uses styles
            # We will use simple links and apply styles by link ID if possible, 
            # or just use generic link syntax and rely on classDefs if we could apply classes to links.
            # Mermaid 'linkStyle' applies by index (0, 1, 2...). 
            
            link_symbol = "---"
            if edge.relation_type == "CONTINUATION":
                link_symbol = "-->"
            
            line = f"    {edge.source} {link_symbol} {edge.target}"
            lines.append(line)
            
            # Style application
            style_class = "critical" if edge.is_critical else "redundant"
            # stroke-width for critical, dash for redundant
            color = "#ff0000" if edge.is_critical else "#0000ff"
            width = "4px" if edge.is_critical else "1px"
            dash = "" if edge.is_critical else ",stroke-dasharray: 5 5"
            
            lines.append(f"    linkStyle {i} stroke:{color},stroke-width:{width}{dash};")
            
        return "\n".join(lines)
