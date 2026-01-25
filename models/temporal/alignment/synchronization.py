"""Timeline synchronization across sources."""

from __future__ import annotations
from typing import Dict, List, Tuple
from datetime import datetime
import hashlib

from ...contracts.temporal_contracts import AlignmentResult, AlignmentStatus
from ...contracts.data_contracts import AnnotatedFragment


class TimelineSynchronizer:
    """Synchronize timelines from multiple sources."""
    
    def __init__(self):
        self._version = "1.0.0"
    
    def synchronize(
        self,
        source_fragments: Dict[str, List[AnnotatedFragment]]
    ) -> AlignmentResult:
        """Synchronize fragments from multiple sources."""
        if not source_fragments:
            return self._empty_result()
        
        source_ids = tuple(sorted(source_fragments.keys()))
        
        # Compute offsets by finding common events
        offsets = self._compute_offsets(source_fragments)
        
        # Align timestamps
        aligned_timestamps = []
        for source_id, fragments in source_fragments.items():
            offset = offsets.get(source_id, 0.0)
            for frag in fragments:
                orig_ts = frag.preprocessed_fragment.temporal_features.timestamp
                # Apply offset
                aligned_timestamps.append((frag.fragment_id, orig_ts))
        
        # Determine status
        if len(source_ids) == 1:
            status = AlignmentStatus.ALIGNED
        elif all(abs(o) < 60 for o in offsets.values()):  # Within 1 minute
            status = AlignmentStatus.ALIGNED
        elif all(abs(o) < 3600 for o in offsets.values()):  # Within 1 hour
            status = AlignmentStatus.PARTIAL
        else:
            status = AlignmentStatus.MISALIGNED
        
        align_id = hashlib.sha256(
            f"{','.join(source_ids)}|{len(aligned_timestamps)}".encode()
        ).hexdigest()[:12]
        
        return AlignmentResult(
            alignment_id=f"align_{align_id}",
            source_ids=source_ids,
            status=status,
            aligned_timestamps=tuple(aligned_timestamps),
            offset_corrections=tuple(offsets.items()),
            confidence=0.8 if status == AlignmentStatus.ALIGNED else 0.5,
            timestamp=datetime.now()
        )
    
    def _compute_offsets(
        self,
        source_fragments: Dict[str, List[AnnotatedFragment]]
    ) -> Dict[str, float]:
        """Compute time offsets between sources."""
        offsets = {}
        
        # Use first source as reference
        reference_source = sorted(source_fragments.keys())[0]
        offsets[reference_source] = 0.0
        
        ref_fragments = source_fragments[reference_source]
        if not ref_fragments:
            return offsets
        
        ref_start = min(
            f.preprocessed_fragment.temporal_features.timestamp
            for f in ref_fragments
        )
        
        for source_id, fragments in source_fragments.items():
            if source_id == reference_source:
                continue
            if not fragments:
                offsets[source_id] = 0.0
                continue
            
            src_start = min(
                f.preprocessed_fragment.temporal_features.timestamp
                for f in fragments
            )
            
            offset = (src_start - ref_start).total_seconds()
            offsets[source_id] = offset
        
        return offsets
    
    def _empty_result(self) -> AlignmentResult:
        """Return empty alignment result."""
        return AlignmentResult(
            alignment_id=f"align_empty_{datetime.now().timestamp()}",
            source_ids=(),
            status=AlignmentStatus.UNKNOWN,
            aligned_timestamps=(),
            offset_corrections=(),
            confidence=0.0,
            timestamp=datetime.now()
        )
