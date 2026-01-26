"""
End-to-End Integration Demo

Verifies the complete pipeline:
Ingestion (RSS) → Backend (Narrative Engine) → Model (Adapter) → Frontend (DTOs)
"""

import sys
import os
import json
import shutil
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Monkeypatch RSSFetcher to support file:// scheme
import ingestion.service
from ingestion.fetcher import RSSFetcher
from ingestion.contracts import FetchResult, RawRSSPayload, FetchStatus

class MockRSSFetcher(RSSFetcher):
    def fetch_sync(self, source):
        # Handle file URI scheme for local demo
        if source.url.startswith("file:///"):
            try:
                # Extract path (very naive handling for demo)
                file_path = source.url.replace("file:///", "")
                
                with open(file_path, "rb") as f:
                    content = f.read()
                
                completed_at = datetime.utcnow()
                
                raw_payload = RawRSSPayload.create(
                    source_id=source.source_id,
                    url=source.url,
                    http_status=200,
                    raw_bytes=content,
                    headers={'content-type': 'application/rss+xml'},
                    fetched_at=completed_at
                )
                
                items = self._parse_rss(
                    raw_bytes=content,
                    source_id=source.source_id,
                    payload_id=raw_payload.payload_id,
                    fetched_at=completed_at
                )
                
                result = FetchResult(
                    result_id=self._generate_result_id(source, completed_at),
                    source_id=source.source_id,
                    url=source.url,
                    attempted_at=completed_at,
                    completed_at=completed_at,
                    status=FetchStatus.SUCCESS,
                    payload_id=raw_payload.payload_id,
                    items_count=len(items)
                )
                return result, raw_payload, items
                
            except Exception as e:
                print(f"Mock fetch failed: {e}")
                import traceback
                traceback.print_exc()
                # Fallback to failure
                return super()._generic_error_result(source, datetime.utcnow(), e), None, []
                
        return super().fetch_sync(source)

# Apply patch
ingestion.service.RSSFetcher = MockRSSFetcher

from ingestion.service import create_service
from backend.engine import NarrativeIntelligenceBackend
from backend.contracts.base import SourceId, Timestamp, ThreadId
from backend.ingestion import IngestionConfig
from adapter.facade import BackendModelFacade
from frontend.mapper import DTOMapper

def setup_environment():
    """Setup clean environment for demo."""
    data_dir = Path("./demo_data")
    if data_dir.exists():
        shutil.rmtree(data_dir)
    data_dir.mkdir(parents=True)
    return data_dir

def run_ingestion_layer(data_dir: Path):
    """Layer 1: Fetch from RSS feeds."""
    print("\n" + "="*60)
    print("LAYER 1: EXTERNAL INGESTION (RSS)")
    print("="*60)
    
    # Create local mock RSS file
    rss_path = data_dir / "mock_feed.xml"
    with open(rss_path, "w") as f:
        f.write("""<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>Local Demo Feed</title>
  <link>http://localhost</link>
  <description>Demo Feed</description>
  <item>
    <title>AI Safety Protocol Announced</title>
    <link>http://localhost/article1</link>
    <description>Global leaders agree on new safety standards for AI development, emphasizing transparency and alignment.</description>
    <author>Tech Reporter</author>
    <pubDate>Mon, 01 Jan 2024 12:00:00 GMT</pubDate>
  </item>
  <item>
    <title>New Climate Model Predictions</title>
    <link>http://localhost/article2</link>
    <description>Updated climate models suggest faster warming trends unless immediate action is taken.</description>
    <author>Science Editor</author>
    <pubDate>Mon, 01 Jan 2024 14:00:00 GMT</pubDate>
  </item>
</channel>
</rss>""")

    # Initialize ingestion service with local feed config
    config_path = Path("config/feeds.json")
    config_path.parent.mkdir(exist_ok=True)
    with open(config_path, "w") as f:
        json.dump({
            "feeds": {
                "national_news": {
                    "tier": 1,
                    "sources": [
                        {
                            "id": "local_demo",
                            "url": f"file:///{rss_path.absolute().as_posix()}",
                            "category": "national_news",
                            "name": "Local Demo Feed",
                            "enabled": True
                        }
                    ]
                }
            }
        }, f)
            
    service = create_service(str(data_dir))
    
    print("Polling feeds...")
    batch = service.poll_all_sync()
    
    total_items = sum(r.items_count for r in batch.results)
    success_feeds = batch.success_count
    failed_feeds = batch.failure_count
    
    print(f"Fetched {total_items} items from {success_feeds} feeds")
    if failed_feeds > 0:
        print(f"Failed feeds: {failed_feeds}")
        
    # Retrieve items from store for the demo
    all_items = []
    for result in batch.results:
        if result.success and result.items_count > 0:
            items = service._store.get_recent_items(result.source_id, limit=result.items_count)
            all_items.extend(items)
            
    return all_items

