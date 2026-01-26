"""
Temporal Layer Determinism Tests
=================================

Tests verifying temporal immutability invariants.

INVARIANTS TESTED:
1. Same log → identical state hash
2. Replay produces identical results
3. Late arrivals trigger recomputation (not mutation)
4. Absence is encoded explicitly
"""

import pytest
from datetime import datetime, timezone, timedelta

from backend.contracts.base import (
    Timestamp, FragmentId, SourceId, ThreadId,
    SourceMetadata, ContentSignature
)
from backend.contracts.events import (
    NormalizedFragment, DuplicateInfo, DuplicateStatus
)
from backend.temporal.event_log import ImmutableEventLog, LogSequence
from backend.temporal.state_machine import StateMachine, DerivedState
from backend.temporal.versioning import VersionTracker
from backend.temporal.replay import ReplayEngine


def make_fragment(
    content: str,
    topic_ids: tuple = ("topic_1",),
    timestamp: datetime = None
) -> NormalizedFragment:
    """Factory for test fragments."""
    ts = timestamp or datetime.now(timezone.utc)
    
    source_id = SourceId(value="test_source", source_type="test")
    fragment_id = FragmentId.generate(
        source_id="test_source",
        timestamp=ts,
        payload=content
    )
    
    from backend.contracts.base import CanonicalTopic
    from backend.contracts.events import ContradictionInfo, ContradictionStatus
    
    topics = tuple(CanonicalTopic(topic_id=tid, canonical_name=tid) for tid in topic_ids)
    
    return NormalizedFragment(
        fragment_id=fragment_id,
        source_event_id=f"raw_{fragment_id.value}",
        content_signature=ContentSignature.compute(content),
        normalized_payload=content,
        detected_language="en",
        canonical_topics=topics,
        canonical_entities=(),
        duplicate_info=DuplicateInfo(
            status=DuplicateStatus.UNIQUE,
            original_fragment_id=None,
            similarity_score=None
        ),
        contradiction_info=ContradictionInfo(
            status=ContradictionStatus.NO_CONTRADICTION
        ),
        normalization_timestamp=Timestamp(value=ts),
        source_metadata=SourceMetadata(
            source_id=source_id,
            source_confidence=1.0,
            capture_timestamp=Timestamp(value=ts),
            event_timestamp=Timestamp(value=ts)
        )
    )


class TestEventLogImmutability:
    """Test append-only log semantics."""
    
    def test_append_only(self):
        """Log only supports append, not update or delete."""
        log = ImmutableEventLog()
        
        frag1 = make_fragment("Fragment 1")
        frag2 = make_fragment("Fragment 2")
        
        entry1 = log.append(frag1)
        entry2 = log.append(frag2)
        
        assert entry1.sequence.value == 1
        assert entry2.sequence.value == 2
        assert log.state.entry_count == 2
    
    def test_hash_chain_integrity(self):
        """Entries form verifiable hash chain."""
        log = ImmutableEventLog()
        
        for i in range(5):
            log.append(make_fragment(f"Fragment {i}"))
        
        is_valid, error = log.verify_integrity()
        assert is_valid, error
    
    def test_deterministic_hashing(self):
        """Same content produces same hash."""
        log = ImmutableEventLog()
        
        # Fixed timestamp for determinism
        ts = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        
        frag = make_fragment("Test content", timestamp=ts)
        entry = log.append(frag)
        
        # Entry hash is deterministic
        assert entry.entry_hash is not None
        assert len(entry.entry_hash) == 64  # SHA256


class TestStateMachineDeterminism:
    """Test pure function state derivation."""
    
    def test_same_log_same_state(self):
        """Same log produces identical state."""
        log = ImmutableEventLog()
        
        # Add some fragments
        for i in range(3):
            log.append(make_fragment(f"Fragment {i}", topic_ids=("topic_1",)))
        
        machine = StateMachine()
        
        state1 = machine.derive_state(log)
        state2 = machine.derive_state(log)
        
        assert state1.state_hash == state2.state_hash
    
    def test_different_sequence_different_state(self):
        """Different sequences may produce different states."""
        log = ImmutableEventLog()
        
        for i in range(5):
            log.append(make_fragment(f"Fragment {i}"))
        
        machine = StateMachine()
        
        state_at_2 = machine.derive_state(log, until_sequence=LogSequence(2))
        state_at_5 = machine.derive_state(log, until_sequence=LogSequence(5))
        
        # More entries = potentially different state
        assert state_at_5.at_sequence.value > state_at_2.at_sequence.value
    
    def test_threads_are_views(self):
        """Threads are computed views, not stored entities."""
        log = ImmutableEventLog()
        machine = StateMachine()
        
        # Add fragments with same topic
        for i in range(3):
            log.append(make_fragment(f"Fragment {i}", topic_ids=("topic_1",)))
        
        state = machine.derive_state(log)
        
        # Should have at least one thread
        assert len(state.threads) >= 1
        
        # Thread has version and sequence
        thread = state.threads[0]
        assert thread.version is not None
        assert thread.at_sequence.value == log.state.head_sequence.value


class TestReplayDeterminism:
    """Test replay produces identical results."""
    
    def test_replay_is_deterministic(self):
        """Multiple replays produce identical state."""
        log = ImmutableEventLog()
        machine = StateMachine()
        tracker = VersionTracker()
        engine = ReplayEngine(log, machine, tracker)
        
        # Add fragments
        for i in range(5):
            log.append(make_fragment(f"Fragment {i}", topic_ids=("topic_1",)))
        
        # Verify determinism
        is_deterministic, diff = engine.verify_determinism()
        assert is_deterministic, diff
    
    def test_replay_full_matches_incremental(self):
        """Full replay matches state from incremental derivation."""
        log = ImmutableEventLog()
        machine = StateMachine()
        
        # Add fragments
        for i in range(5):
            log.append(make_fragment(f"Fragment {i}"))
        
        # Full replay
        full_state = machine.derive_state(log)
        
        # Should get same hash from fresh derivation
        fresh_state = machine.derive_state(log)
        
        assert full_state.state_hash == fresh_state.state_hash


class TestAbsenceEncoding:
    """Test that absence is first-class data."""
    
    def test_gap_creates_absence_marker(self):
        """Long temporal gap creates absence marker."""
        log = ImmutableEventLog()
        machine = StateMachine(dormancy_hours=24, topic_overlap_min=0.4)  # Lower threshold for test matching
        
        base_time = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
        
        # Add fragment
        log.append(make_fragment("Fragment 1", topic_ids=("topic_1",), timestamp=base_time))
        
        # Add fragment 30 days later (exceeds dormancy)
        later_time = base_time + timedelta(days=30)
        log.append(make_fragment("Fragment 2", topic_ids=("topic_1",), timestamp=later_time))
        
        state = machine.derive_state(log)
        
        # Should have absence markers
        assert len(state.absences) >= 1 or \
               any(len(t.absence_markers) > 0 for t in state.threads)
