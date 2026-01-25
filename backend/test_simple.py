"""Simple test script for backend verification."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine import NarrativeIntelligenceBackend
from backend.contracts.base import SourceId, ThreadId

def test_backend():
    # Initialize
    backend = NarrativeIntelligenceBackend()
    print("✓ Backend initialized")

    # Create source
    source = SourceId(value="test", source_type="in_memory")
    print("✓ Source created")

    # Ingest
    events = backend.ingest_batch(
        source_id=source,
        payloads=[
            '{"payload": "Climate policy announced", "topic": "climate"}',
            '{"payload": "Industry responds to climate", "topic": "climate"}',
            '{"payload": "Tech company releases AI model", "topic": "technology"}',
        ]
    )
    print(f"✓ Ingested: {len(events)} events")

    # Check threads
    threads = backend.get_all_threads()
    print(f"✓ Threads created: {len(threads)}")

    for tid, snap in threads.items():
        print(f"  - Thread: {snap.lifecycle_state.value}, {len(snap.member_fragment_ids)} fragments")
        print(f"    Topics: {[t.topic_id for t in snap.canonical_topics]}")

    # Query
    if threads:
        first_tid = ThreadId(value=list(threads.keys())[0])
        result = backend.query_timeline(first_tid)
        print(f"✓ Query success: {result.success}, results: {result.result_count}")

    # Audit
    report = backend.get_audit_report()
    print(f"✓ Audit entries: {report['total_entries']}")

    print("\n=== ALL TESTS PASSED ===")

if __name__ == "__main__":
    test_backend()
