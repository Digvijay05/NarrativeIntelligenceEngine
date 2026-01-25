"""
Core Narrative State Engine

RESPONSIBILITY: Thread construction, lifecycle management, divergence detection
ALLOWED INPUTS: NormalizedFragment from normalization layer
OUTPUTS: NarrativeStateEvent (immutable)

WHAT THIS LAYER MUST NOT DO:
============================
- Persist data (that's storage layer's job)
- Query historical data (use query layer)
- Normalize or canonicalize data (normalization layer's job)
- Make truth judgments or resolve contradictions
- Rank importance or priority
- Predict future events
- Perform sentiment analysis

BOUNDARY ENFORCEMENT:
=====================
- Consumes ONLY NormalizedFragment from normalization layer
- Produces ONLY NarrativeStateEvent and ThreadStateSnapshot
- All state changes produce NEW immutable snapshots (append-only)
- No in-place mutation of any state

REFACTORING FROM PREVIOUS CODE:
===============================
Previous coupling risks eliminated:
1. OLD: NarrativeStateEngine in models.py directly mutated thread state
   NEW: All state changes produce new immutable snapshots
2. OLD: Thread.add_fragment() mutated the thread in place
   NEW: State transitions create new ThreadStateSnapshot
3. OLD: Processing history was mutable list embedded in engine
   NEW: NarrativeStateEvent emitted for every change, stored externally
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set
from enum import Enum, auto
import hashlib
import time

# ONLY import from contracts - never from other layers' implementations
from ..contracts.base import (
    FragmentId, ThreadId, VersionId, Timestamp, TimeRange,
    ThreadLifecycleState, FragmentRelationType, FragmentRelation,
    CanonicalTopic, Error, ErrorCode
)
from ..contracts.events import (
    NormalizedFragment, NarrativeStateEvent, ThreadStateSnapshot,
    ThreadMembership, FragmentProcessingOutcome, ThreadProcessingResult,
    DuplicateStatus, ContradictionStatus, AuditLogEntry, AuditEventType
)


# =============================================================================
# THREAD GROUPING STRATEGIES (Deterministic)
# =============================================================================

class ThreadMatcher:
    """
    Determine which thread a fragment belongs to.
    
    Uses topic coherence and temporal adjacency for deterministic matching.
    No probabilistic models - same input always produces same match.
    """
    
    def __init__(self, temporal_window_seconds: int = 86400 * 7):  # 7 days default
        self._temporal_window_seconds = temporal_window_seconds
    
    def find_matching_thread(
        self,
        fragment: NormalizedFragment,
        thread_states: Dict[str, ThreadStateSnapshot]
    ) -> Optional[ThreadId]:
        """
        Find a matching thread for the fragment.
        
        Returns ThreadId if match found, None if new thread should be created.
        Deterministic: same fragment and state always produces same result.
        """
        if not thread_states:
            return None
        
        # Score each thread
        scores: List[Tuple[float, str, ThreadId]] = []
        
        for thread_id_str, snapshot in thread_states.items():
            # Skip terminated threads
            if snapshot.lifecycle_state == ThreadLifecycleState.TERMINATED:
                continue
            
            score = self._compute_match_score(fragment, snapshot)
            if score > 0:
                scores.append((score, thread_id_str, snapshot.thread_id))
        
        if not scores:
            return None
        
        # Sort by score descending, then by thread_id for determinism
        scores.sort(key=lambda x: (-x[0], x[1]))
        
        # Return best match if score exceeds threshold
        best_score, _, best_thread_id = scores[0]
        if best_score >= 0.3:  # Minimum match threshold
            return best_thread_id
        
        return None
    
    def _compute_match_score(
        self,
        fragment: NormalizedFragment,
        snapshot: ThreadStateSnapshot
    ) -> float:
        """
        Compute match score between fragment and thread.
        
        Score factors:
        - Topic overlap (0.0 to 0.5)
        - Temporal proximity (0.0 to 0.3)
        - Entity overlap (0.0 to 0.2)
        """
        score = 0.0
        
        # Topic overlap
        fragment_topic_ids = {t.topic_id for t in fragment.canonical_topics}
        thread_topic_ids = {t.topic_id for t in snapshot.canonical_topics}
        
        if fragment_topic_ids and thread_topic_ids:
            overlap = len(fragment_topic_ids & thread_topic_ids)
            union = len(fragment_topic_ids | thread_topic_ids)
            topic_score = (overlap / union) * 0.5
            score += topic_score
        
        # Temporal proximity
        if snapshot.last_activity_timestamp:
            fragment_time = fragment.normalization_timestamp.value
            last_activity = snapshot.last_activity_timestamp.value
            
            time_diff = abs((fragment_time - last_activity).total_seconds())
            if time_diff <= self._temporal_window_seconds:
                proximity = 1.0 - (time_diff / self._temporal_window_seconds)
                score += proximity * 0.3
        
        # Entity overlap (simplified)
        fragment_entity_ids = {e.entity_id for e in fragment.canonical_entities}
        # Would need entity tracking in snapshot for full implementation
        # For now, just use topic matching
        
        return score


# =============================================================================
# LIFECYCLE STATE MACHINE (Deterministic transitions)
# =============================================================================

class LifecycleStateMachine:
    """
    Manage thread lifecycle state transitions.
    
    All transitions are explicit and deterministic.
    Invalid transitions are rejected with explicit errors.
    """
    
    # Valid transitions: from_state -> set of valid to_states
    _VALID_TRANSITIONS: Dict[ThreadLifecycleState, Set[ThreadLifecycleState]] = {
        ThreadLifecycleState.EMERGING: {
            ThreadLifecycleState.ACTIVE,
            ThreadLifecycleState.TERMINATED,
        },
        ThreadLifecycleState.ACTIVE: {
            ThreadLifecycleState.DORMANT,
            ThreadLifecycleState.TERMINATED,
            ThreadLifecycleState.DIVERGED,
        },
        ThreadLifecycleState.DORMANT: {
            ThreadLifecycleState.ACTIVE,
            ThreadLifecycleState.TERMINATED,
        },
        ThreadLifecycleState.TERMINATED: set(),  # Terminal state
        ThreadLifecycleState.DIVERGED: {
            ThreadLifecycleState.TERMINATED,
        },
    }
    
    # Thresholds for automatic transitions
    ACTIVE_FRAGMENT_THRESHOLD = 3
    DORMANCY_SECONDS = 86400 * 14  # 14 days without activity
    
    def compute_new_state(
        self,
        current_state: ThreadLifecycleState,
        fragment_count: int,
        last_activity: Optional[Timestamp],
        current_time: Timestamp
    ) -> ThreadLifecycleState:
        """
        Compute new lifecycle state based on activity.
        
        Returns the new state. If no change needed, returns current state.
        Deterministic: same inputs always produce same output.
        """
        # Check for transition to ACTIVE from EMERGING
        if current_state == ThreadLifecycleState.EMERGING:
            if fragment_count >= self.ACTIVE_FRAGMENT_THRESHOLD:
                return ThreadLifecycleState.ACTIVE
        
        # Check for transition to DORMANT from ACTIVE
        if current_state == ThreadLifecycleState.ACTIVE and last_activity:
            time_since_activity = (
                current_time.value - last_activity.value
            ).total_seconds()
            
            if time_since_activity > self.DORMANCY_SECONDS:
                return ThreadLifecycleState.DORMANT
        
        # Check for reactivation from DORMANT
        if current_state == ThreadLifecycleState.DORMANT:
            # If we're computing state due to new fragment, reactivate
            return ThreadLifecycleState.ACTIVE
        
        return current_state
    
    def validate_transition(
        self,
        from_state: ThreadLifecycleState,
        to_state: ThreadLifecycleState
    ) -> bool:
        """Check if a state transition is valid."""
        if from_state == to_state:
            return True
        return to_state in self._VALID_TRANSITIONS.get(from_state, set())


# =============================================================================
# DIVERGENCE DETECTOR (Identifies incompatible evolution paths)
# =============================================================================

class DivergenceDetector:
    """
    Detect when a narrative thread has diverged into incompatible paths.
    
    Divergence is detected when:
    - Multiple contradicting fragments are present
    - Fragments suggest mutually exclusive outcomes
    
    Divergence is FLAGGED, not resolved. Both paths remain valid.
    """
    
    CONTRADICTION_THRESHOLD = 2  # Number of contradictions before divergence
    
    def check_divergence(
        self,
        thread_id: ThreadId,
        current_snapshot: ThreadStateSnapshot,
        new_fragment: NormalizedFragment
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if adding fragment causes divergence.
        
        Returns (is_diverged, reason) tuple.
        """
        # Count existing contradictions
        contradiction_count = sum(
            1 for rel in current_snapshot.relations
            if rel.relation_type == FragmentRelationType.CONTRADICTION
        )
        
        # Add new contradictions from this fragment
        if new_fragment.contradiction_info.status == ContradictionStatus.CONTRADICTION_DETECTED:
            contradiction_count += len(
                new_fragment.contradiction_info.contradicting_fragment_ids
            )
        
        if contradiction_count >= self.CONTRADICTION_THRESHOLD:
            return True, f"Thread has {contradiction_count} contradictions, indicating divergent paths"
        
        return False, None


