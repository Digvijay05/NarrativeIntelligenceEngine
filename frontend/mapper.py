"""
Backend to DTO Mapper

Converts internal backend entities to read-only frontend DTOs.

MAPPING BOUNDARY:
=================
This is the ONLY place where backend entities become DTOs.
All conversion happens here, nowhere else.

MAPPING RULES:
==============
1. Never expose internal entity structure
2. Always include explicit availability
3. Fill UNKNOWN, never infer
4. Preserve backend ordering
"""

from __future__ import annotations
from typing import List, Tuple, Optional
from datetime import datetime
import uuid

from frontend.dtos import (
    DTOVersion, AvailabilityState, ContinuityState, LifecycleState,
    SilenceType, DivergenceFlag, OrderingBasis,
    NarrativeThreadDTO, TimelineSegmentDTO, EvidenceFragmentDTO,
    ModelOverlayRefDTO,
)
from frontend.dtos.thread import (
    TemporalBoundsDTO, PresenceMarkerDTO, OverlayRefDTO
)
from frontend.dtos.segment import TimeWindowDTO, SilenceIndicatorDTO
from frontend.dtos.fragment import TimestampDTO
from frontend.dtos.overlay import ScoreRefDTO, AnnotationRefDTO
from frontend.dtos.envelope import (
    QueryMetadataDTO, ThreadListEnvelope, SegmentListEnvelope,
    FragmentListEnvelope, PaginationDTO
)


