"""
Immutable Event Log
===================

Append-only fragment storage with sequence numbering.

INVARIANTS:
- No updates or deletes - append only
- Every entry has monotonic sequence number
- Hash chain for integrity verification
- Deterministic replay: same entries → same hash

This is the SOURCE OF TRUTH for all narrative state.
State is DERIVED from this log, never stored separately.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Iterator, Optional, List, Tuple
from datetime import datetime, timezone
import hashlib
import json

from ..contracts.base import Timestamp, FragmentId, ThreadId, Error, ErrorCode
from ..contracts.events import NormalizedFragment
from ..contracts.temporal import LogSequence, LogEntry


@dataclass(frozen=True)
class LogState:
    """
    Immutable snapshot of log state.
    
    WHY THIS TYPE:
    - Captures log state at a point in time
    - Enables deterministic replay verification
    """
    head_sequence: LogSequence
    head_hash: str
    entry_count: int
    
    @staticmethod
    def empty() -> 'LogState':
        return LogState(
            head_sequence=LogSequence(0),
            head_hash="",
            entry_count=0
        )


class ImmutableEventLog:
    """
    Append-only event log.
    
    GUARANTEES:
    ===========
    1. NO updates - entries are immutable once written
    2. NO deletes - log only grows
    3. Deterministic - same entries in same order → same state
    4. Verifiable - hash chain ensures integrity
    
    EXPLICIT FAILURE STATES:
    - TEMPORAL_AMBIGUITY: Fragment timestamp conflicts with sequence
    - STRUCTURAL_INCONSISTENCY: Hash chain broken
    """
    
    def __init__(self):
        # Internal storage (append-only list)
        self._entries: List[LogEntry] = []
        self._sequence_counter = LogSequence(0)
        self._head_hash = ""
        
        # Index for efficient lookup (derived, not authoritative)
        self._fragment_index: dict[str, LogSequence] = {}
        self._temporal_index: List[Tuple[Timestamp, LogSequence]] = []
    
    @property
    def state(self) -> LogState:
        """Get current log state (immutable snapshot)."""
        return LogState(
            head_sequence=self._sequence_counter,
            head_hash=self._head_hash,
            entry_count=len(self._entries)
        )
    
    def append(self, fragment: NormalizedFragment) -> LogEntry:
        """
        Append fragment to log.
        
        This is the ONLY write operation.
        Returns the created entry for caller reference.
        """
        ingestion_timestamp = Timestamp.now()
        
        # Create new sequence
        new_sequence = self._sequence_counter.next()
        
        # Create entry with hash chain
        entry = LogEntry.create(
            sequence=new_sequence,
            fragment=fragment,
            ingestion_timestamp=ingestion_timestamp,
            previous_hash=self._head_hash
        )
        
        # Append to log (this is the only mutation)
        self._entries.append(entry)
        self._sequence_counter = new_sequence
        self._head_hash = entry.entry_hash
        
        # Update indices
        self._fragment_index[fragment.fragment_id.value] = new_sequence
        self._temporal_index.append((ingestion_timestamp, new_sequence))
        
        return entry
    
    def load_verified_entry(self, entry: LogEntry) -> bool:
        """
        Load an existing entry from storage.
        
        VERIFIES:
        1. Sequence is monotonic (next in line)
        2. Previous hash matches current head
        3. Entry hash is valid for its content
        
        Returns True if loaded, False (and raises or logs) if invalid.
        Used for hydration from disk.
        """
        # 1. Check sequence
        expected_seq = self._sequence_counter.next()
        # If loading first entry (seq 1) and we are at 0
        if self._sequence_counter.value == 0 and entry.sequence.value == 1:
            pass
        elif entry.sequence.value != expected_seq.value:
            # Maybe we are loading out of order or gap?
            raise ValueError(f"Invalid sequence load: expected {expected_seq.value}, got {entry.sequence.value}")
            
        # 2. Check hash chain
        if entry.previous_hash != self._head_hash:
            raise ValueError(f"Broken hash chain at {entry.sequence.value}: prev {entry.previous_hash} != head {self._head_hash}")
        
        # 3. Verify entry hash (recompute)
        hash_content = (
            f"{entry.sequence.value}|"
            f"{entry.fragment.fragment_id.value}|"
            f"{entry.ingestion_timestamp.to_iso()}|"
            f"{entry.previous_hash}"
        )
        computed_hash = hashlib.sha256(hash_content.encode()).hexdigest()
        if computed_hash != entry.entry_hash:
            raise ValueError(f"Corrupt entry at {entry.sequence.value}: Hash mismatch")
            
        # All good - load it
        self._entries.append(entry)
        self._sequence_counter = entry.sequence
        self._head_hash = entry.entry_hash
        
        # Update indices
        self._fragment_index[entry.fragment.fragment_id.value] = entry.sequence
        self._temporal_index.append((entry.ingestion_timestamp, entry.sequence))
        
        return True

    def replay(
        self,
        from_seq: Optional[LogSequence] = None,
        until_seq: Optional[LogSequence] = None
    ) -> Iterator[LogEntry]:
        """
        Replay entries in sequence order.
        
        This is the primary read operation for state derivation.
        
        Args:
            from_seq: Start from this sequence (inclusive), None = start
            until_seq: Stop at this sequence (inclusive), None = end
        """
        start = (from_seq.value if from_seq else 1)
        end = (until_seq.value if until_seq else len(self._entries))
        
        for entry in self._entries:
            if entry.sequence.value < start:
                continue
            if entry.sequence.value > end:
                break
            yield entry
    
    def get_entry(self, sequence: LogSequence) -> Optional[LogEntry]:
        """Get specific entry by sequence number."""
        if sequence.value < 1 or sequence.value > len(self._entries):
            return None
        return self._entries[sequence.value - 1]
    
    def get_entry_by_fragment(self, fragment_id: FragmentId) -> Optional[LogEntry]:
        """Get entry containing specific fragment."""
        seq = self._fragment_index.get(fragment_id.value)
        if seq:
            return self.get_entry(seq)
        return None
    
    def verify_integrity(self) -> Tuple[bool, Optional[Error]]:
        """
        Verify hash chain integrity.
        
        Returns (is_valid, error) tuple.
        Error contains details if integrity check fails.
        """
        if not self._entries:
            return (True, None)
        
        expected_previous = ""
        
        for entry in self._entries:
            if entry.previous_hash != expected_previous:
                return (False, Error(
                    code=ErrorCode.STRUCTURAL_INCONSISTENCY,
                    message=f"Hash chain broken at sequence {entry.sequence.value}",
                    timestamp=datetime.now(timezone.utc),
                    context=(
                        ("expected_hash", expected_previous),
                        ("actual_hash", entry.previous_hash),
                    )
                ))
            expected_previous = entry.entry_hash
        
        return (True, None)
    
    def compute_state_hash(self, at_sequence: Optional[LogSequence] = None) -> str:
        """
        Compute deterministic state hash at given sequence.
        
        Same entries at same sequence → same hash.
        This is the core determinism guarantee.
        """
        if at_sequence is None:
            at_sequence = self._sequence_counter
        
        entry = self.get_entry(at_sequence)
        if entry:
            return entry.entry_hash
        return ""
    
    def find_temporal_position(self, event_timestamp: Timestamp) -> LogSequence:
        """
        Find where a fragment with given timestamp should be positioned.
        
        For late arrivals, returns the sequence AFTER which this fragment
        should logically exist (based on event timestamp, not ingestion).
        """
        # Binary search through temporal index
        target = event_timestamp.value
        
        left, right = 0, len(self._temporal_index)
        
        while left < right:
            mid = (left + right) // 2
            if self._temporal_index[mid][0].value < target:
                left = mid + 1
            else:
                right = mid
        
        if left == 0:
            return LogSequence(0)
        return self._temporal_index[left - 1][1]