# =============================================================================
# ABSENCE DETECTOR (Detects missing expected activity)
# =============================================================================

class AbsenceDetector:
    """
    Detect absence of expected activity in a thread.
    
    Absence is a first-class concept - the lack of information is itself
    meaningful and tracked explicitly.
    """
    
    def check_absence(
        self,
        snapshot: ThreadStateSnapshot,
        current_time: Timestamp
    ) -> Tuple[bool, Optional[int]]:
        """
        Check if a thread has unexpected absence of activity.
        
        Returns (is_absent, absence_duration_seconds) tuple.
        """
        if not snapshot.last_activity_timestamp:
            return False, None
        
        if not snapshot.expected_activity_interval_seconds:
            return False, None
        
        time_since_activity = (
            current_time.value - snapshot.last_activity_timestamp.value
        ).total_seconds()
        
        if time_since_activity > snapshot.expected_activity_interval_seconds:
            return True, int(time_since_activity)
        
        return False, None


# =============================================================================
# CORE NARRATIVE STATE ENGINE
# =============================================================================

@dataclass
class NarrativeEngineConfig:
    """Configuration for narrative state engine."""
    temporal_window_seconds: int = 86400 * 7  # 7 days
    active_fragment_threshold: int = 3
    dormancy_seconds: int = 86400 * 14  # 14 days
    enable_divergence_detection: bool = True


