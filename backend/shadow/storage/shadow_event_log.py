import json
import os
from datetime import datetime, timezone
from typing import List
from backend.shadow.contract import RawShadowEvent
from backend.contracts.base import Timestamp

class ShadowEventLog:
    """
    Append-only log for shadow events.
    Persists to local JSONL file for forensic replay.
    """
    
    FILE_PATH = "data/shadow/events.jsonl"

    def __init__(self):
        self._events: List[RawShadowEvent] = []
        self._ensure_dir()
        self._load()

    def _ensure_dir(self):
        os.makedirs(os.path.dirname(self.FILE_PATH), exist_ok=True)

    def append(self, event: RawShadowEvent) -> None:
        self._events.append(event)
        # Append to file
        with open(self.FILE_PATH, "a", encoding="utf-8") as f:
            # Serialize (simple JSON for skeleton)
            # Need to handle bytes (raw_payload) and timestamps
            record = {
                "source_id": event.source_id,
                # Store bytes as hex or latin-1? Hex is safer.
                "raw_payload_hex": event.raw_payload.hex(),
                "published_timestamp": event.published_timestamp.to_iso() if event.published_timestamp else None,
                "ingest_timestamp": event.ingest_timestamp.to_iso(),
                "poll_tick_id": event.poll_tick_id
            }
            f.write(json.dumps(record) + "\n")

    def all_events(self) -> List[RawShadowEvent]:
        return list(self._events)
        
    def _load(self):
        if not os.path.exists(self.FILE_PATH):
            return
            
        with open(self.FILE_PATH, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip(): continue
                try:
                    record = json.loads(line)
                    event = RawShadowEvent(
                        source_id=record["source_id"],
                        raw_payload=bytes.fromhex(record["raw_payload_hex"]),
                        published_timestamp=Timestamp.from_iso(record["published_timestamp"]) if record["published_timestamp"] else None,
                        ingest_timestamp=Timestamp.from_iso(record["ingest_timestamp"]),
                        poll_tick_id=record["poll_tick_id"]
                    )
                    self._events.append(event)
                except Exception:
                    continue
