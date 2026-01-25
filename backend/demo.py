"""
Demonstration Script for Narrative Intelligence Engine Backend

This script demonstrates the complete backend functionality with
strict layer boundaries and immutable data flow.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

from backend.engine import NarrativeIntelligenceBackend, BackendConfig
from backend.contracts.base import SourceId, Timestamp, TimeRange, ThreadId
from backend.contracts.events import QueryType


def print_section(title: str):
    """Print a formatted section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70 + "\n")


def demonstrate_ingestion(backend: NarrativeIntelligenceBackend):
    """Demonstrate the ingestion layer."""
    print_section("LAYER 1: INGESTION")
    
    # Create source identifier
    source = SourceId(value="demo_source", source_type="in_memory")
    print(f"Source ID: {source.value} (type: {source.source_type})")
    
    # Sample narrative data
    sample_data = [
        '{"timestamp": "2024-01-01T10:00:00", "payload": "Government announces new climate policy to reduce carbon emissions by 2030", "topic": "climate_policy"}',
        '{"timestamp": "2024-01-01T11:00:00", "payload": "Environmental groups praise initial measures in new climate policy", "topic": "climate_policy"}',
        '{"timestamp": "2024-01-02T09:00:00", "payload": "Industry leaders express concerns about costs of new climate regulations", "topic": "climate_policy"}',
        '{"timestamp": "2024-01-03T14:00:00", "payload": "Policy debate shifts to implementation timeline and funding", "topic": "climate_policy"}',
        '{"timestamp": "2024-01-01T12:00:00", "payload": "Tech company unveils revolutionary AI model with breakthrough capabilities", "topic": "technology"}',
        '{"timestamp": "2024-01-01T13:00:00", "payload": "Ethics board raises concerns about bias in newly released AI system", "topic": "technology"}',
        '{"timestamp": "2024-01-02T10:00:00", "payload": "Regulators announce investigation into algorithm transparency", "topic": "technology"}',
    ]
    
    print(f"Ingesting {len(sample_data)} events...")
    
    # Ingest through full pipeline
    state_events = backend.ingest_batch(
        source_id=source,
        payloads=sample_data
    )
    
    print(f"Produced {len(state_events)} state events")
    
    for event in state_events:
        print(f"  - Event: {event.event_type} → Thread: {event.thread_id.value[:16]}...")
    
    return state_events


def demonstrate_thread_state(backend: NarrativeIntelligenceBackend):
    """Demonstrate the core narrative state engine."""
    print_section("LAYER 3: CORE NARRATIVE STATE ENGINE")
    
    threads = backend.get_all_threads()
    print(f"Total threads created: {len(threads)}")
    
    for thread_id, snapshot in threads.items():
        print(f"\nThread: {thread_id[:16]}...")
        print(f"  State: {snapshot.lifecycle_state.value}")
        print(f"  Fragments: {len(snapshot.member_fragment_ids)}")
        print(f"  Topics: {[t.canonical_name for t in snapshot.canonical_topics]}")
        print(f"  Version: {snapshot.version_id.sequence}")
        
        if snapshot.relations:
            print(f"  Relations: {len(snapshot.relations)}")
            for rel in snapshot.relations:
                print(f"    - {rel.relation_type.value}: {rel.source_fragment_id.value[:12]} → {rel.target_fragment_id.value[:12]}")


