"""
Chaos Fixtures

Explicit corruption scenarios for temporal chaos testing.

RULES:
======
1. All fixtures are EXPLICIT, not random
2. Each fixture declares corruption type
3. Each fixture documents expected invariant
4. No fixture should "look reasonable"
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
from datetime import datetime, timezone, timedelta
from enum import Enum


# =============================================================================
# CORRUPTION TYPES
# =============================================================================

class CorruptionType(Enum):
    """Type of temporal corruption being injected."""
    OUT_OF_ORDER = "out_of_order"
    TEMPORAL_GAP = "temporal_gap"
    CONTRADICTION = "contradiction"
    DELAYED_FLOOD = "delayed_flood"
    ADVERSARIAL_NOISE = "adversarial_noise"


class ExpectedInvariant(Enum):
    """What invariant this test expects to hold."""
    IMMUTABILITY_PRESERVED = "immutability_preserved"
    DIVERGENCE_SURFACED = "divergence_surfaced"
    ABSENCE_PRESERVED = "absence_preserved"
    DETERMINISTIC_REPLAY = "deterministic_replay"
    EXPLICIT_FAILURE = "explicit_failure"


# =============================================================================
# BASE CORRUPTION FIXTURE
# =============================================================================

@dataclass(frozen=True)
class CorruptedFragment:
    """A fragment with potential temporal corruption."""
    fragment_id: str
    source_id: str
    content: str
    event_time: datetime  # When event supposedly happened
    ingest_time: datetime  # When we received it
    payload_hash: str
    
    @property
    def is_late(self) -> bool:
        """Fragment arrived significantly after event."""
        return (self.ingest_time - self.event_time) > timedelta(hours=1)
    
    @property
    def is_future(self) -> bool:
        """Fragment claims to be from the future."""
        return self.event_time > self.ingest_time


@dataclass(frozen=True)
class ChaosScenario:
    """A complete chaos test scenario."""
    scenario_id: str
    corruption_type: CorruptionType
    expected_invariant: ExpectedInvariant
    description: str
    fragments: Tuple[CorruptedFragment, ...]
    
    # Expected outcomes
    expect_divergence: bool = False
    expect_rejection: bool = False
    expect_explicit_gap: bool = False
    expect_parallel_threads: bool = False


# =============================================================================
# OUT-OF-ORDER INGESTION FIXTURES
# =============================================================================

def make_out_of_order_scenario() -> ChaosScenario:
    """
    Fragments where event_time ≪ ingest_time.
    
    SCENARIO: Breaking news happened at 10:00.
    Thread established with fragments at 10:00-10:30.
    At 14:00, a late fragment arrives claiming to be from 09:45.
    
    EXPECTED: System must NOT retroactively mutate the 10:00-10:30 narrative.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        # Normal fragments (event_time ≈ ingest_time)
        CorruptedFragment(
            fragment_id="frag_001",
            source_id="source_a",
            content="Breaking: Event X happened",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=2),
            payload_hash="hash_001"
        ),
        CorruptedFragment(
            fragment_id="frag_002",
            source_id="source_b",
            content="Update on Event X",
            event_time=base_time + timedelta(minutes=15),
            ingest_time=base_time + timedelta(minutes=17),
            payload_hash="hash_002"
        ),
        CorruptedFragment(
            fragment_id="frag_003",
            source_id="source_a",
            content="Event X developing",
            event_time=base_time + timedelta(minutes=30),
            ingest_time=base_time + timedelta(minutes=32),
            payload_hash="hash_003"
        ),
        # LATE ARRIVAL: Claims to predate first fragment
        CorruptedFragment(
            fragment_id="frag_late_004",
            source_id="source_c",
            content="Earlier report: Event X was predicted",
            event_time=base_time - timedelta(minutes=15),  # Claims 09:45
            ingest_time=base_time + timedelta(hours=4),    # Arrives at 14:00
            payload_hash="hash_late_004"
        ),
    )
    
    return ChaosScenario(
        scenario_id="out_of_order_001",
        corruption_type=CorruptionType.OUT_OF_ORDER,
        expected_invariant=ExpectedInvariant.IMMUTABILITY_PRESERVED,
        description="Late fragment claims to predate established narrative",
        fragments=fragments,
        expect_divergence=True,
    )


