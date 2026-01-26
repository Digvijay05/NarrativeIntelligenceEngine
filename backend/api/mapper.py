"""
API Mapper
==========

Transforms internal forensic state (ThreadView) into Frontend DTOs.
Enforces the "Anti-Constitution" by exposing raw structural data without smoothing.
"""
import uuid
from typing import List, Dict, Any
from datetime import datetime, timezone

from ..contracts.base import Timestamp
from ..contracts.events import NormalizedFragment
from ..temporal.state_machine import DerivedState, ThreadView, AbsenceMarker, ThreadLifecycleState

# DTO Structures (Mirroring frontend/client/src/layers/state/contracts.ts)

def map_state_to_dto(state: DerivedState, fragments: Dict[str, NormalizedFragment]) -> Dict[str, Any]:
    """
    Map DerivedState to NarrativeVersionDTO.
    
    Args:
        state: The derived state from StateMachine.
        fragments: Lookup dict for fragment details (needed for timestamps).
    """
    threads_dto = []
    
    for thread in state.threads:
        threads_dto.append(_map_thread(thread, fragments))
        
    return {
        "version_id": f"v_{state.state_hash[:8]}",
        "generated_at": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "threads": threads_dto
    }

def _map_thread(thread: ThreadView, fragments: Dict[str, NormalizedFragment]) -> Dict[str, Any]:
    """Map single ThreadView to NarrativeThreadDTO."""
    segments = []
    
    # 1. Map Fragments -> Presence Segments
    # We group contiguous fragments? Or just one segment per thread for now?
    # The frontend supports segments. For the prototype, we can create one "Presence" segment
    # encompassing the range, OR discrete segments if we want to show gaps.
    # Given the constraint "No Smoothing", discrete segments or raw points are better.
    # However, standard timeline UIs usually expect blocks.
    # Let's map each fragment as a micro-segment for maximum granularity (Forensic Mode),
    # or cluster them if they are close.
    # For this implementation, we will create ONE presence segment for the whole active range,
    # UNLESS there are explicit absence markers breaking it.
    
    # Actually, the truest forensic view is: 
    # - Fragments are points (or short segments).
    # - Absence is a block.
    
    # Let's iterate and build segments.
    # Sort fragments by time
    thread_frags = []
    for fid in thread.member_fragment_ids:
        frag = fragments.get(fid.value)
        if frag:
            thread_frags.append(frag)
    
    thread_frags.sort(key=lambda f: f.normalization_timestamp.value)
    
    if thread_frags:
        # Create a single presence segment for the duration (or distinct ones if we had logic)
        # For simplicity in Phase 7 prototype: One continuous presence segment from First to Last.
        # BUT this violates "No Smoothing" if there are huge gaps.
        # CORRECT APPROACH: The "AbsenceMarker" defines the gaps. 
        # So we can have one Presence segment, and overlay Absence? 
        # Or split Presence around Absence.
        
        # Simpler: Map each fragment as a point-like segment.
        # But for the requested visualizing:
        segments.append({
            "segment_id": str(uuid.uuid4()),
            "thread_id": thread.thread_id.value,
            "kind": "presence",
            "start_time": thread_frags[0].normalization_timestamp.to_iso(),
            "end_time": thread_frags[-1].normalization_timestamp.to_iso(),
            "state": thread.lifecycle_state.value, # active/dormant
            "fragment_ids": [f.fragment_id.value for f in thread_frags]
        })

    # 2. Map Absence Markers -> Absence Segments
    for absence in thread.absence_markers:
        segments.append({
            "segment_id": absence.marker_id,
            "thread_id": thread.thread_id.value,
            "kind": "absence",
            "start_time": absence.gap_start.to_iso(),
            # If gap is ongoing (None), use current time
            "end_time": (absence.gap_end or Timestamp.now()).to_iso(),
            "state": "dormant",
            "fragment_ids": []
        })

    return {
        "thread_id": thread.thread_id.value,
        "segments": segments
    }
