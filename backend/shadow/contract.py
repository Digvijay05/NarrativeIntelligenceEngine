"""
Shadow Ingestion Contracts
==========================

These contracts are specific to the "Shadow Mode" scaling path.
They are physically separate from the canonical contracts to prevents accidental mixing.

INVARIANTS:
1. No mutation of canonical state
2. Raw data preservation (bytes)
3. Explicit polling tick alignment
"""

from __future__ import annotations
from dataclasses import dataclass
from backend.contracts.base import SourceId, Timestamp

@dataclass(frozen=True)
class RawShadowEvent:
    """
    Immutable raw event from Shadow RSS ingestion.
    
    Distinct from Canonical RawIngestionEvent to ensure separation.
    Captures bytes exactly as received on the wire.
    """
    source_id: SourceId
    raw_payload: bytes          # RAW bytes from the wire (UTF-8 or otherwise)
    published_timestamp: Timestamp  # When source claims it occurred
    ingest_timestamp: Timestamp     # When we grabbed it
    poll_tick_id: int              # Logical tick of the shadow system