def make_post_dormancy_arrival() -> ChaosScenario:
    """
    Fragment arrives after thread marked dormant.
    
    EXPECTED: Dormancy state must not be silently undone.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        CorruptedFragment(
            fragment_id="frag_d001",
            source_id="source_a",
            content="Story begins",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=1),
            payload_hash="hash_d001"
        ),
        # 24+ hours of silence would mark thread dormant
        # Then this arrives:
        CorruptedFragment(
            fragment_id="frag_d002",
            source_id="source_a",
            content="Story continues (arriving very late)",
            event_time=base_time + timedelta(hours=2),
            ingest_time=base_time + timedelta(hours=48),
            payload_hash="hash_d002"
        ),
    )
    
    return ChaosScenario(
        scenario_id="post_dormancy_001",
        corruption_type=CorruptionType.OUT_OF_ORDER,
        expected_invariant=ExpectedInvariant.DIVERGENCE_SURFACED,
        description="Fragment arrives after thread dormancy",
        fragments=fragments,
        expect_divergence=True,
    )


# =============================================================================
# TEMPORAL GAP / SILENCE FIXTURES
# =============================================================================

def make_gap_with_no_fragments() -> ChaosScenario:
    """
    Expected continuation window with no fragments.
    
    EXPECTED: Explicit silence marker, not null or inferred continuation.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        CorruptedFragment(
            fragment_id="frag_g001",
            source_id="source_a",
            content="Story starts",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=1),
            payload_hash="hash_g001"
        ),
        # GAP: 4 hours of expected silence
        CorruptedFragment(
            fragment_id="frag_g002",
            source_id="source_a",
            content="Story resumes without explanation",
            event_time=base_time + timedelta(hours=4),
            ingest_time=base_time + timedelta(hours=4, minutes=1),
            payload_hash="hash_g002"
        ),
    )
    
    return ChaosScenario(
        scenario_id="temporal_gap_001",
        corruption_type=CorruptionType.TEMPORAL_GAP,
        expected_invariant=ExpectedInvariant.ABSENCE_PRESERVED,
        description="4-hour gap with no fragments",
        fragments=fragments,
        expect_explicit_gap=True,
    )


def make_sudden_reappearance() -> ChaosScenario:
    """
    Long silence followed by sudden reappearance.
    
    EXPECTED: System must not infer continuity across the gap.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        CorruptedFragment(
            fragment_id="frag_r001",
            source_id="source_a",
            content="Crisis begins",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=1),
            payload_hash="hash_r001"
        ),
        CorruptedFragment(
            fragment_id="frag_r002",
            source_id="source_a",
            content="Crisis ongoing",
            event_time=base_time + timedelta(minutes=30),
            ingest_time=base_time + timedelta(minutes=31),
            payload_hash="hash_r002"
        ),
        # 7 DAYS of silence
        CorruptedFragment(
            fragment_id="frag_r003",
            source_id="source_a",
            content="Crisis suddenly returns",
            event_time=base_time + timedelta(days=7),
            ingest_time=base_time + timedelta(days=7, minutes=1),
            payload_hash="hash_r003"
        ),
    )
    
    return ChaosScenario(
        scenario_id="sudden_reappearance_001",
        corruption_type=CorruptionType.TEMPORAL_GAP,
        expected_invariant=ExpectedInvariant.ABSENCE_PRESERVED,
        description="7-day gap then sudden reappearance",
        fragments=fragments,
        expect_explicit_gap=True,
    )


# =============================================================================
# CONTRADICTORY UPDATE FIXTURES
# =============================================================================

def make_mutually_exclusive_claims() -> ChaosScenario:
    """
    Two sources make simultaneous contradictory claims.
    
    EXPECTED: Both threads must coexist. No resolution.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        CorruptedFragment(
            fragment_id="frag_c001",
            source_id="source_a",
            content="Claim: X is true",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=1),
            payload_hash="hash_c001"
        ),
        CorruptedFragment(
            fragment_id="frag_c002",
            source_id="source_b",
            content="Claim: X is false (contradicts source_a)",
            event_time=base_time + timedelta(minutes=5),
            ingest_time=base_time + timedelta(minutes=6),
            payload_hash="hash_c002"
        ),
    )
    
    return ChaosScenario(
        scenario_id="contradiction_001",
        corruption_type=CorruptionType.CONTRADICTION,
        expected_invariant=ExpectedInvariant.DIVERGENCE_SURFACED,
        description="Mutually exclusive claims from different sources",
        fragments=fragments,
        expect_parallel_threads=True,
        expect_divergence=True,
    )


