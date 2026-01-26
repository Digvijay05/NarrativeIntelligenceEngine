"""
Domain to Contract Mapper
=========================
Bridges the Internal Domain State (Engine/storage) to the Strict External Contract (DTOs).
Implements Derivation Logic for Timeline Segments.

Principles:
- Read-only access to Backend.
- Deterministic derivation of Segments from State Transitions.
- Enforces R1-R4 of the Spec.
"""

from typing import List, Dict, Optional, Tuple, Any
from datetime import datetime, timezone

from .spec import (
    NarrativeVersionDTO, NarrativeThreadDTO, TimelineSegmentDTO, FragmentDTO,
    SegmentKind, ThreadState
)
from .base import Timestamp, ThreadLifecycleState, ThreadId
from .events import ThreadStateSnapshot, Timeline, TimelinePoint

# Type for the Backend Engine (Forward ref or Protocol ideally, but dynamic for now)
NarrativeBackend = Any 

class ContractMapper:
    
    @staticmethod
    def to_version_dto(backend: NarrativeBackend, version_id: str) -> NarrativeVersionDTO:
        """
        Constructs a NarrativeVersionDTO from the current backend state.
        
        Args:
            backend: The orchestrator instance (provides query access).
            version_id: Unique ID for this generated version.
        """
        generated_at = datetime.now(timezone.utc)
        thread_dtos = []
        
        # 1. Get all threads
        threads: Dict[str, ThreadStateSnapshot] = backend.get_all_threads()
        
        for thread_id, snapshot in threads.items():
            # 2. Query full timeline for each thread
            # Timelines provide the state transitions needed to build segments
            timeline_result = backend.query_timeline(ThreadId(value=thread_id))
            
            if not timeline_result.success or not timeline_result.results:
                continue
                
            # Unpack first result (Timeline object)
            timeline: Timeline = timeline_result.results[0]
            
            # 3. Derive Segments from Timeline
            segments = ContractMapper._derive_segments(backend, timeline, snapshot)
            
            thread_dtos.append(NarrativeThreadDTO(
                thread_id=thread_id,
                segments=segments
            ))
            
        return NarrativeVersionDTO(
            version_id=version_id,
            generated_at=generated_at,
            threads=thread_dtos
        )

    @staticmethod
    def _derive_segments(
        backend: NarrativeBackend, 
        timeline: Timeline, 
        current_snapshot: ThreadStateSnapshot
    ) -> List[TimelineSegmentDTO]:
        """
        Derives contiguous segments from discrete timeline points.
        Rules:
        - Segment starts at a State Change.
        - Segment ends at next State Change or Now.
        - Gaps > threshold implies ABSENCE? 
          (For now, we assume continuity between points unless state is Dormant/Terminated)
        """
        segments: List[TimelineSegmentDTO] = []
        points = sorted(timeline.points, key=lambda p: p.timestamp.value)
        
        if not points:
            return []
            
        # Iterate points to create segments
        for i in range(len(points)):
            current_point = points[i]
            
            # End time is next point's start, or Now if last point
            if i < len(points) - 1:
                next_point = points[i+1]
                end_time = next_point.timestamp.value
            else:
                end_time = datetime.now(timezone.utc)
            
            # To get specific state (Active vs Dormant), we need the snapshot at that version
            # Optimization: The TimelinePoint could allow inferring state, but strictly we fetch it.
            # For prototype: We assume the State Summary in TimelinePoint helps, or we fetch.
            # Let's fetch the snapshot for this version to be precise.
            
            # This is expensive (N+1 queries). For prototype, acceptable.
            # Real impl would batch or cache.
            snapshot_result = backend.query_thread_state(
                current_snapshot.thread_id, 
                at_time=current_point.timestamp
            )
            
            state_snapshot: Optional[ThreadStateSnapshot] = None
            if snapshot_result.success and snapshot_result.results:
                state_snapshot = snapshot_result.results[0]
            
            if not state_snapshot:
                continue
                
            # Map Lifecycle to ThreadState
            contract_state = ContractMapper._map_state(state_snapshot.lifecycle_state)
            
            # Determine Kind
            kind = SegmentKind.PRESENCE
            if hasattr(state_snapshot, 'absence_markers') and len(state_snapshot.absence_markers) > 0:
                 kind = SegmentKind.ABSENCE
            
            # Fragments
            # Only PRESENCE segments have fragments
            fragment_ids = []
            if kind == SegmentKind.PRESENCE:
                fragment_ids = [f.value for f in state_snapshot.member_fragment_ids]

            segments.append(TimelineSegmentDTO(
                segment_id=f"seg_{current_point.version_id.value}",
                thread_id=state_snapshot.thread_id.value,
                kind=kind,
                start_time=current_point.timestamp.value,
                end_time=end_time,
                state=contract_state,
                fragment_ids=fragment_ids
            ))
            
        return segments

    @staticmethod
    def _map_state(lifecycle: ThreadLifecycleState) -> ThreadState:
        if lifecycle == ThreadLifecycleState.EMERGING:
            return ThreadState.ACTIVE
        elif lifecycle == ThreadLifecycleState.ACTIVE:
            return ThreadState.ACTIVE
        elif lifecycle == ThreadLifecycleState.DORMANT:
            return ThreadState.DORMANT
        elif lifecycle == ThreadLifecycleState.TERMINATED:
            return ThreadState.TERMINATED
        elif lifecycle == ThreadLifecycleState.DIVERGED:
            return ThreadState.DIVERGENT
        return ThreadState.ACTIVE