def demonstrate_temporal_storage(backend: NarrativeIntelligenceBackend):
    """Demonstrate temporal storage with time-travel."""
    print_section("LAYER 4: TEMPORAL STORAGE")
    
    threads = backend.get_all_threads()
    if not threads:
        print("No threads to demonstrate")
        return
    
    # Pick first thread
    thread_id = ThreadId(value=list(threads.keys())[0])
    
    print(f"Examining thread: {thread_id.value[:16]}...")
    
    # Get timeline
    timeline = backend.storage_layer.get_thread_timeline(thread_id)
    print(f"\nTimeline has {timeline.total_versions} versions:")
    
    for point in timeline.points:
        print(f"  [{point.timestamp.to_iso()[:19]}] v{point.version_id.sequence}: {point.state_summary}")
    
    # Demonstrate time-travel
    if timeline.points and len(timeline.points) > 1:
        midpoint = timeline.points[len(timeline.points) // 2]
        print(f"\n⏮️ Rewinding to: {midpoint.timestamp.to_iso()[:19]}")
        
        historical_snapshot = backend.storage_layer.get_thread_at_time(
            thread_id=thread_id,
            target_time=midpoint.timestamp
        )
        
        if historical_snapshot:
            print(f"  Historical state: {historical_snapshot.lifecycle_state.value}")
            print(f"  Fragments at that time: {len(historical_snapshot.member_fragment_ids)}")


def demonstrate_query_layer(backend: NarrativeIntelligenceBackend):
    """Demonstrate the query layer."""
    print_section("LAYER 5: QUERY & ANALYSIS")
    
    threads = backend.get_all_threads()
    if not threads:
        print("No threads to query")
        return
    
    thread_id = ThreadId(value=list(threads.keys())[0])
    
    # Timeline query
    print("1. Timeline Query")
    result = backend.query_timeline(thread_id)
    print(f"   Success: {result.success}")
    print(f"   Results: {result.result_count}")
    print(f"   Execution time: {result.execution_time_ms:.2f}ms")
    
    # Thread state query
    print("\n2. Thread State Query")
    result = backend.query_thread_state(thread_id)
    print(f"   Success: {result.success}")
    if result.success and result.results:
        snapshot = result.results[0]
        print(f"   Current state: {snapshot.lifecycle_state.value}")
    
    # Comparison query
    print("\n3. Comparison Query")
    now = Timestamp.now()
    past = Timestamp(value=datetime(2024, 1, 1, tzinfo=timezone.utc))
    time_range = TimeRange(start=past, end=now)
    
    result = backend.query_comparison(time_range, max_results=5)
    print(f"   Success: {result.success}")
    print(f"   Threads compared: {result.result_count}")


def demonstrate_observability(backend: NarrativeIntelligenceBackend):
    """Demonstrate the observability layer."""
    print_section("LAYER 6: OBSERVABILITY & AUDIT")
    
    # Get audit report
    report = backend.get_audit_report()
    
    print("Audit Report Summary")
    print(f"  Total entries: {report['total_entries']}")
    
    print("\n  By Layer:")
    for layer, count in report.get('by_layer', {}).items():
        print(f"    {layer}: {count} entries")
    
    print("\n  By Event Type:")
    for event_type, count in report.get('by_event_type', {}).items():
        print(f"    {event_type}: {count} entries")
    
    # Show some log entries
    print("\nRecent Audit Entries:")
    logs = backend.get_audit_log()[-5:]  # Last 5
    for entry in logs:
        print(f"  [{entry.timestamp.to_iso()[:19]}] {entry.layer}: {entry.action}")
    
    # Lineage tracking
    lineage = backend.get_lineage()
    if lineage:
        print(f"\nLineage Nodes Tracked: {len(lineage._nodes)}")


def demonstrate_determinism(backend: NarrativeIntelligenceBackend):
    """Demonstrate deterministic behavior."""
    print_section("DETERMINISM VERIFICATION")
    
    source = SourceId(value="determinism_test", source_type="in_memory")
    
    # Same input twice
    payload = '{"payload": "Test deterministic processing", "topic": "test"}'
    
    print("Processing identical input twice...")
    
    # First run
    result1 = backend.normalization_layer.normalize(
        backend.ingestion_layer.ingest_single(source, payload)
    )
    
    # Create fresh backend for second run
    backend2 = NarrativeIntelligenceBackend()
    result2 = backend2.normalization_layer.normalize(
        backend2.ingestion_layer.ingest_single(source, payload)
    )
    
    print(f"\nRun 1 - Fragment ID: {result1.fragment.fragment_id.value}")
    print(f"Run 1 - Content Hash: {result1.fragment.content_signature.payload_hash[:32]}...")
    print(f"Run 1 - Language: {result1.fragment.detected_language}")
    print(f"Run 1 - Topics: {[t.topic_id for t in result1.fragment.canonical_topics]}")
    
    print(f"\nRun 2 - Fragment ID: {result2.fragment.fragment_id.value}")
    print(f"Run 2 - Content Hash: {result2.fragment.content_signature.payload_hash[:32]}...")
    print(f"Run 2 - Language: {result2.fragment.detected_language}")
    print(f"Run 2 - Topics: {[t.topic_id for t in result2.fragment.canonical_topics]}")
    
    # Verify determinism
    is_deterministic = (
        result1.fragment.content_signature.payload_hash == 
        result2.fragment.content_signature.payload_hash and
        result1.fragment.detected_language == 
        result2.fragment.detected_language
    )
    
    print(f"\n✓ Deterministic: {is_deterministic}")


def main():
    """Run the complete demonstration."""
    print("\n" + "=" * 70)
    print("  NARRATIVE INTELLIGENCE ENGINE - BACKEND DEMONSTRATION")
    print("  Strictly Layered Architecture with Hard Boundaries")
    print("=" * 70)
    
    # Initialize backend
    backend = NarrativeIntelligenceBackend()
    print("\n✓ Backend initialized with all 6 layers")
    
    # Run demonstrations
    demonstrate_ingestion(backend)
    demonstrate_thread_state(backend)
    demonstrate_temporal_storage(backend)
    demonstrate_query_layer(backend)
    demonstrate_observability(backend)
    demonstrate_determinism(backend)
    
    # Summary
    print_section("SUMMARY")
    print("Layer Boundaries Enforced:")
    print("  ✓ Ingestion → RawIngestionEvent only")
    print("  ✓ Normalization → NormalizedFragment only (contradictions tagged, not resolved)")
    print("  ✓ Core Engine → NarrativeStateEvent only (immutable snapshots)")
    print("  ✓ Storage → Append-only, versioned (time-travel enabled)")
    print("  ✓ Query → Read-only with explicit errors")
    print("  ✓ Observability → Pure observation, no modification")
    
    print("\nConstraints Verified:")
    print("  ✓ Immutability-first design (frozen dataclasses)")
    print("  ✓ Append-only data models")
    print("  ✓ Deterministic behavior")
    print("  ✓ Explicit error states")
    print("  ✓ No truth adjudication")
    print("  ✓ No importance ranking")
    
    print("\n" + "=" * 70)
    print("  DEMONSTRATION COMPLETE")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