def make_late_contradiction() -> ChaosScenario:
    """
    Contradiction arrives after narrative seems settled.
    
    EXPECTED: Original narrative immutable. Contradiction surfaces separately.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        CorruptedFragment(
            fragment_id="frag_lc001",
            source_id="source_a",
            content="Official: Event Y happened",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=1),
            payload_hash="hash_lc001"
        ),
        CorruptedFragment(
            fragment_id="frag_lc002",
            source_id="source_a",
            content="Confirmed: Event Y details",
            event_time=base_time + timedelta(hours=1),
            ingest_time=base_time + timedelta(hours=1, minutes=1),
            payload_hash="hash_lc002"
        ),
        CorruptedFragment(
            fragment_id="frag_lc003",
            source_id="source_a",
            content="Narrative settled on Event Y",
            event_time=base_time + timedelta(hours=2),
            ingest_time=base_time + timedelta(hours=2, minutes=1),
            payload_hash="hash_lc003"
        ),
        # Late contradiction
        CorruptedFragment(
            fragment_id="frag_lc_contradict",
            source_id="source_b",
            content="Investigation: Event Y never happened",
            event_time=base_time + timedelta(days=3),
            ingest_time=base_time + timedelta(days=3, minutes=1),
            payload_hash="hash_lc_contradict"
        ),
    )
    
    return ChaosScenario(
        scenario_id="late_contradiction_001",
        corruption_type=CorruptionType.CONTRADICTION,
        expected_invariant=ExpectedInvariant.IMMUTABILITY_PRESERVED,
        description="Contradiction arrives 3 days after settled narrative",
        fragments=fragments,
        expect_divergence=True,
        expect_parallel_threads=True,
    )


# =============================================================================
# DELAYED FLOOD FIXTURES
# =============================================================================

def make_delayed_volume_burst() -> ChaosScenario:
    """
    Burst of fragments from single source arriving late.
    
    EXPECTED: No importance weighting by volume. No thread dominance.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    # Established narrative (sparse)
    existing = [
        CorruptedFragment(
            fragment_id="frag_e001",
            source_id="source_a",
            content="Story develops",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=1),
            payload_hash="hash_e001"
        ),
        CorruptedFragment(
            fragment_id="frag_e002",
            source_id="source_b",
            content="Story continues",
            event_time=base_time + timedelta(minutes=30),
            ingest_time=base_time + timedelta(minutes=31),
            payload_hash="hash_e002"
        ),
    ]
    
    # Flood: 20 fragments from source_c arriving 2 hours late
    flood = [
        CorruptedFragment(
            fragment_id=f"frag_flood_{i:03d}",
            source_id="source_c",
            content=f"Flood fragment {i} - attempting narrative dominance",
            event_time=base_time + timedelta(minutes=i),
            ingest_time=base_time + timedelta(hours=2),  # All arrive at once
            payload_hash=f"hash_flood_{i:03d}"
        )
        for i in range(20)
    ]
    
    return ChaosScenario(
        scenario_id="delayed_flood_001",
        corruption_type=CorruptionType.DELAYED_FLOOD,
        expected_invariant=ExpectedInvariant.IMMUTABILITY_PRESERVED,
        description="20 late fragments attempting volume-based dominance",
        fragments=tuple(existing + flood),
        expect_divergence=True,
    )


# =============================================================================
# ADVERSARIAL NOISE FIXTURES
# =============================================================================

