"""
Trace Harness (Phase 4)
=======================

Infrastructure for running parameterized narrative experiments.
Encapsulates the standard pipeline:
1. Fetch (cached/mock)
2. Normalize
3. Enrich (Embeddings)
4. Inject Edges (Parameterized)
5. Ingest (Core Engine)
6. Measure (Topology)

Design:
- Reusable pipeline execution
- Configurable edge policies (Hyperlinks, Sequential, Dropout)
- Standardized metric collection
"""

import os
import sys
from datetime import datetime
from typing import List, Tuple, Dict, Optional, Set
from dataclasses import dataclass
import random

# Add project root to path (robustly)
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.core import NarrativeStateEngine
from backend.contracts.base import (
    FragmentId, Timestamp, SourceId, ContentSignature, SourceMetadata,
    FragmentRelation, FragmentRelationType
)
from backend.contracts.events import (
    NormalizedFragment, DuplicateInfo, DuplicateStatus,
    ContradictionInfo, ContradictionStatus,
    EmbeddingVector, ThreadStateSnapshot
)
from backend.contracts.evidence import EvidenceFragment
from backend.normalization.embedding_service import get_embedding_service, EmbeddingServiceConfig
from ingestion.normalizer import RSSNormalizer
from ingestion.contracts import FeedSource, FeedCategory, FeedTier
from demo.edge_injector import EdgeInjector

# Mock/Cached data path
RAW_STORAGE_DIR = os.path.join(project_root, "demo_data", "raw_rss")

@dataclass
class ExperimentConfig:
    """Configuration for a single experiment run."""
    name: str
    use_hyperlinks: bool
    use_analyst_sequence: bool
    edge_dropout_rate: float = 0.0  # 0.0 to 1.0
    inject_conflicts: bool = False
    keyword_filter: Optional[List[str]] = None

@dataclass
class ExperimentResult:
    """Result of an experiment."""
    config_name: str
    total_fragments: int
    total_edges: int
    final_thread_count: int
    connected_components: int
    max_component_size: int
    is_connected: bool
    divergence_reasons: List[str]

