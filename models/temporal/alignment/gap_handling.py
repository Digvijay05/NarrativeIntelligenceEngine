"""Temporal gap handling."""

from __future__ import annotations
from typing import List
from datetime import datetime
import hashlib

from ...contracts.temporal_contracts import TimelineGap, GapFillResult, TemporalState, LifecycleState
from ...contracts.data_contracts import AnnotatedFragment


class GapHandler:
    """Handle gaps in temporal sequences."""
    
    def __init__(self, gap_threshold_seconds: float = 86400):
        self._threshold = gap_threshold_seconds
        self._version = "1.0.0"
    
    def detect_gaps(
        self,
        fragments: List[AnnotatedFragment]
    ) -> List[TimelineGap]:
        """Detect gaps in fragment timeline."""
        if len(fragments) < 2:
            return []
        
        sorted_frags = sorted(
            fragments,
            key=lambda f: f.preprocessed_fragment.temporal_features.timestamp
        )
        
        gaps = []
        for i in range(1, len(sorted_frags)):
            start_ts = sorted_frags[i-1].preprocessed_fragment.temporal_features.timestamp
            end_ts = sorted_frags[i].preprocessed_fragment.temporal_features.timestamp
            
            duration = (end_ts - start_ts).total_seconds()
            
            if duration > self._threshold:
                gap_id = hashlib.sha256(
                    f"{sorted_frags[i-1].fragment_id}|{sorted_frags[i].fragment_id}".encode()
                ).hexdigest()[:12]
                
                gaps.append(TimelineGap(
                    gap_id=f"gap_{gap_id}",
                    timeline_id=sorted_frags[0].fragment_id[:16],
                    start_time=start_ts,
                    end_time=end_ts,
                    duration_seconds=duration,
                    gap_type="missing_data",
                    interpolation_available=duration < self._threshold * 3
                ))
        
        return gaps
    
    def fill_gap(self, gap: TimelineGap) -> GapFillResult:
        """Attempt to fill a gap with inferred states."""
        if not gap.interpolation_available:
            return GapFillResult(
                result_id=f"fill_{gap.gap_id}",
                gap_id=gap.gap_id,
                fill_method="none",
                filled_states=(),
                confidence=0.0,
                timestamp=datetime.now()
            )
        
        # Create interpolated states
        num_states = min(3, int(gap.duration_seconds / self._threshold))
        filled_states = []
        
        for i in range(num_states):
            state_id = hashlib.sha256(
                f"{gap.gap_id}|interp|{i}".encode()
            ).hexdigest()[:12]
            
            filled_states.append(TemporalState(
                state_id=f"state_{state_id}",
                entity_id=gap.timeline_id,
                entity_type="thread",
                lifecycle=LifecycleState.DORMANT,
                timestamp=gap.start_time,  # Would interpolate
                sequence_position=i,
                version=self._version
            ))
        
        return GapFillResult(
            result_id=f"fill_{gap.gap_id}",
            gap_id=gap.gap_id,
            fill_method="interpolation",
            filled_states=tuple(filled_states),
            confidence=0.6,
            timestamp=datetime.now()
        )