class NarrativeStateEngine:
    """
    Core Narrative State Engine.
    
    BOUNDARY ENFORCEMENT:
    - Consumes ONLY NormalizedFragment from normalization layer
    - Produces ONLY NarrativeStateEvent objects
    - All state changes create NEW immutable snapshots
    - No in-place mutation, no persistence, no queries
    
    This engine operates on in-memory state. Persistence is handled
    by the storage layer, which consumes NarrativeStateEvent outputs.
    """
    
    def __init__(self, config: Optional[NarrativeEngineConfig] = None):
        self._config = config or NarrativeEngineConfig()
        
        # Internal state (immutable snapshots only)
        self._current_snapshots: Dict[str, ThreadStateSnapshot] = {}
        self._version_counter: Dict[str, int] = {}
        
        # Component modules
        self._thread_matcher = ThreadMatcher(
            temporal_window_seconds=self._config.temporal_window_seconds
        )
        self._lifecycle_machine = LifecycleStateMachine()
        self._lifecycle_machine.ACTIVE_FRAGMENT_THRESHOLD = self._config.active_fragment_threshold
        self._lifecycle_machine.DORMANCY_SECONDS = self._config.dormancy_seconds
        self._divergence_detector = DivergenceDetector()
        self._absence_detector = AbsenceDetector()
        
        # Event log (internal, for replay support)
        self._event_log: List[NarrativeStateEvent] = []
        self._audit_log: List[AuditLogEntry] = []
    
    def process_fragment(self, fragment: NormalizedFragment) -> FragmentProcessingOutcome:
        """
        Process a normalized fragment into the narrative state.
        
        This is the primary entry point. Returns immutable outcome
        with the result of processing and any state events emitted.
        """
        # Skip duplicates
        if fragment.duplicate_info.status in (
            DuplicateStatus.EXACT_DUPLICATE, 
            DuplicateStatus.NEAR_DUPLICATE
        ):
            return FragmentProcessingOutcome(
                result=ThreadProcessingResult.DUPLICATE_SKIPPED,
                thread_id=None,
                state_event=None
            )
        
        # Find matching thread or create new one
        matching_thread_id = self._thread_matcher.find_matching_thread(
            fragment=fragment,
            thread_states=self._current_snapshots
        )
        
        if matching_thread_id:
            return self._add_to_existing_thread(matching_thread_id, fragment)
        else:
            return self._create_new_thread(fragment)
    
    def _create_new_thread(self, fragment: NormalizedFragment) -> FragmentProcessingOutcome:
        """Create a new thread from a fragment."""
        # Generate thread ID from fragment
        thread_id = ThreadId.generate(f"thread_from_{fragment.fragment_id.value}")
        
        # Create initial version
        version_id = VersionId.generate(thread_id.value, 1, None)
        
        # Create initial snapshot
        snapshot = ThreadStateSnapshot(
            version_id=version_id,
            thread_id=thread_id,
            lifecycle_state=ThreadLifecycleState.EMERGING,
            member_fragment_ids=(fragment.fragment_id,),
            canonical_topics=fragment.canonical_topics,
            relations=(),
            created_at=Timestamp.now(),
            previous_version_id=None,
            last_activity_timestamp=fragment.normalization_timestamp,
        )
        
        # Store snapshot
        self._current_snapshots[thread_id.value] = snapshot
        self._version_counter[thread_id.value] = 1
        
        # Create state event
        event = self._create_state_event(
            event_type="thread_created",
            thread_id=thread_id,
            snapshot=snapshot,
            trigger_fragment_id=fragment.fragment_id
        )
        self._event_log.append(event)
        
        self._log_audit(
            action="thread_created",
            entity_id=thread_id.value,
            metadata=(
                ("fragment_id", fragment.fragment_id.value),
                ("topics", ",".join(t.topic_id for t in fragment.canonical_topics)),
            )
        )
        
        return FragmentProcessingOutcome(
            result=ThreadProcessingResult.NEW_THREAD_CREATED,
            thread_id=thread_id,
            state_event=event
        )
    
    def _add_to_existing_thread(
        self,
        thread_id: ThreadId,
        fragment: NormalizedFragment
    ) -> FragmentProcessingOutcome:
        """Add fragment to an existing thread."""
        current_snapshot = self._current_snapshots.get(thread_id.value)
        
        if not current_snapshot:
            return FragmentProcessingOutcome(
                result=ThreadProcessingResult.PROCESSING_FAILED,
                error=Error(
                    code=ErrorCode.THREAD_NOT_FOUND,
                    message=f"Thread {thread_id.value} not found",
                    timestamp=Timestamp.now().value
                )
            )
        
        # Check for divergence
        if self._config.enable_divergence_detection:
            is_diverged, divergence_reason = self._divergence_detector.check_divergence(
                thread_id=thread_id,
                current_snapshot=current_snapshot,
                new_fragment=fragment
            )
            if is_diverged:
                return self._handle_divergence(
                    thread_id=thread_id,
                    current_snapshot=current_snapshot,
                    fragment=fragment,
                    reason=divergence_reason
                )
        
        # Build new relations
        new_relations = list(current_snapshot.relations)
        
        # Add contradiction relations if applicable
        if fragment.contradiction_info.status == ContradictionStatus.CONTRADICTION_DETECTED:
            for contradicting_id in fragment.contradiction_info.contradicting_fragment_ids:
                relation = FragmentRelation(
                    source_fragment_id=fragment.fragment_id,
                    target_fragment_id=contradicting_id,
                    relation_type=FragmentRelationType.CONTRADICTION,
                    confidence=0.9,  # High confidence from contradiction detector
                    detected_at=Timestamp.now()
                )
                new_relations.append(relation)
        
        # Compute new lifecycle state
        new_fragment_count = len(current_snapshot.member_fragment_ids) + 1
        new_lifecycle_state = self._lifecycle_machine.compute_new_state(
            current_state=current_snapshot.lifecycle_state,
            fragment_count=new_fragment_count,
            last_activity=current_snapshot.last_activity_timestamp,
            current_time=Timestamp.now()
        )
        
        # Merge topics
        all_topics = set(current_snapshot.canonical_topics) | set(fragment.canonical_topics)
        
        # Create new version
        self._version_counter[thread_id.value] += 1
        new_version_id = VersionId.generate(
            thread_id.value,
            self._version_counter[thread_id.value],
            current_snapshot.version_id.value
        )
        
        # Create new snapshot (immutable - replaces old one)
        new_snapshot = ThreadStateSnapshot(
            version_id=new_version_id,
            thread_id=thread_id,
            lifecycle_state=new_lifecycle_state,
            member_fragment_ids=current_snapshot.member_fragment_ids + (fragment.fragment_id,),
            canonical_topics=tuple(sorted(all_topics, key=lambda t: t.topic_id)),
            relations=tuple(new_relations),
            created_at=Timestamp.now(),
            previous_version_id=current_snapshot.version_id.value,
            last_activity_timestamp=fragment.normalization_timestamp,
            expected_activity_interval_seconds=current_snapshot.expected_activity_interval_seconds,
        )
        
        # Replace current snapshot
        self._current_snapshots[thread_id.value] = new_snapshot
        
        # Determine event type
        event_type = "thread_updated"
        if new_lifecycle_state != current_snapshot.lifecycle_state:
            event_type = "state_transition"
        elif fragment.contradiction_info.status == ContradictionStatus.CONTRADICTION_DETECTED:
            event_type = "contradiction_added"
        
        # Create state event
        event = self._create_state_event(
            event_type=event_type,
            thread_id=thread_id,
            snapshot=new_snapshot,
            trigger_fragment_id=fragment.fragment_id
        )
        self._event_log.append(event)
        
        # Determine processing result
        if fragment.contradiction_info.status == ContradictionStatus.CONTRADICTION_DETECTED:
            result = ThreadProcessingResult.CONTRADICTION_RECORDED
        else:
            result = ThreadProcessingResult.ADDED_TO_EXISTING
        
        self._log_audit(
            action="fragment_added_to_thread",
            entity_id=thread_id.value,
            metadata=(
                ("fragment_id", fragment.fragment_id.value),
                ("version", str(new_version_id.sequence)),
                ("lifecycle_state", new_lifecycle_state.value),
            )
        )
        
        return FragmentProcessingOutcome(
            result=result,
            thread_id=thread_id,
            state_event=event
        )
    
    def _handle_divergence(
        self,
        thread_id: ThreadId,
        current_snapshot: ThreadStateSnapshot,
        fragment: NormalizedFragment,
        reason: Optional[str]
    ) -> FragmentProcessingOutcome:
        """Handle a divergence in the narrative thread."""
        # Create new version with DIVERGED state
        self._version_counter[thread_id.value] += 1
        new_version_id = VersionId.generate(
            thread_id.value,
            self._version_counter[thread_id.value],
            current_snapshot.version_id.value
        )
        
        # Create diverged snapshot
        diverged_snapshot = ThreadStateSnapshot(
            version_id=new_version_id,
            thread_id=thread_id,
            lifecycle_state=ThreadLifecycleState.DIVERGED,
            member_fragment_ids=current_snapshot.member_fragment_ids + (fragment.fragment_id,),
            canonical_topics=current_snapshot.canonical_topics,
            relations=current_snapshot.relations,
            created_at=Timestamp.now(),
            previous_version_id=current_snapshot.version_id.value,
            last_activity_timestamp=fragment.normalization_timestamp,
            diverged_from_version_id=current_snapshot.version_id.value,
            divergence_reason=reason,
        )
        
        self._current_snapshots[thread_id.value] = diverged_snapshot
        
        event = self._create_state_event(
            event_type="divergence_detected",
            thread_id=thread_id,
            snapshot=diverged_snapshot,
            trigger_fragment_id=fragment.fragment_id
        )
        self._event_log.append(event)
        
        self._log_audit(
            action="thread_diverged",
            entity_id=thread_id.value,
            metadata=(
                ("reason", reason or "unknown"),
                ("fragment_id", fragment.fragment_id.value),
            )
        )
        
        return FragmentProcessingOutcome(
            result=ThreadProcessingResult.DIVERGENCE_DETECTED,
            thread_id=thread_id,
            state_event=event
        )
    
    def _create_state_event(
        self,
        event_type: str,
        thread_id: ThreadId,
        snapshot: ThreadStateSnapshot,
        trigger_fragment_id: Optional[FragmentId] = None
    ) -> NarrativeStateEvent:
        """Create an immutable state event."""
        event_id = hashlib.sha256(
            f"{event_type}|{thread_id.value}|{Timestamp.now().value.timestamp()}".encode()
        ).hexdigest()[:16]
        
        return NarrativeStateEvent(
            event_id=f"evt_{event_id}",
            event_type=event_type,
            thread_id=thread_id,
            timestamp=Timestamp.now(),
            new_state_snapshot=snapshot,
            trigger_fragment_id=trigger_fragment_id
        )
    
    def get_current_snapshot(self, thread_id: ThreadId) -> Optional[ThreadStateSnapshot]:
        """Get current snapshot for a thread (read-only)."""
        return self._current_snapshots.get(thread_id.value)
    
    def get_all_current_snapshots(self) -> Dict[str, ThreadStateSnapshot]:
        """Get all current thread snapshots (read-only)."""
        return dict(self._current_snapshots)
    
    def get_event_log(self) -> List[NarrativeStateEvent]:
        """Get copy of event log (for replay/audit)."""
        return list(self._event_log)
    
    def _log_audit(
        self,
        action: str,
        entity_id: Optional[str] = None,
        metadata: tuple = ()
    ):
        """Add entry to internal audit log."""
        entry_id = hashlib.sha256(
            f"core_{action}|{Timestamp.now().value.timestamp()}".encode()
        ).hexdigest()[:16]
        
        entry = AuditLogEntry(
            entry_id=f"audit_{entry_id}",
            event_type=AuditEventType.STATE_CHANGE,
            timestamp=Timestamp.now(),
            layer="core",
            action=action,
            entity_id=entity_id,
            entity_type="thread",
            metadata=metadata
        )
        self._audit_log.append(entry)
    
    def get_audit_log(self) -> List[AuditLogEntry]:
        """Return copy of audit log entries."""
        return list(self._audit_log)