def make_duplicate_timestamp_conflict() -> ChaosScenario:
    """
    Same timestamp with conflicting payload hashes.
    
    EXPECTED: Explicit error or both preserved. No silent resolution.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        CorruptedFragment(
            fragment_id="frag_dup_001a",
            source_id="source_a",
            content="Content version A",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=1),
            payload_hash="hash_A"
        ),
        CorruptedFragment(
            fragment_id="frag_dup_001b",
            source_id="source_a",
            content="Content version B (same timestamp, different hash)",
            event_time=base_time,  # SAME timestamp
            ingest_time=base_time + timedelta(minutes=2),
            payload_hash="hash_B"  # DIFFERENT hash
        ),
    )
    
    return ChaosScenario(
        scenario_id="duplicate_timestamp_001",
        corruption_type=CorruptionType.ADVERSARIAL_NOISE,
        expected_invariant=ExpectedInvariant.DIVERGENCE_SURFACED,
        description="Same timestamp with conflicting content hashes",
        fragments=fragments,
        expect_divergence=True,
    )


def make_future_timestamp() -> ChaosScenario:
    """
    Fragment claims to be from the future.
    
    EXPECTED: Explicit rejection or error marker. No silent normalization.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        CorruptedFragment(
            fragment_id="frag_future_001",
            source_id="source_a",
            content="Normal fragment",
            event_time=base_time,
            ingest_time=base_time + timedelta(minutes=1),
            payload_hash="hash_normal"
        ),
        CorruptedFragment(
            fragment_id="frag_future_002",
            source_id="source_a",
            content="This claims to be from 2027",
            event_time=base_time + timedelta(days=365),  # FUTURE
            ingest_time=base_time + timedelta(minutes=5),
            payload_hash="hash_future"
        ),
    )
    
    return ChaosScenario(
        scenario_id="future_timestamp_001",
        corruption_type=CorruptionType.ADVERSARIAL_NOISE,
        expected_invariant=ExpectedInvariant.EXPLICIT_FAILURE,
        description="Fragment claims future timestamp",
        fragments=fragments,
        expect_rejection=True,
    )


def make_negative_duration() -> ChaosScenario:
    """
    Segment with negative duration (end before start).
    
    EXPECTED: Explicit rejection. No silent fix.
    """
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    
    fragments = (
        CorruptedFragment(
            fragment_id="frag_neg_001",
            source_id="source_a",
            content="Start of segment (claims 11:00)",
            event_time=base_time + timedelta(hours=1),  # 11:00
            ingest_time=base_time + timedelta(hours=1, minutes=1),
            payload_hash="hash_neg_001"
        ),
        CorruptedFragment(
            fragment_id="frag_neg_002",
            source_id="source_a",
            content="End of segment (claims 10:30 - BEFORE start)",
            event_time=base_time + timedelta(minutes=30),  # 10:30 - before 11:00
            ingest_time=base_time + timedelta(hours=1, minutes=2),
            payload_hash="hash_neg_002"
        ),
    )
    
    return ChaosScenario(
        scenario_id="negative_duration_001",
        corruption_type=CorruptionType.ADVERSARIAL_NOISE,
        expected_invariant=ExpectedInvariant.EXPLICIT_FAILURE,
        description="Segment with end before start",
        fragments=fragments,
        expect_rejection=True,
    )


# =============================================================================
# FIXTURE AGGREGATION
# =============================================================================

ALL_CHAOS_SCENARIOS = [
    # Out-of-order
    make_out_of_order_scenario,
    make_post_dormancy_arrival,
    # Temporal gaps
    make_gap_with_no_fragments,
    make_sudden_reappearance,
    # Contradictions
    make_mutually_exclusive_claims,
    make_late_contradiction,
    # Delayed flood
    make_delayed_volume_burst,
    # Adversarial noise
    make_duplicate_timestamp_conflict,
    make_future_timestamp,
    make_negative_duration,
]


def get_all_scenarios() -> List[ChaosScenario]:
    """Get all chaos scenarios for testing."""
    return [factory() for factory in ALL_CHAOS_SCENARIOS]


def get_scenarios_by_type(corruption_type: CorruptionType) -> List[ChaosScenario]:
    """Get scenarios filtered by corruption type."""
    return [
        s for s in get_all_scenarios()
        if s.corruption_type == corruption_type
    ]