def run_backend_ingestion(backend: NarrativeIntelligenceBackend, items):
    """Layer 2: Ingest into Narrative Engine."""
    print("\n" + "="*60)
    print("LAYER 2: BACKEND INGESTION")
    print("="*60)
    
    payloads = []
    timestamps = []
    
    for item in items:
        # Dictionary from sqlite row
        # Format as JSON for normalization layer
        payload_dict = {
            "title": item['title'],
            "payload": f"{item['title']}\n\n{item['description']}",
            "url": item['link'],
            "author": item['author'],
            "feed_id": item['source_id']
        }
        payloads.append(json.dumps(payload_dict))
        
        ts = None
        if item.get('published_at'):
            try:
                ts = Timestamp.from_iso(item['published_at'])
            except:
                pass
        timestamps.append(ts)
    
    if not payloads:
        print("No items to ingest.")
        return
        
    print(f"Ingesting {len(payloads)} items into Backend Engine...")
    
    source_id = SourceId("rss_aggregator", "rss")
    
    events = backend.ingest_batch(
        source_id=source_id,
        payloads=payloads,
        event_timestamps=timestamps
    )
    print(events)
    print(f"Produced {len(events)} narrative state events")
    for evt in events[:5]:
        print(f"  - Event: {evt.event_type} | Thread: {evt.thread_id.value[:8]}...")

def run_backend_queries(backend: NarrativeIntelligenceBackend):
    """Layer 3: Query Backend State."""
    print("\n" + "="*60)
    print("LAYER 3: NARRATIVE STATE MAPPING")
    print("="*60)
    
    threads = backend.get_all_threads()
    print(f"Active Threads: {len(threads)}")
    
    demo_thread = None
    
    for tid, snapshot in threads.items():
        print(f"\nThread: {tid[:8]}...")
        print(f"  Fragments: {len(snapshot.member_fragment_ids)}")
        print(f"  Topics: {[t.canonical_name for t in snapshot.canonical_topics]}")
        
        if len(snapshot.member_fragment_ids) > 0:
            demo_thread = snapshot
            
    return demo_thread

def run_model_adapter(backend: NarrativeIntelligenceBackend, facade: BackendModelFacade, thread_snapshot):
    """Layer 4: Model Analysis via Adapter."""
    if not thread_snapshot:
        return
        
    print("\n" + "="*60)
    print("LAYER 4: MODEL ADAPTER & ANALYSIS")
    print("="*60)
    
    tid = thread_snapshot.thread_id.value
    print(f"Analyzing Thread: {tid[:8]}...")
    
    fragment_ids = [f.value for f in thread_snapshot.member_fragment_ids]
    
    result = facade.analyze_thread(
        thread_id=tid,
        thread_version=thread_snapshot.version_id.sequence,
        thread_lifecycle=thread_snapshot.lifecycle_state.value,
        fragment_ids=fragment_ids,
        fragment_contents=["Dummy content"] * len(fragment_ids),
        fragment_timestamps=[datetime.utcnow()] * len(fragment_ids),
        task_type="divergence_scoring"
    )
    
    print(f"Analysis Success: {result.success}")
    print(f"Processing Time: {result.processing_time_ms:.2f}ms")
    if result.overlay:
        print(f"Overlay ID: {result.overlay.overlay_id}")
        print(f"Scores: {len(result.overlay.scores)}")
        print(f"Annotations: {len(result.overlay.annotations)}")

def run_frontend_mapping(backend: NarrativeIntelligenceBackend, thread_snapshot):
    """Layer 5: Frontend DTO Mapping."""
    if not thread_snapshot:
        return
        
    print("\n" + "="*60)
    print("LAYER 5: FRONTEND DTO CONTRACT")
    print("="*60)
    
    mapper = DTOMapper()
    
    tid = thread_snapshot.thread_id.value
    dto = mapper.map_thread(
        thread_id=tid,
        thread_version=thread_snapshot.version_id.sequence,
        lifecycle=thread_snapshot.lifecycle_state.value,
        start_timestamp=datetime.utcnow(),
        end_timestamp=None,
        topic_ids=[t.topic_id for t in thread_snapshot.canonical_topics],
        segment_ids=["seg_1"],
        display_label=f"Thread {tid[:8]}"
    )
    
    print(f"DTO Generated: {type(dto).__name__}")
    print(f"Version: {dto.dto_version}")
    print(f"Thread ID: {dto.thread_id}")
    print(f"Lifecycle: {dto.lifecycle_state}")
    print(f"Availability: {dto.availability}")
    
    try:
        dto.thread_id = "modified"
        print("❌ FAILED: DTO is mutable!")
    except:
        print("✓ PASS: DTO is immutable")

def main():
    data_dir = setup_environment()
    
    try:
        backend = NarrativeIntelligenceBackend()
        model_facade = BackendModelFacade()
        
        batch = run_ingestion_layer(data_dir)
        run_backend_ingestion(backend, batch)
        demo_thread = run_backend_queries(backend)
        
        if demo_thread:
            run_model_adapter(backend, model_facade, demo_thread)
            run_frontend_mapping(backend, demo_thread)
        else:
            print("\n⚠ No threads created, skipping analysis/mapping.")
            
    finally:
        if data_dir.exists():
            shutil.rmtree(data_dir)

if __name__ == "__main__":
    main()
