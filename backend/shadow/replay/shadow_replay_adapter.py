from datetime import timezone
import hashlib

from backend.shadow.contract import RawShadowEvent
from backend.contracts.events import RawIngestionEvent
from backend.contracts.base import (
    SourceMetadata, SourceId, Timestamp, SourceTier
)

def adapt_shadow_event(event: RawShadowEvent) -> RawIngestionEvent:
    """
    Adapter ONLY.
    No semantics. No enrichment. No guessing.
    
    Converts RawShadowEvent -> RawIngestionEvent for pipeline consumption.
    """
    # 1. Decode payload (RawIngestionEvent requires str)
    # We assume UTF-8 for now as per skeleton fetcher
    try:
        payload_str = event.raw_payload.decode('utf-8')
    except UnicodeDecodeError:
        payload_str = event.raw_payload.decode('latin-1', errors='replace')

    # 2. Generate Event ID (Deterministic)
    msg_hash = hashlib.sha256(event.raw_payload).hexdigest()
    event_id = f"ev_shadow_{msg_hash[:16]}"
    
    # 3. Construct SourceMetadata
    meta = SourceMetadata(
        source_id=SourceId(event.source_id, SourceTier.SHADOW_RSS.value),
        source_confidence=0.5, # Neutral for shadow
        capture_timestamp=event.ingest_timestamp,
        event_timestamp=event.published_timestamp, # Might be None
        raw_metadata=(("poll_tick", str(event.poll_tick_id)),)
    )

    return RawIngestionEvent(
        event_id=event_id,
        source_metadata=meta,
        raw_payload=payload_str,
        raw_payload_hash=msg_hash,
        ingestion_timestamp=event.ingest_timestamp,
        source_tier=SourceTier.SHADOW_RSS
    )
