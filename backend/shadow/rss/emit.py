from backend.shadow.contract import RawShadowEvent
from backend.shadow.rss.poller import now_utc
from backend.contracts.base import Timestamp

def emit_raw_shadow_event(
    *,
    source_id: str,
    raw_payload: bytes,
    published_timestamp,
    poll_tick_id: int,
) -> RawShadowEvent:
    """
    Create an immutable RawShadowEvent.
    """
    return RawShadowEvent(
        source_id=source_id,
        raw_payload=raw_payload,
        published_timestamp=published_timestamp,
        ingest_timestamp=Timestamp(now_utc()),
        poll_tick_id=poll_tick_id,
    )
