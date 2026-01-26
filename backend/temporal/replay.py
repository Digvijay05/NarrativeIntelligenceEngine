"""
Replay Engine
=============

Recomputation for late arrivals and point-in-time queries.

INVARIANT: Replay is deterministic.
Same log at same sequence = same derived state.

LATE ARRIVAL HANDLING:
1. Late fragment is appended to log (NOT inserted)
2. System recomputes state from log
3. Version lineage shows the change
4. No mutation of historical versions
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime, timezone

from ..contracts.base import Timestamp, ThreadId, Error, ErrorCode

from .event_log import ImmutableEventLog
from ..contracts.temporal import LogEntry, LogSequence
from .state_machine import StateMachine, DerivedState
from .versioning import VersionTracker, VersionedThread, ThreadLineage


# From task.md
MAX_REWIND_HORIZON_HOURS = 168  # 7 days


@dataclass(frozen=True)
class ReplayResult:
    """
    Result of replay operation.
    
    Contains both the derived state and any differences
    from previous derivation (if applicable).
    """
    success: bool
    state: Optional[DerivedState] = None
    error: Optional[Error] = None
    
    # Changes detected during replay
    new_threads: Tuple[ThreadId, ...] = ()
    modified_threads: Tuple[ThreadId, ...] = ()
    new_absences: int = 0


@dataclass(frozen=True)
class LateArrivalResult:
    """
    Result of processing a late-arriving fragment.
    
    Late arrivals are appended to log, then full state is
    recomputed. This captures what changed.
    """
    success: bool
    entry: Optional[LogEntry] = None
    replay_result: Optional[ReplayResult] = None
    error: Optional[Error] = None


class ReplayEngine:
    """
    Handles state recomputation and late arrivals.
    
    GUARANTEES:
    ===========
    1. Replay produces identical state for identical log
    2. Late arrivals trigger full recomputation, not patching
    3. Rewind horizon is enforced
    4. All changes are captured in result
    """
    
    def __init__(
        self,
        log: ImmutableEventLog,
        state_machine: StateMachine,
        version_tracker: VersionTracker,
        max_rewind_hours: int = MAX_REWIND_HORIZON_HOURS
    ):
        self._log = log
        self._state_machine = state_machine
        self._version_tracker = version_tracker
        self._max_rewind_hours = max_rewind_hours
        
        # Cache of latest derived state (for change detection)
        self._current_state: Optional[DerivedState] = None
    
    def replay_to(self, sequence: LogSequence) -> ReplayResult:
        """
        Replay log up to given sequence.
        
        Returns derived state at that point.
        """
        try:
            state = self._state_machine.derive_state(
                log=self._log,
                until_sequence=sequence
            )
            
            # Record versions
            for thread in state.threads:
                self._version_tracker.record_version(
                    thread_id=thread.thread_id,
                    at_sequence=sequence,
                    state_hash=thread.state_hash,
                    fragment_count=len(thread.member_fragment_ids)
                )
            
            # Detect changes from previous state
            changes = self._detect_changes(state)
            
            self._current_state = state
            
            return ReplayResult(
                success=True,
                state=state,
                new_threads=changes[0],
                modified_threads=changes[1],
                new_absences=changes[2]
            )
            
        except Exception as e:
            return ReplayResult(
                success=False,
                error=Error(
                    code=ErrorCode.STRUCTURAL_INCONSISTENCY,
                    message=str(e),
                    timestamp=datetime.now(timezone.utc)
                )
            )
    
    def replay_full(self) -> ReplayResult:
        """Replay entire log from start."""
        return self.replay_to(self._log.state.head_sequence)
    
    def handle_late_arrival(
        self,
        fragment,  # NormalizedFragment
        event_timestamp: Timestamp
    ) -> LateArrivalResult:
        """
        Handle late-arriving fragment.
        
        1. Check rewind horizon
        2. Append to log (NOT insert)
        3. Trigger full recomputation
        4. Return changes
        """
        # Check rewind horizon
        now = datetime.now(timezone.utc)
        age_hours = (now - event_timestamp.value).total_seconds() / 3600
        
        if age_hours > self._max_rewind_hours:
            return LateArrivalResult(
                success=False,
                error=Error(
                    code=ErrorCode.TEMPORAL_AMBIGUITY,
                    message=f"Late arrival exceeds rewind horizon ({age_hours:.1f}h > {self._max_rewind_hours}h)",
                    timestamp=datetime.now(timezone.utc),
                    context=(
                        ("event_timestamp", event_timestamp.to_iso()),
                        ("age_hours", str(age_hours)),
                    )
                )
            )
        
        # Append to log (append-only, no insertion)
        entry = self._log.append(fragment)
        
        # Trigger full recomputation
        replay_result = self.replay_full()
        
        return LateArrivalResult(
            success=replay_result.success,
            entry=entry,
            replay_result=replay_result,
            error=replay_result.error
        )
    
    def get_state_at(self, sequence: LogSequence) -> Optional[DerivedState]:
        """Get derived state at specific sequence (point-in-time query)."""
        result = self.replay_to(sequence)
        if result.success:
            return result.state
        return None
    
    def verify_determinism(self) -> Tuple[bool, Optional[str]]:
        """
        Verify that replay produces identical state.
        
        Runs replay twice and compares state hashes.
        Returns (is_deterministic, difference_description).
        """
        state1 = self._state_machine.derive_state(self._log)
        state2 = self._state_machine.derive_state(self._log)
        
        if state1.state_hash != state2.state_hash:
            return (False, f"Hash mismatch: {state1.state_hash} != {state2.state_hash}")
        
        if len(state1.threads) != len(state2.threads):
            return (False, f"Thread count mismatch: {len(state1.threads)} != {len(state2.threads)}")
        
        return (True, None)
    
    def _detect_changes(
        self,
        new_state: DerivedState
    ) -> Tuple[Tuple[ThreadId, ...], Tuple[ThreadId, ...], int]:
        """Detect changes from previous state."""
        if not self._current_state:
            # All threads are new
            return (
                tuple(t.thread_id for t in new_state.threads),
                (),
                len(new_state.absences)
            )
        
        old_threads = {t.thread_id.value: t for t in self._current_state.threads}
        new_threads_list = []
        modified_threads_list = []
        
        for thread in new_state.threads:
            if thread.thread_id.value not in old_threads:
                new_threads_list.append(thread.thread_id)
            else:
                old = old_threads[thread.thread_id.value]
                if thread.state_hash != old.state_hash:
                    modified_threads_list.append(thread.thread_id)
        
        new_absences = len(new_state.absences) - len(self._current_state.absences)
        
        return (tuple(new_threads_list), tuple(modified_threads_list), max(0, new_absences))
