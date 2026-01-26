"""
Version Lineage
===============

Thread version tracking for temporal evolution.

INVARIANT: Every derived state produces a new version.
Versions form a DAG (directed acyclic graph) with explicit lineage.

WHY VERSIONING:
- Threads are views, not entities
- Same thread at different sequences = different versions
- Branching creates parallel version lineages
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
import hashlib

from ..contracts.base import ThreadId, VersionId, Timestamp

from .event_log import LogSequence


@dataclass(frozen=True)
class VersionedThread:
    """
    A thread version tied to a specific log sequence.
    
    Same thread_id at different sequences produces different versions.
    This captures the temporal evolution of threads.
    """
    thread_id: ThreadId
    version_id: VersionId
    at_sequence: LogSequence
    state_hash: str
    
    # Lineage
    parent_version_id: Optional[VersionId] = None
    
    # Metadata
    created_at: Timestamp = field(default_factory=Timestamp.now)
    fragment_count: int = 0
    
    def is_descendant_of(self, ancestor: VersionId) -> bool:
        """Check if this version descends from ancestor."""
        return self.parent_version_id == ancestor


@dataclass(frozen=True)
class ThreadLineage:
    """
    Complete version lineage for a thread.
    
    Captures how a thread evolved over log sequences.
    Branches are explicit (divergence creates new lineage root).
    """
    thread_id: ThreadId
    versions: Tuple[VersionedThread, ...]
    
    @property
    def latest(self) -> Optional[VersionedThread]:
        """Get latest version by sequence."""
        if not self.versions:
            return None
        return max(self.versions, key=lambda v: v.at_sequence.value)
    
    @property
    def root(self) -> Optional[VersionedThread]:
        """Get root version (first in lineage)."""
        if not self.versions:
            return None
        return min(self.versions, key=lambda v: v.at_sequence.value)
    
    def at_sequence(self, seq: LogSequence) -> Optional[VersionedThread]:
        """Get version at specific sequence (or closest earlier)."""
        candidates = [v for v in self.versions if v.at_sequence <= seq]
        if not candidates:
            return None
        return max(candidates, key=lambda v: v.at_sequence.value)


class VersionTracker:
    """
    Tracks version lineage for all threads.
    
    GUARANTEES:
    - Every state derivation produces version record
    - Version lineage is append-only
    - Same sequence always maps to same version
    """
    
    def __init__(self):
        self._lineages: Dict[str, List[VersionedThread]] = {}
        self._version_index: Dict[str, VersionedThread] = {}
    
    def record_version(
        self,
        thread_id: ThreadId,
        at_sequence: LogSequence,
        state_hash: str,
        fragment_count: int
    ) -> VersionedThread:
        """
        Record a new version from state derivation.
        
        Links to previous version in lineage automatically.
        """
        # Get previous version if exists
        lineage = self._lineages.get(thread_id.value, [])
        parent_version_id = lineage[-1].version_id if lineage else None
        
        # Generate version ID
        version_id = VersionId.generate(
            entity_id=thread_id.value,
            sequence=at_sequence.value,
            parent=parent_version_id.value if parent_version_id else None
        )
        
        # Create version
        version = VersionedThread(
            thread_id=thread_id,
            version_id=version_id,
            at_sequence=at_sequence,
            state_hash=state_hash,
            parent_version_id=parent_version_id,
            fragment_count=fragment_count
        )
        
        # Append to lineage
        if thread_id.value not in self._lineages:
            self._lineages[thread_id.value] = []
        self._lineages[thread_id.value].append(version)
        
        # Index by version ID
        self._version_index[version_id.value] = version
        
        return version
    
    def get_lineage(self, thread_id: ThreadId) -> ThreadLineage:
        """Get complete lineage for a thread."""
        versions = self._lineages.get(thread_id.value, [])
        return ThreadLineage(
            thread_id=thread_id,
            versions=tuple(versions)
        )
    
    def get_version(self, version_id: VersionId) -> Optional[VersionedThread]:
        """Get specific version by ID."""
        return self._version_index.get(version_id.value)
    
    def get_all_thread_ids(self) -> Tuple[ThreadId, ...]:
        """Get all thread IDs with recorded versions."""
        return tuple(
            ThreadId(value=tid) for tid in self._lineages.keys()
        )
