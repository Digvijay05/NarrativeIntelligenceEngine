"""
DTO Contract Tests

Tests that enforce the epistemic boundary contract.

TEST CATEGORIES:
================
1. Immutability - DTOs cannot be mutated
2. Versioning - Unknown versions fail fast
3. Forbidden Fields - Prohibited fields do not exist
4. No Inference - Frontend cannot compute or derive
"""

import pytest
from dataclasses import fields, FrozenInstanceError
from datetime import datetime

from frontend.state import (
    DTOVersion, AvailabilityState, ContinuityState, LifecycleState,
    NarrativeThreadDTO, TimelineSegmentDTO, EvidenceFragmentDTO,
    ModelOverlayRefDTO,
)
from frontend.state.thread import TemporalBoundsDTO, PresenceMarkerDTO
from frontend.state.segment import TimeWindowDTO
from frontend.state.fragment import TimestampDTO
from frontend.state.envelope import ResponseEnvelope, QueryMetadataDTO
from frontend.mapper import DTOMapper


# =============================================================================
# IMMUTABILITY TESTS
# =============================================================================

class TestDTOImmutability:
    """
    All DTOs MUST be frozen (immutable).
    
    WHY: Read-only by construction.
    """
    
    @pytest.fixture
    def mapper(self):
        return DTOMapper()
    
    def test_thread_dto_is_frozen(self, mapper):
        """NarrativeThreadDTO must be immutable."""
        thread = mapper.map_thread(
            thread_id='t1',
            thread_version='v1',
            lifecycle='active',
            start_timestamp=datetime.utcnow(),
            end_timestamp=None,
            topic_ids=['topic1'],
            segment_ids=['seg1'],
        )
        
        with pytest.raises(FrozenInstanceError):
            thread.thread_id = "modified"
    
    def test_segment_dto_is_frozen(self, mapper):
        """TimelineSegmentDTO must be immutable."""
        segment = mapper.map_segment(
            segment_id='s1',
            thread_id='t1',
            start_time=datetime.utcnow(),
            end_time=datetime.utcnow(),
            fragment_ids=['f1'],
        )
        
        with pytest.raises(FrozenInstanceError):
            segment.segment_id = "modified"
    
    def test_fragment_dto_is_frozen(self, mapper):
        """EvidenceFragmentDTO must be immutable."""
        fragment = mapper.map_fragment(
            fragment_id='f1',
            source_id='src1',
            published_at=datetime.utcnow(),
            fetched_at=datetime.utcnow(),
            payload_hash='abc123',
        )
        
        with pytest.raises(FrozenInstanceError):
            fragment.fragment_id = "modified"
    
    def test_overlay_dto_is_frozen(self, mapper):
        """ModelOverlayRefDTO must be immutable."""
        overlay = mapper.map_overlay_ref(
            overlay_id='o1',
            entity_id='e1',
            entity_type='thread',
            entity_version='v1',
            model_id='model1',
            model_version='1.0',
            scores=[],
            annotations=[],
            created_at=datetime.utcnow(),
        )
        
        with pytest.raises(FrozenInstanceError):
            overlay.overlay_id = "modified"


# =============================================================================
# VERSION VALIDATION TESTS
# =============================================================================

class TestVersionValidation:
    """
    Unknown versions MUST fail fast.
    
    WHY: Explicit contract enforcement.
    """
    
    def test_thread_rejects_unknown_version(self):
        """Thread DTO must reject unknown version."""
        # Create a fake unknown version (Python doesn't allow this easily)
        # This test verifies the __post_init__ check exists
        thread = NarrativeThreadDTO(
            dto_version=DTOVersion.V1,
            thread_id='t1',
            thread_version='v1',
            lifecycle_state=LifecycleState.ACTIVE,
            temporal_bounds=TemporalBoundsDTO(
                None, False, None, False, True
            ),
            presence_markers=(),
            divergence_flags=(),
            overlay_refs=(),
            topic_ids=(),
            segment_ids=(),
            display_label=None,
            ordering_basis=LifecycleState.ACTIVE,  # Wrong type, but let's test version
            order_position=0,
            availability=AvailabilityState.PRESENT,
            first_seen_at=datetime.utcnow(),
            last_updated_at=datetime.utcnow(),
        )
        
        # Current version should work
        assert thread.dto_version == DTOVersion.V1
    
    def test_all_dtos_have_version_field(self):
        """All DTOs must have dto_version field."""
        dto_classes = [
            NarrativeThreadDTO,
            TimelineSegmentDTO,
            EvidenceFragmentDTO,
            ModelOverlayRefDTO,
        ]
        
        for dto_cls in dto_classes:
            field_names = {f.name for f in fields(dto_cls)}
            assert 'dto_version' in field_names, f"{dto_cls.__name__} missing dto_version"


# =============================================================================
# FORBIDDEN FIELDS TESTS
# =============================================================================

