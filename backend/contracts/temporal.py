from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import hashlib

from .base import Timestamp, FragmentId
from .events import NormalizedFragment

@dataclass(frozen=True)
class LogSequence:
    """
    Immutable sequence position in the log.
    """
    value: int
    
    def next(self) -> 'LogSequence':
        return LogSequence(self.value + 1)
    
    def __lt__(self, other: 'LogSequence') -> bool:
        return self.value < other.value
    
    def __le__(self, other: 'LogSequence') -> bool:
        return self.value <= other.value

@dataclass(frozen=True)
class LogEntry:
    """
    Immutable log entry.
    INVARIANTS:
    - Once written, never modified.
    - Entries form a hash chain for integrity verification.
    """
    sequence: LogSequence
    fragment: NormalizedFragment
    ingestion_timestamp: Timestamp
    previous_hash: str
    entry_hash: str
    
    @staticmethod
    def create(
        sequence: LogSequence,
        fragment: NormalizedFragment,
        ingestion_timestamp: Timestamp,
        previous_hash: str
    ) -> 'LogEntry':
        """Factory for deterministic entry creation."""
        hash_content = (
            f"{sequence.value}|"
            f"{fragment.fragment_id.value}|"
            f"{ingestion_timestamp.to_iso()}|"
            f"{previous_hash}"
        )
        entry_hash = hashlib.sha256(hash_content.encode()).hexdigest()
        
        return LogEntry(
            sequence=sequence,
            fragment=fragment,
            ingestion_timestamp=ingestion_timestamp,
            previous_hash=previous_hash,
            entry_hash=entry_hash
        )
