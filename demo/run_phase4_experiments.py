"""
Phase 4: Edge Provenance Taxonomy & Stress Testing
==================================================

Executes a battery of experiments to characterize the "Failure Envelopes"
of the narrative graph under different edge conditions.

Experiments:
1. "Rigorous" Baseline (Hyperlinks Only)
2. "Curated" Thread (Analyst Sequence Only)
3. Mixed Graph (Simulating real application)
4. Stress Test: Edge Dropout (Finding the collapse point)
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import List

# Add project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(script_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

from demo.trace_harness import TraceHarness, ExperimentConfig
from ingestion.fetcher import RSSFetcher
from ingestion.contracts import FeedSource, FeedCategory, FeedTier
from demo.run_connected_trace import keyword_filter, REAL_SOURCES

async def run_experiments():
    print("=== PHASE 4: EDGE PROVENANCE TAXONOMY & STRESS TESTING ===\n")
    
    # 1. Acquire Data (Reuse Abu Dhabi narrow scope)
    print("Acquiring Baseline Data (Abu Dhabi Trace)...")
    fetcher = RSSFetcher()
    all_items = []
    
    # Quick fetch (or mock if files exist - here we fetch to be fresh)
    for source in REAL_SOURCES:
        res, _, items = await fetcher.fetch(source)
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
            filtered = keyword_filter(items_dicts)
            all_items.extend(filtered)
            
    # Normalize
    harness = TraceHarness()
    report = harness.normalizer.normalize_batch(all_items, datetime.utcnow())
    fragments = report.fragments
    # Sort for consistency
    fragments.sort(key=lambda x: x.event_timestamp or x.ingest_timestamp)
    
    print(f"Dataset: {len(fragments)} fragments sorted by time.\n")
    
    # Build Content Map (FragmentID -> Description)
    content_map = {}
    # We need to map back from fragment to original item description.
    # Since fragment IDs are deterministic hashes of (source|time|link|title|desc), 
    # and we have the fragments and the original items, we can try to map them.
    # A robust way: The normalizer reports fragments. We can assume we have the original items.
    # IMPROVEMENT: The normalizer report could carry the mapping, or we carry it from fetch.
    
    # For this harness, let's create a lookup from the filtered items list
    # Item -> description. Link + Title is good key.
    item_lookup = {}
    for item in all_items:
        key = f"{item['source_id']}|{item['link']}"
        item_lookup[key] = item['description']
        
    for frag in fragments:
        key = f"{frag.source_id}|{frag.link}"
        content_map[frag.fragment_id] = item_lookup.get(key, "")

    results = []
    
    # --- Experiment 1: The "Rigorous" Graph (Hyperlinks Only) ---
    exp1 = ExperimentConfig(
        name="Exp 1: Hyperlinks Only (Rigorous)",
        use_hyperlinks=True,
        use_analyst_sequence=False,
        edge_dropout_rate=0.0
    )
    results.append(harness.run_experiment(fragments, content_map, exp1))
    
    # --- Experiment 2: The "Curated" Graph (Analyst Only) ---
    exp2 = ExperimentConfig(
        name="Exp 2: Analyst Sequence Only (Curated)",
        use_hyperlinks=False,
        use_analyst_sequence=True,
        edge_dropout_rate=0.0
    )
    results.append(harness.run_experiment(fragments, content_map, exp2))
    
    # --- Experiment 3: Mixed Graph ---
    exp3 = ExperimentConfig(
        name="Exp 3: Mixed (Hybrid)",
        use_hyperlinks=True,
        use_analyst_sequence=True,
        edge_dropout_rate=0.0
    )
    results.append(harness.run_experiment(fragments, content_map, exp3))
    
    # --- Experiment 4: Stress Test (Dropout 20%) ---
    exp4a = ExperimentConfig(
        name="Exp 4a: Stress Test (Dropout 20%)",
        use_hyperlinks=False,
        use_analyst_sequence=True,
        edge_dropout_rate=0.2
    )
    results.append(harness.run_experiment(fragments, content_map, exp4a))
    
    # --- Experiment 4: Stress Test (Dropout 50%) ---
    exp4b = ExperimentConfig(
        name="Exp 4b: Stress Test (Dropout 50%)",
        use_hyperlinks=False,
        use_analyst_sequence=True,
        edge_dropout_rate=0.5
    )
    results.append(harness.run_experiment(fragments, content_map, exp4b))
    
    # Report Generation
    print("\n\n=== EXPERIMENT RESULTS ===\n")
    print(f"{'Experiment':<40} | {'Edges':<6} | {'Components':<10} | {'Connected?':<10} | {'Max Size':<8}")
    print("-" * 85)
    
    for res in results:
        print(f"{res.config_name:<40} | {res.total_edges:<6} | {res.connected_components:<10} | {str(res.is_connected):<10} | {res.max_component_size:<8}")

if __name__ == "__main__":
    asyncio.run(run_experiments())