class DTOMapper:
    """
    Maps backend entities to frontend DTOs.
    
    SINGLE POINT OF CONVERSION:
    ===========================
    All backend → frontend conversion goes through this class.
    """
    
    # =========================================================================
    # THREAD MAPPING
    # =========================================================================
    
    def map_thread(
        self,
        thread_id: str,
        thread_version: str,
        lifecycle: str,
        start_timestamp: Optional[datetime],
        end_timestamp: Optional[datetime],
        topic_ids: List[str],
        segment_ids: List[str],
        display_label: Optional[str] = None,
        order_position: int = 0,
        first_seen_at: Optional[datetime] = None,
        last_updated_at: Optional[datetime] = None,
    ) -> NarrativeThreadDTO:
        """Map a thread to DTO."""
        
        # Map lifecycle (never infer)
        lifecycle_state = self._map_lifecycle(lifecycle)
        
        # Create temporal bounds (explicit unknowns)
        temporal_bounds = TemporalBoundsDTO(
            start_timestamp=start_timestamp,
            start_known=start_timestamp is not None,
            end_timestamp=end_timestamp,
            end_known=end_timestamp is not None,
            is_unbounded=start_timestamp is None and end_timestamp is None
        )
        
        now = datetime.utcnow()
        
        return NarrativeThreadDTO(
            dto_version=DTOVersion.current(),
            thread_id=thread_id,
            thread_version=thread_version,
            lifecycle_state=lifecycle_state,
            temporal_bounds=temporal_bounds,
            presence_markers=(),  # Empty unless explicitly provided
            divergence_flags=(),  # Empty unless model provides
            overlay_refs=(),  # Empty unless model provides
            topic_ids=tuple(topic_ids),
            segment_ids=tuple(segment_ids),
            display_label=display_label,
            ordering_basis=OrderingBasis.BACKEND_RANKED,
            order_position=order_position,
            availability=AvailabilityState.PRESENT,
            first_seen_at=first_seen_at or now,
            last_updated_at=last_updated_at or now,
        )
    
    # =========================================================================
    # SEGMENT MAPPING
    # =========================================================================
    
    def map_segment(
        self,
        segment_id: str,
        thread_id: str,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        fragment_ids: List[str],
        order_position: int = 0,
    ) -> TimelineSegmentDTO:
        """Map a segment to DTO."""
        
        time_window = TimeWindowDTO(
            start=start_time,
            start_inclusive=True,
            end=end_time,
            end_inclusive=True,
            is_point_in_time=start_time == end_time,
            is_unbounded_start=start_time is None,
            is_unbounded_end=end_time is None,
        )
        
        return TimelineSegmentDTO(
            dto_version=DTOVersion.current(),
            segment_id=segment_id,
            thread_id=thread_id,
            time_window=time_window,
            continuity_to_previous=ContinuityState.UNKNOWN_GAP,  # Explicit unknown
            continuity_to_next=ContinuityState.UNKNOWN_GAP,  # Explicit unknown
            silence_indicators=(),
            fragment_ids=tuple(fragment_ids),
            ordering_basis=OrderingBasis.CHRONOLOGICAL,
            order_position=order_position,
            availability=AvailabilityState.PRESENT,
            fragment_count=len(fragment_ids),
            created_at=datetime.utcnow(),
        )
    
    # =========================================================================
    # FRAGMENT MAPPING
    # =========================================================================
    
    def map_fragment(
        self,
        fragment_id: str,
        source_id: str,
        published_at: Optional[datetime],
        fetched_at: datetime,
        payload_hash: str,
        byte_size: Optional[int] = None,
        word_count: Optional[int] = None,
        segment_id: Optional[str] = None,
        thread_id: Optional[str] = None,
        order_position: int = 0,
    ) -> EvidenceFragmentDTO:
        """Map a fragment to DTO."""
        
        published_ts = None
        if published_at:
            published_ts = TimestampDTO(
                timestamp=published_at,
                precision="second",
                is_approximate=False,
                source="published"
            )
        
        fetched_ts = TimestampDTO(
            timestamp=fetched_at,
            precision="second",
            is_approximate=False,
            source="fetched"
        )
        
        return EvidenceFragmentDTO(
            dto_version=DTOVersion.current(),
            fragment_id=fragment_id,
            source_id=source_id,
            published_at=published_ts,
            fetched_at=fetched_ts,
            payload_hash=payload_hash,
            availability=AvailabilityState.PRESENT,
            byte_size=byte_size,
            word_count=word_count,
            display_label=None,
            segment_id=segment_id,
            thread_id=thread_id,
            order_position=order_position,
        )
    
    # =========================================================================
    # OVERLAY MAPPING
    # =========================================================================
    
    def map_overlay_ref(
        self,
        overlay_id: str,
        entity_id: str,
        entity_type: str,
        entity_version: str,
        model_id: str,
        model_version: str,
        scores: List[dict],
        annotations: List[dict],
        created_at: datetime,
    ) -> ModelOverlayRefDTO:
        """Map an overlay to reference DTO."""
        
        score_refs = tuple(
            ScoreRefDTO(
                score_type=s['score_type'],
                value=s['value'],
                lower_bound=s.get('lower', s['value'] - 0.1),
                upper_bound=s.get('upper', s['value'] + 0.1),
                confidence_level=s.get('confidence', 0.95),
                display_category=self._categorize_score(s['value']),
                display_label=s.get('label')
            )
            for s in scores
        )
        
        annotation_refs = tuple(
            AnnotationRefDTO(
                annotation_type=a['type'],
                value=a['value'],
                confidence=a.get('confidence', 1.0),
                display_label=a.get('label')
            )
            for a in annotations
        )
        
        return ModelOverlayRefDTO(
            dto_version=DTOVersion.current(),
            overlay_id=overlay_id,
            entity_id=entity_id,
            entity_type=entity_type,
            entity_version=entity_version,
            model_version=model_version,
            model_id=model_id,
            scores=score_refs,
            annotations=annotation_refs,
            created_at=created_at,
            availability=AvailabilityState.PRESENT,
            display_label=None,
        )
    
    # =========================================================================
    # ENVELOPE MAPPING
    # =========================================================================
    
    def create_thread_list_envelope(
        self,
        threads: List[NarrativeThreadDTO],
        query_id: str,
        requested_at: datetime,
        total_count: Optional[int] = None,
    ) -> ThreadListEnvelope:
        """Create envelope for thread list."""
        now = datetime.utcnow()
        
        query = QueryMetadataDTO(
            query_id=query_id,
            requested_at=requested_at,
            responded_at=now,
            processing_time_ms=(now - requested_at).total_seconds() * 1000,
            requested_version=DTOVersion.current(),
            actual_version=DTOVersion.current(),
        )
        
        pagination = PaginationDTO(
            total_count=total_count,
            returned_count=len(threads),
            offset=0,
            has_more=False,
            next_cursor=None,
            prev_cursor=None,
        )
        
        return ThreadListEnvelope(
            dto_version=DTOVersion.current(),
            response_id=str(uuid.uuid4()),
            query=query,
            threads=tuple(threads),
            ordering_basis=OrderingBasis.BACKEND_RANKED,
            pagination=pagination,
            data_availability=AvailabilityState.PRESENT,
            data_as_of=now,
            is_stale=False,
            warnings=(),
        )
    
    # =========================================================================
    # HELPERS
    # =========================================================================
    
    def _map_lifecycle(self, lifecycle: str) -> LifecycleState:
        """Map lifecycle string to enum."""
        mapping = {
            'emerging': LifecycleState.EMERGING,
            'active': LifecycleState.ACTIVE,
            'dormant': LifecycleState.DORMANT,
            'concluded': LifecycleState.CONCLUDED,
            'merged': LifecycleState.MERGED,
        }
        return mapping.get(lifecycle.lower(), LifecycleState.UNKNOWN)
    
    def _categorize_score(self, value: float) -> str:
        """
        Categorize score for display.
        
        NOTE: This is the ONLY place where thresholds are applied.
        Frontend cannot recategorize.
        """
        if value < 0.3:
            return "low"
        elif value < 0.7:
            return "medium"
        else:
            return "high"
