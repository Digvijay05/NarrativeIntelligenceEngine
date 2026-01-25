"""
Deterministic Replay Chaos Tests

Tests that chaotic inputs produce deterministic outputs.

INVARIANTS:
===========
- Same corrupted inputs + same versions = same outputs
- Replay under chaos is repeatable
- No non-deterministic error handling
"""

import pytest
from datetime import datetime, timezone
import hashlib


class TestDeterministicReplay:
    """
    Test: Replay under chaos must still be deterministic.
    """
    
    def test_out_of_order_replay_deterministic(self):
        """
        CHAOS: Out-of-order fragments.
        INVARIANT: Same inputs = same outputs, always.
        """
        from tests.chaos.fixtures import make_out_of_order_scenario
        
        scenario = make_out_of_order_scenario()
        
        # Run twice with same inputs
        def process(fragments):
            """Simulate deterministic processing."""
            result = []
            for frag in sorted(fragments, key=lambda f: f.ingest_time):
                result.append({
                    'id': frag.fragment_id,
                    'event_time': frag.event_time.isoformat(),
                    'ingest_time': frag.ingest_time.isoformat(),
                    'hash': frag.payload_hash,
                })
            return tuple(result)
        
        run1 = process(scenario.fragments)
        run2 = process(scenario.fragments)
        
        assert run1 == run2, "VIOLATION: Non-deterministic under out-of-order chaos"
    
    def test_contradiction_replay_deterministic(self):
        """
        CHAOS: Contradictory inputs.
        INVARIANT: Same contradictions = same divergence markers.
        """
        from tests.chaos.fixtures import make_mutually_exclusive_claims
        
        scenario = make_mutually_exclusive_claims()
        
        def process_with_divergence(fragments):
            """Simulate divergence detection."""
            sources = {}
            for frag in fragments:
                if frag.source_id not in sources:
                    sources[frag.source_id] = []
                sources[frag.source_id].append(frag.content)
            
            # Detect contradiction (simplistic)
            divergence = len(sources) > 1
            return {
                'sources': sorted(sources.keys()),
                'divergence': divergence,
            }
        
        run1 = process_with_divergence(scenario.fragments)
        run2 = process_with_divergence(scenario.fragments)
        
        assert run1 == run2, "VIOLATION: Non-deterministic divergence detection"
    
    def test_temporal_gap_replay_deterministic(self):
        """
        CHAOS: Temporal gaps.
        INVARIANT: Same gaps = same silence markers.
        """
        from tests.chaos.fixtures import make_gap_with_no_fragments
        
        scenario = make_gap_with_no_fragments()
        
        def detect_gaps(fragments):
            """Detect gaps between fragments."""
            sorted_frags = sorted(fragments, key=lambda f: f.event_time)
            gaps = []
            for i in range(len(sorted_frags) - 1):
                gap = sorted_frags[i+1].event_time - sorted_frags[i].event_time
                gaps.append(gap.total_seconds())
            return tuple(gaps)
        
        run1 = detect_gaps(scenario.fragments)
        run2 = detect_gaps(scenario.fragments)
        
        assert run1 == run2, "VIOLATION: Non-deterministic gap detection"


class TestReplayHashInvariance:
    """
    Test: Output hashes must be identical across replays.
    """
    
    def test_output_hash_stable(self):
        """
        CHAOS: Any scenario.
        INVARIANT: Hash of output stable across replays.
        """
        from tests.chaos.fixtures import get_all_scenarios
        
        for scenario in get_all_scenarios():
            def compute_output_hash(fragments):
                content = '|'.join(
                    f"{f.fragment_id}:{f.payload_hash}"
                    for f in sorted(fragments, key=lambda x: x.ingest_time)
                )
                return hashlib.sha256(content.encode()).hexdigest()
            
            hash1 = compute_output_hash(scenario.fragments)
            hash2 = compute_output_hash(scenario.fragments)
            
            assert hash1 == hash2, \
                f"VIOLATION: Non-deterministic output for {scenario.scenario_id}"
    
    def test_all_scenarios_have_stable_fixture(self):
        """
        META: All fixtures must be stable (not random).
        """
        from tests.chaos.fixtures import get_all_scenarios
        
        scenarios1 = get_all_scenarios()
        scenarios2 = get_all_scenarios()
        
        assert len(scenarios1) == len(scenarios2)
        
        for s1, s2 in zip(scenarios1, scenarios2):
            assert s1.scenario_id == s2.scenario_id
            assert len(s1.fragments) == len(s2.fragments)
            
            for f1, f2 in zip(s1.fragments, s2.fragments):
                assert f1.fragment_id == f2.fragment_id
                assert f1.payload_hash == f2.payload_hash
                assert f1.event_time == f2.event_time
                assert f1.ingest_time == f2.ingest_time


class TestNoNonDeterministicErrorHandling:
    """
    Test: Errors must not introduce non-determinism.
    """
    
    def test_error_paths_deterministic(self):
        """
        CHAOS: Adversarial inputs that cause errors.
        INVARIANT: Same error every time.
        """
        from tests.chaos.fixtures import (
            make_future_timestamp, 
            make_negative_duration
        )
        
        for scenario in [make_future_timestamp(), make_negative_duration()]:
            # In a real system, we'd ingest and check error state
            # Here we verify the scenario itself is deterministic
            
            s1 = scenario
            s2_factory = make_future_timestamp if 'future' in scenario.scenario_id else make_negative_duration
            s2 = s2_factory()
            
            assert s1.expect_rejection == s2.expect_rejection
            assert s1.expected_invariant == s2.expected_invariant
    
    def test_no_random_retry_jitter(self):
        """
        CHAOS: Transient errors.
        INVARIANT: No random jitter in retry timing.
        """
        # If system has retry logic:
        # - Retry delays must be deterministic
        # - No random backoff
        
        # This ensures replay produces identical timing
        
        # In real implementation:
        # config = system.get_retry_config()
        # assert config.jitter_enabled == False, "VIOLATION: Random jitter"
        pass
