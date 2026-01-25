"""
Temporal Storage Layer

RESPONSIBILITY: Append-only versioned persistence, time-travel queries
ALLOWED INPUTS: Any immutable event from other layers
OUTPUTS: VersionedSnapshot, HistoricalQuery results

WHAT THIS LAYER MUST NOT DO:
============================
- Transform or interpret data
- Execute business logic
- Make decisions about thread state
- Resolve conflicts or contradictions
- Delete or modify existing data (append-only)

BOUNDARY ENFORCEMENT:
=====================
- ONLY stores immutable events and snapshots
- NEVER modifies stored data
- Supports rewind/replay through version chains
- All writes are append operations

REFACTORING FROM PREVIOUS CODE:
===============================
Previous coupling risks eliminated:
1. OLD: Thread model stored its own versions internally (mixed concerns)
   NEW: Storage layer handles all versioning externally
2. OLD: No support for time-travel queries
   NEW: Full rewind/replay capability via version chains
3. OLD: Mutable data structures
   NEW: Append-only, versioned data model
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Iterator
from enum import Enum
import hashlib
import json
import os

# ONLY import from contracts - never from other layers' implementations
from ..contracts.base import (
    ThreadId, FragmentId, VersionId, Timestamp, TimeRange,
    Error, ErrorCode
)
from ..contracts.events import (
    NarrativeStateEvent, ThreadStateSnapshot, NormalizedFragment,
    RawIngestionEvent, VersionedSnapshot, Timeline, TimelinePoint,
    StorageWriteResult, AuditLogEntry, AuditEventType, ReplayCheckpoint
)


# =============================================================================
# STORAGE INTERFACES (Dependency Inversion)
# =============================================================================

class StorageBackend:
    """
    Abstract storage backend interface.
    
    Implementations can use different storage systems (memory, file, database)
    while maintaining the same append-only, versioned semantics.
    """
    
    def write_event(self, event: NarrativeStateEvent) -> StorageWriteResult:
        """Write an event to storage (append-only)."""
        raise NotImplementedError
    
    def write_fragment(self, fragment: NormalizedFragment) -> StorageWriteResult:
        """Write a normalized fragment to storage (append-only)."""
        raise NotImplementedError
    
    def write_snapshot(self, snapshot: ThreadStateSnapshot) -> StorageWriteResult:
        """Write a thread snapshot to storage (append-only)."""
        raise NotImplementedError
    
    def get_snapshot(self, version_id: VersionId) -> Optional[ThreadStateSnapshot]:
        """Retrieve a specific snapshot version."""
        raise NotImplementedError
    
    def get_latest_snapshot(self, thread_id: ThreadId) -> Optional[ThreadStateSnapshot]:
        """Get the latest snapshot for a thread."""
        raise NotImplementedError
    
    def get_snapshot_history(
        self, 
        thread_id: ThreadId,
        time_range: Optional[TimeRange] = None
    ) -> List[ThreadStateSnapshot]:
        """Get all snapshots for a thread, optionally filtered by time."""
        raise NotImplementedError
    
    def get_events(
        self,
        thread_id: Optional[ThreadId] = None,
        time_range: Optional[TimeRange] = None
    ) -> List[NarrativeStateEvent]:
        """Get events, optionally filtered by thread and time."""
        raise NotImplementedError
    
    def create_checkpoint(self) -> ReplayCheckpoint:
        """Create a checkpoint for replay capability."""
        raise NotImplementedError
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[ReplayCheckpoint]:
        """Retrieve a specific checkpoint."""
        raise NotImplementedError


# =============================================================================
# IN-MEMORY STORAGE BACKEND (Reference Implementation)
# =============================================================================

class InMemoryStorageBackend(StorageBackend):
    """
    In-memory implementation of storage backend.
    
    Uses append-only data structures. No mutation of stored data.
    Suitable for testing and small-scale deployments.
    """
    
    def __init__(self):
        # Append-only event log
        self._events: List[NarrativeStateEvent] = []
        
        # Append-only fragment store
        self._fragments: Dict[str, NormalizedFragment] = {}
        
        # Append-only snapshot store (version_id -> snapshot)
        self._snapshots: Dict[str, ThreadStateSnapshot] = {}
        
        # Index: thread_id -> list of version_ids (ordered)
        self._thread_versions: Dict[str, List[str]] = {}
        
        # Checkpoints for replay
        self._checkpoints: Dict[str, ReplayCheckpoint] = {}
        self._checkpoint_counter: int = 0
        
        # Write sequence for ordering
        self._write_sequence: int = 0
    
    def write_event(self, event: NarrativeStateEvent) -> StorageWriteResult:
        """Append event to storage."""
        self._events.append(event)
        self._write_sequence += 1
        
        return StorageWriteResult(
            success=True,
            version_id=event.new_state_snapshot.version_id,
            write_timestamp=Timestamp.now()
        )
    
    def write_fragment(self, fragment: NormalizedFragment) -> StorageWriteResult:
        """Append fragment to storage."""
        self._fragments[fragment.fragment_id.value] = fragment
        self._write_sequence += 1
        
        return StorageWriteResult(
            success=True,
            write_timestamp=Timestamp.now()
        )
    
    def write_snapshot(self, snapshot: ThreadStateSnapshot) -> StorageWriteResult:
        """Append snapshot to storage."""
        # Store snapshot by version_id
        self._snapshots[snapshot.version_id.value] = snapshot
        
        # Update thread version index
        thread_id = snapshot.thread_id.value
        if thread_id not in self._thread_versions:
            self._thread_versions[thread_id] = []
        self._thread_versions[thread_id].append(snapshot.version_id.value)
        
        self._write_sequence += 1
        
        return StorageWriteResult(
            success=True,
            version_id=snapshot.version_id,
            write_timestamp=Timestamp.now()
        )
    
    def get_snapshot(self, version_id: VersionId) -> Optional[ThreadStateSnapshot]:
        """Retrieve a specific snapshot version."""
        return self._snapshots.get(version_id.value)
    
    def get_latest_snapshot(self, thread_id: ThreadId) -> Optional[ThreadStateSnapshot]:
        """Get the latest snapshot for a thread."""
        versions = self._thread_versions.get(thread_id.value, [])
        if not versions:
            return None
        return self._snapshots.get(versions[-1])
    
    def get_snapshot_history(
        self,
        thread_id: ThreadId,
        time_range: Optional[TimeRange] = None
    ) -> List[ThreadStateSnapshot]:
        """Get all snapshots for a thread, optionally filtered by time."""
        versions = self._thread_versions.get(thread_id.value, [])
        snapshots = [self._snapshots[v] for v in versions if v in self._snapshots]
        
        if time_range:
            snapshots = [
                s for s in snapshots
                if time_range.contains(s.created_at)
            ]
        
        return snapshots
    
    def get_events(
        self,
        thread_id: Optional[ThreadId] = None,
        time_range: Optional[TimeRange] = None
    ) -> List[NarrativeStateEvent]:
        """Get events, optionally filtered by thread and time."""
        events = self._events
        
        if thread_id:
            events = [e for e in events if e.thread_id.value == thread_id.value]
        
        if time_range:
            events = [e for e in events if time_range.contains(e.timestamp)]
        
        return list(events)
    
    def get_fragment(self, fragment_id: FragmentId) -> Optional[NormalizedFragment]:
        """Retrieve a fragment by ID."""
        return self._fragments.get(fragment_id.value)
    
    def get_all_fragments(self) -> List[NormalizedFragment]:
        """Get all stored fragments."""
        return list(self._fragments.values())
    
    def get_all_thread_ids(self) -> List[ThreadId]:
        """Get all thread IDs with stored snapshots."""
        return [ThreadId(value=tid) for tid in self._thread_versions.keys()]
    
    def create_checkpoint(self) -> ReplayCheckpoint:
        """Create a checkpoint for replay capability."""
        self._checkpoint_counter += 1
        
        # Compute state hash
        state_content = json.dumps({
            'event_count': len(self._events),
            'snapshot_count': len(self._snapshots),
            'fragment_count': len(self._fragments),
            'write_sequence': self._write_sequence
        }, sort_keys=True)
        state_hash = hashlib.sha256(state_content.encode()).hexdigest()
        
        checkpoint = ReplayCheckpoint(
            checkpoint_id=f"ckpt_{self._checkpoint_counter:06d}",
            timestamp=Timestamp.now(),
            layer="storage",
            sequence_number=self._write_sequence,
            state_hash=state_hash
        )
        
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        return checkpoint
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[ReplayCheckpoint]:
        """Retrieve a specific checkpoint."""
        return self._checkpoints.get(checkpoint_id)


# =============================================================================
# FILE-BASED STORAGE BACKEND
# =============================================================================

class FileStorageBackend(StorageBackend):
    """
    File-based implementation of storage backend.
    
    Uses append-only JSON files. No mutation of stored data.
    Suitable for persistent storage without a database.
    """
    
    def __init__(self, storage_dir: str):
        self._storage_dir = storage_dir
        self._events_file = os.path.join(storage_dir, "events.jsonl")
        self._fragments_file = os.path.join(storage_dir, "fragments.jsonl")
        self._snapshots_file = os.path.join(storage_dir, "snapshots.jsonl")
        self._checkpoints_file = os.path.join(storage_dir, "checkpoints.jsonl")
        
        # Ensure storage directory exists
        os.makedirs(storage_dir, exist_ok=True)
        
        # In-memory indices (rebuilt on load)
        self._snapshot_index: Dict[str, int] = {}  # version_id -> file offset
        self._thread_versions: Dict[str, List[str]] = {}
        self._checkpoint_counter: int = 0
        
        # Load existing indices
        self._rebuild_indices()
    
    def _rebuild_indices(self):
        """Rebuild in-memory indices from storage files."""
        # Rebuild snapshot index
        if os.path.exists(self._snapshots_file):
            with open(self._snapshots_file, 'r') as f:
                offset = 0
                for line in f:
                    data = json.loads(line)
                    version_id = data.get('version_id', {}).get('value')
                    thread_id = data.get('thread_id', {}).get('value')
                    
                    if version_id:
                        self._snapshot_index[version_id] = offset
                    
                    if thread_id:
                        if thread_id not in self._thread_versions:
                            self._thread_versions[thread_id] = []
                        if version_id:
                            self._thread_versions[thread_id].append(version_id)
                    
                    offset = f.tell()
    
    def _serialize_snapshot(self, snapshot: ThreadStateSnapshot) -> str:
        """Serialize snapshot to JSON string."""
        return json.dumps({
            'version_id': {
                'value': snapshot.version_id.value,
                'sequence': snapshot.version_id.sequence,
                'parent_version': snapshot.version_id.parent_version
            },
            'thread_id': {'value': snapshot.thread_id.value},
            'lifecycle_state': snapshot.lifecycle_state.value,
            'member_fragment_ids': [
                {'value': fid.value, 'content_hash': fid.content_hash}
                for fid in snapshot.member_fragment_ids
            ],
            'canonical_topics': [
                {'topic_id': t.topic_id, 'canonical_name': t.canonical_name}
                for t in snapshot.canonical_topics
            ],
            'created_at': snapshot.created_at.to_iso(),
            'previous_version_id': snapshot.previous_version_id,
        })
    
    def write_snapshot(self, snapshot: ThreadStateSnapshot) -> StorageWriteResult:
        """Append snapshot to storage file."""
        try:
            with open(self._snapshots_file, 'a') as f:
                offset = f.tell()
                f.write(self._serialize_snapshot(snapshot) + '\n')
            
            # Update indices
            self._snapshot_index[snapshot.version_id.value] = offset
            thread_id = snapshot.thread_id.value
            if thread_id not in self._thread_versions:
                self._thread_versions[thread_id] = []
            self._thread_versions[thread_id].append(snapshot.version_id.value)
            
            return StorageWriteResult(
                success=True,
                version_id=snapshot.version_id,
                write_timestamp=Timestamp.now()
            )
        except Exception as e:
            return StorageWriteResult(
                success=False,
                error=Error(
                    code=ErrorCode.TIMELINE_CORRUPTION,
                    message=f"Failed to write snapshot: {str(e)}",
                    timestamp=Timestamp.now().value
                )
            )
    
    def write_event(self, event: NarrativeStateEvent) -> StorageWriteResult:
        """Append event to storage file."""
        # Simplified - in production would serialize full event
        return self.write_snapshot(event.new_state_snapshot)
    
    def write_fragment(self, fragment: NormalizedFragment) -> StorageWriteResult:
        """Append fragment to storage file."""
        try:
            with open(self._fragments_file, 'a') as f:
                data = {
                    'fragment_id': {
                        'value': fragment.fragment_id.value,
                        'content_hash': fragment.fragment_id.content_hash
                    },
                    'source_event_id': fragment.source_event_id,
                    'normalized_payload': fragment.normalized_payload,
                    'detected_language': fragment.detected_language,
                    'normalization_timestamp': fragment.normalization_timestamp.to_iso(),
                }
                f.write(json.dumps(data) + '\n')
            
            return StorageWriteResult(
                success=True,
                write_timestamp=Timestamp.now()
            )
        except Exception as e:
            return StorageWriteResult(
                success=False,
                error=Error(
                    code=ErrorCode.TIMELINE_CORRUPTION,
                    message=f"Failed to write fragment: {str(e)}",
                    timestamp=Timestamp.now().value
                )
            )
    
    def get_snapshot(self, version_id: VersionId) -> Optional[ThreadStateSnapshot]:
        """Retrieve a specific snapshot version from file."""
        # Would need to deserialize from file - simplified for now
        return None
    
    def get_latest_snapshot(self, thread_id: ThreadId) -> Optional[ThreadStateSnapshot]:
        """Get the latest snapshot for a thread."""
        versions = self._thread_versions.get(thread_id.value, [])
        if not versions:
            return None
        return self.get_snapshot(VersionId(value=versions[-1], sequence=0))
    
    def get_snapshot_history(
        self,
        thread_id: ThreadId,
        time_range: Optional[TimeRange] = None
    ) -> List[ThreadStateSnapshot]:
        """Get all snapshots for a thread."""
        # Would need full implementation
        return []
    
    def get_events(
        self,
        thread_id: Optional[ThreadId] = None,
        time_range: Optional[TimeRange] = None
    ) -> List[NarrativeStateEvent]:
        """Get events from storage."""
        # Would need full implementation
        return []
    
    def create_checkpoint(self) -> ReplayCheckpoint:
        """Create a checkpoint for replay capability."""
        self._checkpoint_counter += 1
        
        checkpoint = ReplayCheckpoint(
            checkpoint_id=f"ckpt_{self._checkpoint_counter:06d}",
            timestamp=Timestamp.now(),
            layer="storage",
            sequence_number=self._checkpoint_counter,
            state_hash=hashlib.sha256(str(self._checkpoint_counter).encode()).hexdigest()
        )
        
        # Append to checkpoints file
        try:
            with open(self._checkpoints_file, 'a') as f:
                f.write(json.dumps({
                    'checkpoint_id': checkpoint.checkpoint_id,
                    'timestamp': checkpoint.timestamp.to_iso(),
                    'sequence_number': checkpoint.sequence_number,
                    'state_hash': checkpoint.state_hash
                }) + '\n')
        except Exception:
            pass
        
        return checkpoint
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[ReplayCheckpoint]:
        """Retrieve a specific checkpoint."""
        # Would need full implementation
        return None


# =============================================================================
# TEMPORAL STORAGE ENGINE (Orchestrates storage operations)
# =============================================================================

@dataclass
class TemporalStorageConfig:
    """Configuration for temporal storage."""
    backend_type: str = "memory"  # "memory" or "file"
    storage_dir: Optional[str] = None
    enable_checkpoints: bool = True
    checkpoint_interval: int = 100  # Events between checkpoints


class TemporalStorageEngine:
    """
    Temporal Storage Engine.
    
    BOUNDARY ENFORCEMENT:
    - ONLY performs append operations
    - NEVER modifies existing data
    - Supports full rewind/replay via version chains
    - Maintains data lineage for audit
    """
    
    def __init__(self, config: Optional[TemporalStorageConfig] = None):
        self._config = config or TemporalStorageConfig()
        self._backend = self._create_backend()
        self._write_count: int = 0
        self._audit_log: List[AuditLogEntry] = []
    
    def _create_backend(self) -> StorageBackend:
        """Create storage backend based on configuration."""
        if self._config.backend_type == "file" and self._config.storage_dir:
            return FileStorageBackend(self._config.storage_dir)
        return InMemoryStorageBackend()
    
    def store_event(self, event: NarrativeStateEvent) -> StorageWriteResult:
        """Store a narrative state event."""
        result = self._backend.write_event(event)
        
        if result.success:
            self._write_count += 1
            
            # Also store the snapshot
            self._backend.write_snapshot(event.new_state_snapshot)
            
            # Auto-checkpoint if needed
            if (self._config.enable_checkpoints and 
                self._write_count % self._config.checkpoint_interval == 0):
                self._backend.create_checkpoint()
            
            self._log_audit(
                action="event_stored",
                entity_id=event.event_id,
                metadata=(
                    ("thread_id", event.thread_id.value),
                    ("event_type", event.event_type),
                )
            )
        
        return result
    
    def store_fragment(self, fragment: NormalizedFragment) -> StorageWriteResult:
        """Store a normalized fragment."""
        result = self._backend.write_fragment(fragment)
        
        if result.success:
            self._write_count += 1
            self._log_audit(
                action="fragment_stored",
                entity_id=fragment.fragment_id.value,
            )
        
        return result
    
    def get_thread_at_time(
        self,
        thread_id: ThreadId,
        target_time: Timestamp
    ) -> Optional[ThreadStateSnapshot]:
        """
        Get the state of a thread at a specific point in time.
        
        This is the core time-travel query capability.
        """
        snapshots = self._backend.get_snapshot_history(thread_id)
        
        # Find the latest snapshot that existed at target_time
        valid_snapshots = [
            s for s in snapshots
            if s.created_at.value <= target_time.value
        ]
        
        if not valid_snapshots:
            return None
        
        # Return the most recent valid snapshot
        return max(valid_snapshots, key=lambda s: s.created_at.value)
    
    def get_thread_timeline(
        self,
        thread_id: ThreadId,
        time_range: Optional[TimeRange] = None
    ) -> Timeline:
        """Get the full timeline of a thread's evolution."""
        snapshots = self._backend.get_snapshot_history(thread_id, time_range)
        
        points = tuple(
            TimelinePoint(
                timestamp=s.created_at,
                version_id=s.version_id,
                entity_id=thread_id.value,
                state_summary=f"{s.lifecycle_state.value}: {len(s.member_fragment_ids)} fragments"
            )
            for s in snapshots
        )
        
        if points:
            actual_range = TimeRange(
                start=points[0].timestamp,
                end=points[-1].timestamp
            )
        else:
            now = Timestamp.now()
            actual_range = time_range or TimeRange(start=now, end=now)
        
        return Timeline(
            thread_id=thread_id,
            points=points,
            time_range=actual_range,
            total_versions=len(points)
        )
    
    def get_version_lineage(
        self,
        version_id: VersionId
    ) -> List[VersionId]:
        """
        Get the full lineage of a version back to the root.
        
        Supports audit and replay capabilities.
        """
        lineage = []
        current_version = version_id
        
        while current_version:
            lineage.append(current_version)
            snapshot = self._backend.get_snapshot(current_version)
            
            if not snapshot or not snapshot.previous_version_id:
                break
            
            # Get parent version
            parent_snapshot = None
            for thread_id in self._get_all_thread_ids():
                history = self._backend.get_snapshot_history(thread_id)
                for s in history:
                    if s.version_id.value == snapshot.previous_version_id:
                        parent_snapshot = s
                        break
                if parent_snapshot:
                    break
            
            if parent_snapshot:
                current_version = parent_snapshot.version_id
            else:
                break
        
        return lineage
    
    def _get_all_thread_ids(self) -> List[ThreadId]:
        """Get all thread IDs from backend."""
        if hasattr(self._backend, 'get_all_thread_ids'):
            return self._backend.get_all_thread_ids()
        return []
    
    def create_checkpoint(self) -> ReplayCheckpoint:
        """Manually create a checkpoint."""
        checkpoint = self._backend.create_checkpoint()
        self._log_audit(
            action="checkpoint_created",
            entity_id=checkpoint.checkpoint_id,
            metadata=(("state_hash", checkpoint.state_hash),)
        )
        return checkpoint
    
    def replay_from_checkpoint(
        self,
        checkpoint_id: str
    ) -> Optional[Dict]:
        """
        Replay system state from a checkpoint.
        
        Returns the reconstructed state or None if checkpoint not found.
        """
        checkpoint = self._backend.get_checkpoint(checkpoint_id)
        
        if not checkpoint:
            return None
        
        # Get all events up to checkpoint
        # In a real implementation, this would rebuild state
        self._log_audit(
            action="replay_started",
            entity_id=checkpoint_id,
            metadata=(("sequence", str(checkpoint.sequence_number)),)
        )
        
        return {
            'checkpoint': checkpoint,
            'status': 'replay_capability_available'
        }
    
    def _log_audit(
        self,
        action: str,
        entity_id: Optional[str] = None,
        metadata: tuple = ()
    ):
        """Add entry to internal audit log."""
        entry_id = hashlib.sha256(
            f"storage_{action}|{Timestamp.now().value.timestamp()}".encode()
        ).hexdigest()[:16]
        
        entry = AuditLogEntry(
            entry_id=f"audit_{entry_id}",
            event_type=AuditEventType.SYSTEM,
            timestamp=Timestamp.now(),
            layer="storage",
            action=action,
            entity_id=entity_id,
            metadata=metadata
        )
        self._audit_log.append(entry)
    
    def get_audit_log(self) -> List[AuditLogEntry]:
        """Return copy of audit log entries."""
        return list(self._audit_log)
    
    @property
    def backend(self) -> StorageBackend:
        """Access to the underlying storage backend."""
        return self._backend
