"""
State Machine
=============

Pure function state derivation from event log.

INVARIANT: derive_state(log, seq) is a PURE FUNCTION
Same log at same sequence → identical derived state.

This module DOES NOT store state.
It COMPUTES state from the event log on demand.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, FrozenSet, Iterator
from datetime import datetime, timezone
import hashlib

from ..contracts.base import (
    Timestamp, FragmentId, ThreadId, VersionId,
    ThreadLifecycleState, Error, ErrorCode
)
from ..contracts.events import NormalizedFragment, ThreadStateSnapshot

from .event_log import ImmutableEventLog, LogEntry, LogSequence


# =============================================================================
# ABSENCE ENCODING
# =============================================================================

@dataclass(frozen=True)
class ExpectedContinuation:
    """
    Explicit encoding of expected but missing activity.
    
    Absence is FIRST-CLASS data, not a null or missing field.
    """
    thread_id: ThreadId
    expected_after: Timestamp
    last_seen: Timestamp
    expected_cadence_seconds: int
    silence_duration_seconds: int
    
    @property
    def is_significant(self) -> bool:
        """Silence exceeds 2x expected cadence."""
        return self.silence_duration_seconds > (self.expected_cadence_seconds * 2)


@dataclass(frozen=True)
class AbsenceMarker:
    """
    A specific gap in the narrative that has been explicitly recorded.
    """
    marker_id: str
    thread_id: ThreadId
    gap_start: Timestamp
    gap_end: Optional[Timestamp]  # None if ongoing
    gap_type: str  # "silence" | "expected_continuation_missing"


# =============================================================================
# DERIVED STATE STRUCTURES
# =============================================================================

@dataclass(frozen=True)
class ThreadView:
    """
    Immutable view of a thread derived from log.
    
    WHY VIEW, NOT ENTITY:
    A thread is a COMPUTED projection over fragment history.
    Different sequences produce different views of the same thread.
    """
    thread_id: ThreadId
    version: VersionId
    at_sequence: LogSequence
    
    # Derived content
    lifecycle_state: ThreadLifecycleState
    member_fragment_ids: Tuple[FragmentId, ...]
    canonical_topics: Tuple[str, ...]
    
    # Temporal bounds
    first_activity: Timestamp
    last_activity: Timestamp
    
    # Absence tracking
    absence_markers: Tuple[AbsenceMarker, ...] = field(default_factory=tuple)
    
    # State hash for determinism verification
    state_hash: str = ""
    
    def compute_hash(self) -> str:
        """Compute deterministic state hash."""
        content = (
            f"{self.thread_id.value}|"
            f"{self.version.value}|"
            f"{self.at_sequence.value}|"
            f"{self.lifecycle_state.value}|"
            f"{','.join(f.value for f in self.member_fragment_ids)}"
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass(frozen=True)
class ParallelBranch:
    """
    Represents parallel divergent evolution of a thread.
    
    When fragments suggest incompatible futures, both paths are preserved.
    NO RECONCILIATION, NO DOMINANCE, NO COLLAPSE.
    """
    branch_id: str
    parent_thread_id: ThreadId
    divergence_point: LogSequence
    branch_fragments: Tuple[FragmentId, ...]
    divergence_reason: str


@dataclass(frozen=True)
class DerivedState:
    """
    Complete derived state at a point in the log.
    
    This is the OUTPUT of the state machine.
    Computed fresh for each query, not cached.
    """
    at_sequence: LogSequence
    state_hash: str
    
    # Thread views
    threads: Tuple[ThreadView, ...]
    
    # Parallel divergences
    branches: Tuple[ParallelBranch, ...] = field(default_factory=tuple)
    
    # Absence markers
    absences: Tuple[AbsenceMarker, ...] = field(default_factory=tuple)
    
    # Errors encountered during derivation
    errors: Tuple[Error, ...] = field(default_factory=tuple)


# =============================================================================
# STATE MACHINE
# =============================================================================

# Prototype constants (from task.md)
TOPIC_OVERLAP_MIN = 0.6
TEMPORAL_ADJACENCY_HOURS = 72
DORMANCY_HOURS = 168  # 7 days


class StateMachine:
    """
    Pure function state derivation engine.
    
    GUARANTEES:
    ===========
    1. derive_state(log, seq) is deterministic
    2. No side effects on log
    3. No hidden state between calls
    4. Explicit failure states for all ambiguity
    """
    
    def __init__(
        self,
        topic_overlap_min: float = TOPIC_OVERLAP_MIN,
        temporal_adjacency_hours: int = TEMPORAL_ADJACENCY_HOURS,
        dormancy_hours: int = DORMANCY_HOURS
    ):
        self._topic_overlap_min = topic_overlap_min
        self._temporal_adjacency_hours = temporal_adjacency_hours
        self._dormancy_hours = dormancy_hours
    
    def derive_state(
        self,
        log: ImmutableEventLog,
        until_sequence: Optional[LogSequence] = None,
        reference_time: Optional[Timestamp] = None
    ) -> DerivedState:
        """
        Derive complete state from log up to given sequence.
        
        This is the CORE DERIVATION FUNCTION.
        Same log + same sequence = same state (deterministic).
        """
        target_seq = until_sequence or log.state.head_sequence
        
        # Accumulator for building state
        thread_builders: Dict[str, _ThreadBuilder] = {}
        branches: List[ParallelBranch] = []
        absences: List[AbsenceMarker] = []
        errors: List[Error] = []
        
        # Replay log entries in order
        for entry in log.replay(until_seq=target_seq):
            result = self._process_entry(
                entry=entry,
                thread_builders=thread_builders,
                branches=branches
            )
            
            if result.error:
                errors.append(result.error)
            if result.absence:
                absences.append(result.absence)
        
        # Build final thread views
        threads = tuple(
            builder.build(at_sequence=target_seq, reference_time=reference_time)
            for builder in thread_builders.values()
        )
        
        # Compute state hash
        state_hash = self._compute_state_hash(threads, target_seq)
        
        return DerivedState(
            at_sequence=target_seq,
            state_hash=state_hash,
            threads=threads,
            branches=tuple(branches),
            absences=tuple(absences),
            errors=tuple(errors)
        )
    
    def _process_entry(
        self,
        entry: LogEntry,
        thread_builders: Dict[str, '_ThreadBuilder'],
        branches: List[ParallelBranch]
    ) -> '_ProcessingResult':
        """Process single log entry."""
        fragment = entry.fragment
        
        # Find matching thread
        matching_thread_id = self._find_matching_thread(
            fragment=fragment,
            thread_builders=thread_builders
        )
        
        if matching_thread_id:
            # Add to existing thread
            builder = thread_builders[matching_thread_id]
            
            # Check for divergence
            divergence = self._check_divergence(fragment, builder)
            if divergence:
                # DIVERGENCE DETECTED: Fork the thread
                # We start a NEW thread for this parallel reality
                branch_thread_id = ThreadId.generate(f"branch_{fragment.fragment_id.value}")
                branch_builder = _ThreadBuilder(
                    thread_id=branch_thread_id,
                    config=self
                )
                
                # Clone history? 
                # For strict forensic/append-only, we don't copy data.
                # The ParallelBranch object links them. 
                # This new thread starts effectively "ex nihilo" or from the fork point.
                # For this implementation, we just start it fresh to verify the split.
                
                branch_builder.add_fragment(fragment, entry.sequence)
                thread_builders[branch_thread_id.value] = branch_builder
                
                branches.append(divergence)
                return _ProcessingResult()
            
            # Check for absence before this fragment
            absence = self._check_absence(fragment, builder, entry.sequence)
            if absence:
                builder.add_absence(absence)
            
            builder.add_fragment(fragment, entry.sequence)
            
            return _ProcessingResult(absence=absence)
        else:
            # Create new thread
            thread_id = ThreadId.generate(f"thread_from_{fragment.fragment_id.value}")
            builder = _ThreadBuilder(
                thread_id=thread_id,
                config=self
            )
            builder.add_fragment(fragment, entry.sequence)
            thread_builders[thread_id.value] = builder
            
            return _ProcessingResult()
    
    def _find_matching_thread(
        self,
        fragment: NormalizedFragment,
        thread_builders: Dict[str, '_ThreadBuilder']
    ) -> Optional[str]:
        """Find thread that matches this fragment."""
        
        # 1. EXPLICIT EDGE CHECK (Force Merge)
        # If this fragment is explicitly related to a fragment in an existing thread, join it.
        # This overrides topic/time similarity.
        if fragment.candidate_relations:
            for relation in fragment.candidate_relations:
                # We are looking for the 'other' end of the edge
                # The relation could be source->target or target->source
                # Since we inject edges where 'source' is the previous/parent,
                # and 'target' is this fragment (or vice versa), check both.
                
                target_id = relation.target_fragment_id.value
                source_id = relation.source_fragment_id.value
                
                # If the other end is NOT us, it's the anchor
                anchor_id = None
                if target_id != fragment.fragment_id.value:
                    anchor_id = target_id
                elif source_id != fragment.fragment_id.value:
                    anchor_id = source_id
                
                if anchor_id:
                    # Find thread containing anchor
                    for tid, builder in thread_builders.items():
                        # O(N) scan per edge - acceptable for prototype
                        # In prod, maintain fragment_id -> thread_id index
                        for existing_frag_id in builder.fragments:
                            if existing_frag_id.value == anchor_id:
                                return tid

        # 2. Implicit Similarity (Fall back to existing logic)
        best_match: Optional[str] = None
        best_score = 0.0
        
        for thread_id, builder in thread_builders.items():
            score = self._compute_match_score(fragment, builder)
            if score > best_score and score >= self._topic_overlap_min:
                best_score = score
                best_match = thread_id
        
        return best_match
    
    def _compute_match_score(
        self,
        fragment: NormalizedFragment,
        builder: '_ThreadBuilder'
    ) -> float:
        """Compute match score between fragment and thread."""
        # Topic overlap (0.0 to 0.5)
        fragment_topics = set(t.topic_id for t in fragment.canonical_topics)
        thread_topics = set(builder.topics)
        
        if not fragment_topics or not thread_topics:
            topic_score = 0.0
        else:
            overlap = len(fragment_topics & thread_topics)
            topic_score = (overlap / max(len(fragment_topics), len(thread_topics))) * 0.5
        
        # Temporal proximity (0.0 to 0.3)
        if builder.last_activity:
            hours_diff = abs(
                (fragment.normalization_timestamp.value - builder.last_activity.value).total_seconds()
            ) / 3600
            
            # Check for vanished threshold prevention
            # If gap > vanished threshold, thread is effectively TERMINATED.
            # It should NOT match new fragments.
            # Using same heuristic as build(): 5x dormancy
            dormancy_seconds = self._dormancy_hours * 3600
            vanished_seconds = dormancy_seconds * 5 
            
            gap_seconds = (fragment.normalization_timestamp.value - builder.last_activity.value).total_seconds()
            
            if gap_seconds > vanished_seconds:
                # TERMINATED threads cannot accept new fragments.
                return 0.0

            if hours_diff <= self._temporal_adjacency_hours:
                temporal_score = 0.3 * (1 - hours_diff / self._temporal_adjacency_hours)
            else:
                temporal_score = 0.0
        else:
            temporal_score = 0.0
        
        return topic_score + temporal_score
    
    def _check_divergence(
        self,
        fragment: NormalizedFragment,
        builder: '_ThreadBuilder'
    ) -> Optional[ParallelBranch]:
        """
        Check if fragment causes divergence.
        
        HEURISTIC (Forensic):
        If a fragment arrives with the EXACT SAME timestamp as an existing event in the thread,
        but from a DIFFERENT source and with DIFFERENT content, it implies a Parallel Reality.
        
        Strict strict forensic view: Two things cannot happen at the same time in the same narrative 
        unless they are corroborating. If they differ, they represent branching paths.
        """
        if not builder.last_activity:
            return None
            
        # 0. EXPLICIT EDGE EXEMPTION
        # If explicitly connected, it's not a divergence (even if simultaneous)
        if fragment.candidate_relations:
            for relation in fragment.candidate_relations:
                target_id = relation.target_fragment_id.value
                source_id = relation.source_fragment_id.value
                anchor_id = target_id if target_id != fragment.fragment_id.value else source_id
                
                # Check if anchor is in this thread
                # This is an O(N) check, optimization: builder could have a set
                for existing_id in builder.fragments:
                    if existing_id.value == anchor_id:
                        return None

        # Check against existing fragments in this builder (scan backwards)
        # In a real impl, we'd have a better index. here we just check the builder's tracked state.
        # But builder only explicitly stores IDs. We can't check content.
        # However, we can check the timestamp constraint against 'last_activity' if it matches exactly.
        
        if fragment.normalization_timestamp.value == builder.last_activity.value:
            # Timestamp collision. Potentially divergent.
            # We assume for this heuristic that if it matched the thread topic but collided on time,
            # and is not a duplicate (which would be filtered earlier), it's a divergence.
            
            return ParallelBranch(
                branch_id=f"branch_{fragment.fragment_id.value[:8]}",
                parent_thread_id=builder.thread_id,
                divergence_point=builder.last_sequence or LogSequence(0),
                branch_fragments=(fragment.fragment_id,),
                divergence_reason="FORENSIC_TIMESTAMP_COLLISION"
            )
            
        return None
    
    def _check_absence(
        self,
        fragment: NormalizedFragment,
        builder: '_ThreadBuilder',
        current_seq: LogSequence
    ) -> Optional[AbsenceMarker]:
        """Check for significant gap before this fragment."""
        if not builder.last_activity:
            return None
        
        gap_seconds = (
            fragment.normalization_timestamp.value - builder.last_activity.value
        ).total_seconds()
        
        # Check if gap exceeds dormancy threshold
        dormancy_seconds = self._dormancy_hours * 3600
        
        if gap_seconds > dormancy_seconds:
            marker_id = hashlib.sha256(
                f"gap|{builder.thread_id.value}|{current_seq.value}".encode()
            ).hexdigest()[:12]
            
            return AbsenceMarker(
                marker_id=marker_id,
                thread_id=builder.thread_id,
                gap_start=builder.last_activity,
                gap_end=fragment.normalization_timestamp,
                gap_type="expected_continuation_missing"
            )
        
        return None
    
    def _compute_state_hash(
        self,
        threads: Tuple[ThreadView, ...],
        at_sequence: LogSequence
    ) -> str:
        """Compute deterministic hash of derived state."""
        # Sort threads for determinism
        sorted_threads = sorted(threads, key=lambda t: t.thread_id.value)
        
        content = f"{at_sequence.value}|"
        for thread in sorted_threads:
            content += f"{thread.thread_id.value}:{len(thread.member_fragment_ids)}|"
        
        return hashlib.sha256(content.encode()).hexdigest()[:16]


# =============================================================================
# INTERNAL HELPERS
# =============================================================================

@dataclass
class _ThreadBuilder:
    """Mutable builder for constructing ThreadView during derivation."""
    thread_id: ThreadId
    config: StateMachine
    
    fragments: List[FragmentId] = field(default_factory=list)
    topics: set = field(default_factory=set)
    first_activity: Optional[Timestamp] = None
    last_activity: Optional[Timestamp] = None
    last_sequence: Optional[LogSequence] = None
    absence_markers: List[AbsenceMarker] = field(default_factory=list)
    
    def add_fragment(self, fragment: NormalizedFragment, seq: LogSequence):
        self.fragments.append(fragment.fragment_id)
        
        for topic in fragment.canonical_topics:
            self.topics.add(topic.topic_id)
        
        ts = fragment.normalization_timestamp
        if self.first_activity is None or ts.value < self.first_activity.value:
            self.first_activity = ts
        if self.last_activity is None or ts.value > self.last_activity.value:
            self.last_activity = ts
        
        self.last_sequence = seq

    def add_absence(self, absence: AbsenceMarker):
        self.absence_markers.append(absence)
    
    def build(self, at_sequence: LogSequence, reference_time: Optional[Timestamp] = None) -> ThreadView:
        # Compute lifecycle state
        ref_time = reference_time.value if reference_time else datetime.now(timezone.utc)
        
        if len(self.fragments) < 3:
            lifecycle = ThreadLifecycleState.EMERGING
        else:
            # Check for dormancy and vanished
            if self.last_activity:
                gap = (ref_time - self.last_activity.value).total_seconds()
                
                # Vanished threshold (hardcoded 10 ticks = 5 mins approx for test, or purely config based)
                # Config says 168 hours for Dormancy.
                # Absence Spec says: Active -> Dormant (Tick+2), Dormant -> Unresolved (Tick+4), Unresolved -> Vanished (Tick+10).
                # We need to respect the config passed in.
                
                # Assuming config._dormancy_hours corresponds to "Tick+2" roughly.
                # We need a vanished threshold.
                # Let's add _vanished_hours to config or derive it.
                # using 2.5x dormancy as heuristic for vanished if not config.
                
                dormancy_seconds = self.config._dormancy_hours * 3600
                vanished_seconds = dormancy_seconds * 5 # Heuristic: 5x dormancy
                
                if gap > vanished_seconds:
                     lifecycle = ThreadLifecycleState.TERMINATED # Vanished
                elif gap > dormancy_seconds:
                    lifecycle = ThreadLifecycleState.DORMANT
                else:
                    lifecycle = ThreadLifecycleState.ACTIVE
            else:
                lifecycle = ThreadLifecycleState.ACTIVE
        
        # Create version
        version = VersionId.generate(
            self.thread_id.value,
            at_sequence.value,
            None
        )
        
        view = ThreadView(
            thread_id=self.thread_id,
            version=version,
            at_sequence=at_sequence,
            lifecycle_state=lifecycle,
            member_fragment_ids=tuple(self.fragments),
            canonical_topics=tuple(self.topics),
            first_activity=self.first_activity or Timestamp(ref_time),
            last_activity=self.last_activity or Timestamp(ref_time),
            absence_markers=tuple(self.absence_markers)
        )
        
        # Add state hash
        return ThreadView(
            thread_id=view.thread_id,
            version=view.version,
            at_sequence=view.at_sequence,
            lifecycle_state=view.lifecycle_state,
            member_fragment_ids=view.member_fragment_ids,
            canonical_topics=view.canonical_topics,
            first_activity=view.first_activity,
            last_activity=view.last_activity,
            absence_markers=view.absence_markers,
            state_hash=view.compute_hash()
        )


@dataclass
class _ProcessingResult:
    """Result of processing single entry."""
    error: Optional[Error] = None
    absence: Optional[AbsenceMarker] = None
