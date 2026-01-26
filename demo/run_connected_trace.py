"""
Connected Graph Experiment (Phase 3)
====================================

Hypothesis: Explicit edge injection turns "Bag of Points" into "Narrative".

Method:
1. Re-run Abu Dhabi narrow scope fetch.
2. Sort by time.
3. INJECT EDGES: Manually link each fragment to the previous one (Simulating 'Sequential Read' or 'Analyst Threading').
4. Verify if TopologyEngine accepts it as a connected component.
"""

import asyncio
import json
import os
import sys
from datetime import datetime
from typing import List, Tuple
from collections import defaultdict

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
    EmbeddingVector
)
from backend.contracts.evidence import EvidenceFragment
from backend.normalization.embedding_service import get_embedding_service, EmbeddingServiceConfig

# Import Ingestion Layer
from ingestion.fetcher import RSSFetcher
from ingestion.normalizer import RSSNormalizer
from ingestion.contracts import FeedSource, FeedCategory, FeedTier

# Import Edge Injector
from demo.edge_injector import EdgeInjector

ARTIFACT_DIR = "demo_artifacts_connected"
RAW_STORAGE_DIR = os.path.join(project_root, "demo_data", "raw_rss")

# --- Inline Configuration (Restoring lost dependencies) ---

def keyword_filter(items: List[dict]) -> List[dict]:
    keywords = ['Abu Dhabi', 'trilateral', 'peace talks', 'negotiations']
    print(f"  Filtering {len(items)} items for keywords: {keywords}...")
    filtered = []
    for item in items:
        text = (item.get('title') or "") + " " + (item.get('description') or "")
        if any(k.lower() in text.lower() for k in keywords):
            filtered.append(item)
    print(f"  -> Kept {len(filtered)} items.")
    return filtered

# Re-constructing sources based on experiment context (Ukraine/Peace Talks)
REAL_SOURCES = [
    FeedSource(
        source_id="aljazeera",
        name="Al Jazeera",
        url="https://www.aljazeera.com/xml/rss/all.xml",
        category=FeedCategory.GLOBAL_CONTEXT,
        tier=FeedTier.TIER_1,
        language="en",
        region="Global",
        enabled=True
    ),
     FeedSource(
        source_id="bbc_world",
        name="BBC World",
        url="http://feeds.bbci.co.uk/news/world/rss.xml",
        category=FeedCategory.GLOBAL_CONTEXT,
        tier=FeedTier.TIER_1,
        language="en",
        region="uk",
        enabled=True
    ),
    FeedSource(
        source_id="google_news_ukraine",
        name="Google News",
        url="https://news.google.com/rss/search?q=Ukraine+peace+talks+Abu+Dhabi&hl=en-US&gl=US&ceid=US:en",
        category=FeedCategory.SPECIALIZED,
        tier=FeedTier.TIER_2,
        language="en",
        region="US",
        enabled=True
    )
]

# =============================================================================
# PIPELINE
# =============================================================================