class TraceHarness:
    """
    Standardized harness for running narrative experiments.
    """
    
    def __init__(self):
        self.embedding_service = get_embedding_service(
            EmbeddingServiceConfig(model_id="all-MiniLM-L6-v2")
        )
        self.embedding_service.clear_index()
        self.normalizer = RSSNormalizer(raw_storage_path=RAW_STORAGE_DIR)
        
    def run_experiment(self, fragments: List[EvidenceFragment], content_map: Dict[str, str], config: ExperimentConfig) -> ExperimentResult:
        """Run a full pipeline experiment with the given config."""
        print(f"\n--- Running Experiment: {config.name} ---")
        print(f"  Configuration: Links={config.use_hyperlinks}, Seq={config.use_analyst_sequence}, Dropout={config.edge_dropout_rate}")
        
        # 1. Reset Engine
        engine = NarrativeStateEngine()
        
        # 2. Inject Edges
        edges = []
        if config.use_hyperlinks:
            edges.extend(EdgeInjector.compute_hyperlink_edges(fragments))
        
        if config.use_analyst_sequence:
            edges.extend(EdgeInjector.compute_sequential_edges(fragments))
            
        # 3. Apply Dropout (Stress Test)
        if config.edge_dropout_rate > 0:
            original_count = len(edges)
            edges = self._apply_dropout(edges, config.edge_dropout_rate)
            print(f"  Dropout Applied: {original_count} -> {len(edges)} edges")
            
        # 4. Inject Conflicts (Forensic Stress)
        if config.inject_conflicts:
            # TODO: Implement conflict injection
            pass
            
        # Index edges by participant (both source and target)
        # This ensures that whether a fragment is the source or target of a relation,
        # it carries that relation into the engine. This is critical for the StateMachine
        # to see the connection to an existing thread.
        edges_by_participant = {}
        for edge in edges:
            src = edge.source_fragment_id.value
            tgt = edge.target_fragment_id.value
            
            if src not in edges_by_participant:
                edges_by_participant[src] = []
            if tgt not in edges_by_participant:
                edges_by_participant[tgt] = []
                
            edges_by_participant[src].append(edge)
            edges_by_participant[tgt].append(edge)
            
        # 5. Prepare Normalized Fragments
        normalized_fragments = []
        for ev in fragments:
            # Recover content from map using (source_id, link) as key (standardize on how normalizer/fetcher work)
            # Or simplified: the caller passes map keyed by fragment_id or similar.
            # Let's assume content_map is Dict[str, str] keyed by fragment_id for simplicity in harness.
            description = content_map.get(ev.fragment_id, "")
            full_text = f"{ev.title} {description}"
            vec = self.embedding_service.compute_embedding(full_text)
            frag_id = FragmentId(ev.fragment_id, ev.payload_hash)
            
            # Attach edges
            explicit_edges = edges_by_participant.get(ev.fragment_id, [])
            
            norm_frag = NormalizedFragment(
                fragment_id=frag_id,
                source_event_id=f"evt_{ev.fragment_id}",
                content_signature=ContentSignature(ev.fragment_id, len(full_text)),
                normalized_payload=full_text,
                detected_language="en",
                canonical_topics=(),
                canonical_entities=(),
                duplicate_info=DuplicateInfo(DuplicateStatus.UNIQUE),
                contradiction_info=ContradictionInfo(ContradictionStatus.NO_CONTRADICTION),
                normalization_timestamp=Timestamp(ev.ingest_timestamp),
                source_metadata=SourceMetadata(
                    source_id=SourceId(ev.source_id, "rss"),
                    source_confidence=1.0,
                    capture_timestamp=Timestamp(ev.ingest_timestamp),
                    event_timestamp=Timestamp(ev.event_timestamp) if ev.event_timestamp else Timestamp(ev.ingest_timestamp)
                ),
                embedding_vector=vec,
                candidate_relations=tuple(explicit_edges)
            )
            normalized_fragments.append(norm_frag)
            
        # 6. Ingest
        divergence_reasons = []
        for frag in normalized_fragments:
            outcome = engine.process_fragment(frag)
            if outcome.state_event and outcome.state_event.new_state_snapshot.divergence_reason:
                divergence_reasons.append(outcome.state_event.new_state_snapshot.divergence_reason)
                
        # 7. Collect Metrics
        snapshots = engine.get_all_current_snapshots()
        
        # Calculate max component size (simple approximation from thread size for now)
        # Real topology analysis would require accessing the internal graph or result
        max_size = 0
        connected_components = 0
        final_thread_count = len(snapshots)
        
        # Note: In the current engine implementation, each 'thread' is a connected component
        # derived from the event log. If 'divergence' happens, it splits.
        # But if we have valid edges, they should merge.
        # We need to look at the *structure* of the result.
        
        # For this phase, we treat each resulting 'thread' as a component.
        for snap in snapshots.values():
            size = len(snap.member_fragment_ids)
            max_size = max(max_size, size)
            if snap.lifecycle_state.name != "DIVERGED":
                connected_components += 1
            else:
                # If diverged, parsing the reason string is a hack, but sufficient for harness
                # "Structural divergence detected: Thread split into X components"
                try:
                    import re
                    match = re.search(r"split into (\d+) components", snap.divergence_reason or "")
                    if match:
                        connected_components += int(match.group(1))
                    else:
                        connected_components += 1 # Fallback
                except:
                    connected_components += 1

        is_connected = (connected_components == 1) and (final_thread_count == 1)
        
        return ExperimentResult(
            config_name=config.name,
            total_fragments=len(fragments),
            total_edges=len(edges),
            final_thread_count=final_thread_count,
            connected_components=connected_components,
            max_component_size=max_size,
            is_connected=is_connected,
            divergence_reasons=divergence_reasons
        )

    def _apply_dropout(self, edges: List[FragmentRelation], rate: float) -> List[FragmentRelation]:
        """Randomly remove edges based on rate."""
        if not edges:
            return []
        
        keep_count = int(len(edges) * (1.0 - rate))
        return random.sample(edges, keep_count)