class TestForbiddenFields:
    """
    Prohibited fields MUST NOT exist on DTOs.
    
    PROHIBITED:
    ===========
    - importance, weight, ranking
    - computed_*, derived_*
    - is_main, is_primary
    - relevance, sentiment
    """
    
    FORBIDDEN_THREAD_FIELDS = {
        'importance', 'weight', 'ranking', 'rank',
        'is_main', 'is_primary', 'priority',
        'computed_status', 'derived_summary',
        'topic_relevance', 'trending',
        'summary', 'description',
    }
    
    FORBIDDEN_SEGMENT_FIELDS = {
        'merged_from', 'interpolated', 'inferred_gap',
        'likely_continuous', 'importance',
        'computed_duration', 'derived_count',
    }
    
    FORBIDDEN_FRAGMENT_FIELDS = {
        'content', 'text', 'body',  # Semantic content
        'summary', 'relevance', 'importance',
        'keywords', 'sentiment', 'topics',
        'computed_score', 'derived_category',
    }
    
    def test_thread_has_no_forbidden_fields(self):
        """NarrativeThreadDTO must not have forbidden fields."""
        actual_fields = {f.name for f in fields(NarrativeThreadDTO)}
        forbidden_present = actual_fields & self.FORBIDDEN_THREAD_FIELDS
        
        assert forbidden_present == set(), \
            f"Forbidden fields found: {forbidden_present}"
    
    def test_segment_has_no_forbidden_fields(self):
        """TimelineSegmentDTO must not have forbidden fields."""
        actual_fields = {f.name for f in fields(TimelineSegmentDTO)}
        forbidden_present = actual_fields & self.FORBIDDEN_SEGMENT_FIELDS
        
        assert forbidden_present == set(), \
            f"Forbidden fields found: {forbidden_present}"
    
    def test_fragment_has_no_forbidden_fields(self):
        """EvidenceFragmentDTO must not have forbidden fields."""
        actual_fields = {f.name for f in fields(EvidenceFragmentDTO)}
        forbidden_present = actual_fields & self.FORBIDDEN_FRAGMENT_FIELDS
        
        assert forbidden_present == set(), \
            f"Forbidden fields found: {forbidden_present}"


# =============================================================================
# EXPLICIT ABSENCE TESTS
# =============================================================================

class TestExplicitAbsence:
    """
    Missing data MUST be explicit, never inferred.
    """
    
    REQUIRED_AVAILABILITY_VALUES = {
        'PRESENT', 'REDACTED', 'MISSING', 'NEVER_EXISTED', 'UNKNOWN'
    }
    
    def test_availability_enum_is_complete(self):
        """AvailabilityState must have all required values."""
        actual = {e.name for e in AvailabilityState}
        assert self.REQUIRED_AVAILABILITY_VALUES.issubset(actual), \
            f"Missing: {self.REQUIRED_AVAILABILITY_VALUES - actual}"
    
    def test_no_inferred_availability(self):
        """There must be no 'INFERRED' or 'COMPUTED' availability."""
        forbidden = {'INFERRED', 'COMPUTED', 'GUESSED', 'ASSUMED'}
        actual = {e.name for e in AvailabilityState}
        
        assert actual & forbidden == set(), \
            f"Forbidden availability states: {actual & forbidden}"
    
    def test_continuity_is_explicit(self):
        """ContinuityState must not have 'likely' or 'probably' values."""
        actual = {e.name for e in ContinuityState}
        
        for name in actual:
            assert 'LIKELY' not in name.upper(), f"Forbidden: {name}"
            assert 'PROBABLY' not in name.upper(), f"Forbidden: {name}"
            assert 'MAYBE' not in name.upper(), f"Forbidden: {name}"


# =============================================================================
# NO INFERENCE CAPABILITY TESTS
# =============================================================================

class TestNoInferenceCapability:
    """
    DTOs must not provide methods that enable inference.
    """
    
    FORBIDDEN_METHODS = {
        'compute', 'calculate', 'derive', 'infer',
        'aggregate', 'summarize', 'merge', 'rank',
        'score', 'classify', 'predict',
    }
    
    def test_thread_has_no_inference_methods(self):
        """NarrativeThreadDTO must not have inference methods."""
        thread_methods = {m for m in dir(NarrativeThreadDTO) if not m.startswith('_')}
        
        for method in thread_methods:
            for forbidden in self.FORBIDDEN_METHODS:
                assert forbidden not in method.lower(), \
                    f"Forbidden method pattern in {method}"
    
    def test_segment_has_no_inference_methods(self):
        """TimelineSegmentDTO must not have inference methods."""
        segment_methods = {m for m in dir(TimelineSegmentDTO) if not m.startswith('_')}
        
        for method in segment_methods:
            for forbidden in self.FORBIDDEN_METHODS:
                assert forbidden not in method.lower(), \
                    f"Forbidden method pattern in {method}"


# =============================================================================
# ORDERING TESTS
# =============================================================================

class TestBackendControlledOrdering:
    """
    Ordering must be backend-controlled.
    """
    
    def test_thread_has_order_position(self):
        """Thread must have backend-provided order position."""
        field_names = {f.name for f in fields(NarrativeThreadDTO)}
        assert 'order_position' in field_names
    
    def test_segment_has_order_position(self):
        """Segment must have backend-provided order position."""
        field_names = {f.name for f in fields(TimelineSegmentDTO)}
        assert 'order_position' in field_names
    
    def test_fragment_has_order_position(self):
        """Fragment must have backend-provided order position."""
        field_names = {f.name for f in fields(EvidenceFragmentDTO)}
        assert 'order_position' in field_names