async def pipeline_execution():
    print(f"=== PHASE 3: CONNECTED GRAPH EXPERIMENT ===\n")
    
    # Setup
    fetcher = RSSFetcher()
    normalizer = RSSNormalizer(raw_storage_path=RAW_STORAGE_DIR)
    engine = NarrativeStateEngine() 
    
    # 1. Fetch & Filter
    print(f"\n--- Phase 1: Fetching & Filtering ---")
    results = []
    content_map = {}
    
    for source in REAL_SOURCES:
        res, payload, items = await fetcher.fetch(source)
        if res.success:
            items_dicts = []
            for item in items:
                d = {
                    'item_id': item.item_id,
                    'source_id': item.source_id,
                    'title': item.title,
                    'link': item.link,
                    'description': item.description,
                    'published_at': item.published_at,
                    'fetched_at': item.fetched_at,
                    'author': item.author,
                    'categories': item.categories,
                    'guid': item.guid,
                    'raw_payload_path': ""
                }
                items_dicts.append(d)
                content_map[(source.source_id, item.link)] = item.description
            
            filtered_items = keyword_filter(items_dicts)
            if filtered_items:
                results.append((source.source_id, filtered_items))
    
    # 2. Normalize
    print(f"\n--- Phase 2: Normalization ---")
    all_fragments = []
    for sid, items in results:
        report = normalizer.normalize_batch(items, datetime.utcnow())
        all_fragments.extend(report.fragments)
    
    # SORT BY TIME (Crucial for sequential linking)
    all_fragments.sort(key=lambda x: x.event_timestamp or x.ingest_timestamp)
    print(f"Total Topic-Specific Fragments: {len(all_fragments)} (Sorted by Time)")
    
    # 3. Enrichment + EDGE INJECTION
    print(f"\n--- Phase 3: Enrichment & EDGE INJECTION ---")
    config = EmbeddingServiceConfig(model_id="all-MiniLM-L6-v2")
    embedding_service = get_embedding_service(config)
    embedding_service.clear_index() 
    
    # COMPUTE EXPLICIT EDGES
    print("  -> Computing Hyperlink Edges...")
    hyperlink_edges = EdgeInjector.compute_hyperlink_edges(all_fragments)
    print(f"     Found {len(hyperlink_edges)} hyperlink edges.")
    
    print("  -> Computing Sequential Edges (Analyst Simulation)...")
    sequential_edges = EdgeInjector.compute_sequential_edges(all_fragments)
    print(f"     Found {len(sequential_edges)} sequential edges.")
    
    all_edges = hyperlink_edges + sequential_edges
    
    # Index by source ID to attach to fragments
    edges_by_source = defaultdict(list)
    for edge in all_edges:
        edges_by_source[edge.source_fragment_id.value].append(edge)

    normalized_fragments = []
    
    for ev in all_fragments:
        # Recover content
        description = content_map.get((ev.source_id, ev.link), "")
        full_text = f"{ev.title} {description}"
        
        vec = embedding_service.compute_embedding(full_text)
        
        # Calculate derived IDs
        frag_id = FragmentId(ev.fragment_id, ev.payload_hash)
        
        # RETRIEVE INJECTED EDGES
        explicit_edges = edges_by_source[ev.fragment_id]
        if explicit_edges:
            print(f"  -> Fragment {ev.fragment_id} has {len(explicit_edges)} explicit edges.")
            
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
            candidate_relations=tuple(explicit_edges) # INJECTED HERE
        )
        normalized_fragments.append(norm_frag)
        
    # 4. Ingest
    print(f"\n--- Phase 4: Ingestion ---")
    trace_events = []
    
    for frag in normalized_fragments:
        outcome = engine.process_fragment(frag)
        
        status = outcome.state_event.event_type if outcome.state_event else outcome.result
        divergence = "None"
        if outcome.state_event and outcome.state_event.new_state_snapshot.divergence_reason:
            divergence = outcome.state_event.new_state_snapshot.divergence_reason
            
        print(f"[{status}] Thread {outcome.state_event.thread_id.value} | Divergence: {divergence}")
            
        if outcome.state_event:
            trace_events.append({
                "event_type": outcome.state_event.event_type,
                "divergence": divergence,
                "title": frag.normalized_payload[:50]
            })

    # 5. Export
    os.makedirs(ARTIFACT_DIR, exist_ok=True)
    with open(os.path.join(ARTIFACT_DIR, "connected_trace.json"), "w") as f:
        json.dump(trace_events, f, indent=2)

    snapshots = engine.get_all_current_snapshots()
    print(f"\nFinal Threads: {len(snapshots)}")
    for tid, snap in snapshots.items():
        comp_count = snap.divergence_reason if snap.lifecycle_state.name == "DIVERGED" else "1 (Connected)"
        print(f"Thread {tid}: {len(snap.member_fragment_ids)} items. State: {snap.lifecycle_state.name}. Components: {comp_count}")

if __name__ == "__main__":
    asyncio.run(pipeline_execution())
