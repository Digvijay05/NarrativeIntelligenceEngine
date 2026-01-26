"""
Edge Injection Utility (Phase 3)
================================

Explicitly injects edges into the fragment graph WITHOUT inference.
Implements the "Graph Theoretic Falsifier" method:
- Edges must be grounded in explicit signals (links, shared IDs).
- Or explicitly supplied by an analyst (sequential threading).
"""

from typing import List, Tuple, Dict, Optional
from datetime import datetime

from backend.contracts.evidence import EvidenceFragment
from backend.contracts.base import (
    FragmentRelation, FragmentRelationType, 
    FragmentId, Timestamp
)

class EdgeInjector:
    """
    Injects explicit edges into a set of fragments.
    """
    
    @staticmethod
    def compute_hyperlink_edges(
        fragments: List[EvidenceFragment]
    ) -> List[FragmentRelation]:
        """
        Connect fragments based on explicit hyperlinks.
        Rule: If Fragment A contains a link that matches Fragment B's source link,
              create a REFERENCE edge A -> B.
        """
        # Index fragments by their source link for O(1) lookup
        # Note: A single link might be shared by duplicates (which we handled in normalization),
        # or multiple fragments might point to same canonical link.
        link_to_frag_id: Dict[str, FragmentId] = {}
        
        # Build index
        for frag in fragments:
            if frag.link:
                # Store mapping. If collision, last one wins (or we could store list)
                # For this experiment, direct matching is key.
                link_to_frag_id[frag.link] = FragmentId(frag.fragment_id, frag.payload_hash)
        
        edges = []
        now = Timestamp.now()
        
        for source_frag in fragments:
            source_id_obj = FragmentId(source_frag.fragment_id, source_frag.payload_hash)
            
            for hyperlink in source_frag.hyperlinks:
                # Check if this hyperlink points to a known fragment
                if hyperlink in link_to_frag_id:
                    target_id_obj = link_to_frag_id[hyperlink]
                    
                    # Avoid self-loops
                    if target_id_obj.value == source_id_obj.value:
                        continue
                        
                    # Create Edge
                    edge = FragmentRelation(
                        source_fragment_id=source_id_obj,
                        target_fragment_id=target_id_obj,
                        relation_type=FragmentRelationType.REFERENCE,
                        confidence=1.0, # Explicit hard link
                        detected_at=now
                    )
                    edges.append(edge)
                    
        return edges

    @staticmethod
    def compute_sequential_edges(
        fragments: List[EvidenceFragment],
        time_threshold_seconds: int = 86400 # 1 day default
    ) -> List[FragmentRelation]:
        """
        Connect fragments sequentially by time (Analyst Simulation).
        Rule: Connect frag[i] -> frag[i+1] AS IF read in a timeline.
        """
        # Sort by event time or ingest time
        sorted_frags = sorted(
            fragments, 
            key=lambda x: x.event_timestamp or x.ingest_timestamp
        )
        
        edges = []
        now = Timestamp.now()
        
        for i in range(len(sorted_frags) - 1):
            source = sorted_frags[i]
            target = sorted_frags[i+1]
            
            s_time = source.event_timestamp or source.ingest_timestamp
            t_time = target.event_timestamp or target.ingest_timestamp
            
            # Check time delta if threshold set
            delta = (t_time - s_time).total_seconds()
            if delta > time_threshold_seconds:
                continue # Gap too large, break chain
            
            s_id = FragmentId(source.fragment_id, source.payload_hash)
            t_id = FragmentId(target.fragment_id, target.payload_hash)
            
            edge = FragmentRelation(
                source_fragment_id=s_id,
                target_fragment_id=t_id,
                relation_type=FragmentRelationType.CONTINUATION,
                confidence=1.0, # Analyst/Timeline assertion
                detected_at=now
            )
            edges.append(edge)
            
        return edges
