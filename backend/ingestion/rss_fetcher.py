"""
RSS Fetcher (Seismic Sensor)
============================

Responsibility: Capture raw bytes from the wire.
Constraint: PERSIST BEFORE PARSE.
"""

import os
import time
import requests
import hashlib
from datetime import datetime, timezone
from typing import Optional, Tuple
from dataclasses import dataclass

from ..contracts.base import Timestamp

@dataclass(frozen=True)
class RawCapsule:
    """
    A sealed capsule of raw data.
    """
    capsule_id: str
    source_id: str
    fetch_timestamp: Timestamp
    http_status: int
    content_hash: str
    file_path: str

class RssFetcher:
    def __init__(self, storage_dir: str):
        self._capsule_dir = os.path.join(storage_dir, "raw_capsules")
        os.makedirs(self._capsule_dir, exist_ok=True)

    def fetch_source(self, source_id: str, url: str) -> Optional[RawCapsule]:
        """
        Fetch URL and persist raw bytes IMMEDIATELY.
        Returns a RawCapsule handle (pointer to disk), NOT the content.
        """
        try:
            # 1. Wire Capture
            # Using a user agent to avoid bot blocking
            headers = {'User-Agent': 'NarrativeIntelligence/1.0 (Research)'}
            response = requests.get(url, headers=headers, timeout=10)
            
            fetch_ts = Timestamp.now()
            
            # 2. Compute Hash (Identity)
            content_bytes = response.content
            content_hash = hashlib.sha256(content_bytes).hexdigest()
            
            # 3. Generate Capsule ID
            # ID = timestamp_source_hash
            ts_str = f"{fetch_ts.value.timestamp():.0f}"
            capsule_id = f"cap_{source_id}_{ts_str}_{content_hash[:8]}"
            
            # 4. PERSIST TO DISK (Sealed)
            filename = f"{capsule_id}.xml"
            file_path = os.path.join(self._capsule_dir, filename)
            
            # Atomic write pattern not strictly necessary for single file but good practice
            with open(file_path, "wb") as f:
                f.write(content_bytes)
                
            return RawCapsule(
                capsule_id=capsule_id,
                source_id=source_id,
                fetch_timestamp=fetch_ts,
                http_status=response.status_code,
                content_hash=content_hash,
                file_path=file_path
            )
            
        except Exception as e:
            print(f"[!] Fetch failed for {source_id}: {e}")
            return None
