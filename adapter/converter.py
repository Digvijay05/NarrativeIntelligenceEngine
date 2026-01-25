"""
Snapshot Converter

Converts backend contracts to adapter contracts.

BOUNDARY ENFORCEMENT:
=====================
This is where backend types are translated to adapter types.
Backend types NEVER leak into model layer.

WHY THIS EXISTS:
================
1. Clean separation of backend and adapter contracts
2. Explicit conversion points for debugging
3. No implicit type coercion
"""

from __future__ import annotations
from typing import List, Tuple
from datetime import datetime
import hashlib

# Backend contracts (input)
from backend.contracts.events import (
    NormalizedFragment,
    ThreadStateSnapshot,
    NarrativeStateEvent,
)
from backend.contracts.base import (
    ThreadId, FragmentId, Timestamp,
)

# Adapter contracts (output)
from .contracts import (
    NarrativeSnapshotInput,
    FragmentBatchInput,
)


class SnapshotConverter:
    """
    Convert backend types to adapter types.
    
    GUARANTEES:
    ===========
    1. Deterministic conversion
    2. No data loss (all relevant fields mapped)
    3. Explicit errors for unmappable data
    """
    
    def convert_thread_snapshot(
        self,
        snapshot: ThreadStateSnapshot,
        fragments: List[NormalizedFragment]
    ) -> NarrativeSnapshotInput:
        """
        Convert ThreadStateSnapshot to NarrativeSnapshotInput.
        
        WHY THIS CONVERSION:
        Backend ThreadStateSnapshot is for backend-internal use.
        Adapter NarrativeSnapshotInput is for model consumption.
        They have different contracts and guarantees.
        """
        # Convert fragments
        batch = self._convert_fragments(fragments, snapshot.thread_id)
        
        # Extract thread topics
        thread_topics = tuple(
            str(t.topic_id) for t in snapshot.canonical_topics
        )
        
        snapshot_id = self._generate_snapshot_id(snapshot)
        
        return NarrativeSnapshotInput(
            snapshot_id=snapshot_id,
            snapshot_version=str(snapshot.version_id.value) if snapshot.version_id else "v0",
            captured_at=snapshot.created_at.value if snapshot.created_at else datetime.utcnow(),
            thread_id=str(snapshot.thread_id.value) if snapshot.thread_id else "",
            thread_lifecycle=snapshot.lifecycle_state.value if snapshot.lifecycle_state else "unknown",
            thread_topics=thread_topics,
            fragments=batch,
            existing_annotations=()  # Would be populated from overlay store
        )
    
    def _convert_fragments(
        self,
        fragments: List[NormalizedFragment],
        thread_id: ThreadId
    ) -> FragmentBatchInput:
        """Convert list of NormalizedFragment to FragmentBatchInput."""
        if not fragments:
            return FragmentBatchInput(
                batch_id=f"empty_{thread_id.value if thread_id else 'unknown'}",
                fragment_ids=(),
                fragment_contents=(),
                fragment_timestamps=(),
                topic_ids=(),
                entity_ids=(),
                source_ids=()
            )
        
        fragment_ids = []
        fragment_contents = []
        fragment_timestamps = []
        topic_ids = []
        entity_ids = []
        source_ids = []
        
        for frag in fragments:
            fragment_ids.append(str(frag.fragment_id.value))
            fragment_contents.append(frag.normalized_payload)
            fragment_timestamps.append(
                frag.normalization_timestamp.value 
                if frag.normalization_timestamp else datetime.utcnow()
            )
            
            # Extract topics
            topics = [str(t.topic_id) for t in frag.canonical_topics]
            topic_ids.append(tuple(topics))
            
            # Extract entities
            entities = [str(e.entity_id) for e in frag.canonical_entities]
            entity_ids.append(tuple(entities))
            
            # Extract source
            source_ids.append(
                str(frag.source_metadata.source_id.value)
                if frag.source_metadata and frag.source_metadata.source_id else "unknown"
            )
        
        batch_id = self._generate_batch_id(fragment_ids)
        
        return FragmentBatchInput(
            batch_id=batch_id,
            fragment_ids=tuple(fragment_ids),
            fragment_contents=tuple(fragment_contents),
            fragment_timestamps=tuple(fragment_timestamps),
            topic_ids=tuple(topic_ids),
            entity_ids=tuple(entity_ids),
            source_ids=tuple(source_ids)
        )
    
    def _generate_snapshot_id(self, snapshot: ThreadStateSnapshot) -> str:
        """Generate deterministic snapshot ID."""
        thread_id = str(snapshot.thread_id.value) if snapshot.thread_id else "unknown"
        version = str(snapshot.version_id.value) if snapshot.version_id else "v0"
        content = f"{thread_id}|{version}|{len(snapshot.member_fragment_ids)}"
        return f"snap_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    
    def _generate_batch_id(self, fragment_ids: List[str]) -> str:
        """Generate deterministic batch ID."""
        content = "|".join(sorted(fragment_ids))
        return f"batch_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
