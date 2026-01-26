"""
Divergence Markers

Mark narrative divergence points in fragments.

BOUNDARY ENFORCEMENT:
- Marks divergence, does NOT predict or infer
- Deterministic analysis
- NO learning
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from datetime import datetime
import hashlib

from ...contracts.data_contracts import (
    PreprocessedFragment, Annotation, AnnotationType
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class DivergenceConfig:
    """Configuration for divergence detection."""
    min_fragments_for_divergence: int = 3
    topic_divergence_threshold: float = 0.5
    temporal_gap_threshold_seconds: int = 86400  # 24 hours
    marker_version: str = "1.0.0"


# =============================================================================
# DIVERGENCE MARKERS
# =============================================================================

@dataclass
class DivergencePoint:
    """A detected divergence point in the narrative."""
    divergence_id: str
    timestamp: datetime
    topic_id: str
    fragment_ids: Tuple[str, ...]
    divergence_type: str  # "topic_split", "temporal_gap", "contradiction_branch"
    confidence: float


class DivergenceMarker:
    """
    Mark divergence points in narrative data.
    
    Divergence is when a narrative splits into multiple
    incompatible paths.
    
    BOUNDARY ENFORCEMENT:
    - Analysis only, no inference
    - Marks divergence, does not predict outcomes
    - Deterministic
    """
    
    def __init__(self, config: Optional[DivergenceConfig] = None):
        self._config = config or DivergenceConfig()
    
    def detect_divergence(
        self,
        fragments: List[PreprocessedFragment],
        contradiction_map: Optional[Dict[str, List[str]]] = None
    ) -> List[DivergencePoint]:
        """
        Detect divergence points in fragment sequence.
        
        Returns list of DivergencePoint markers.
        """
        divergence_points = []
        
        # Detect topic-based divergence
        topic_divergences = self._detect_topic_divergence(fragments)
        divergence_points.extend(topic_divergences)
        
        # Detect temporal gap divergence
        temporal_divergences = self._detect_temporal_gaps(fragments)
        divergence_points.extend(temporal_divergences)
        
        # Detect contradiction-based divergence
        if contradiction_map:
            contra_divergences = self._detect_contradiction_divergence(
                fragments, contradiction_map
            )
            divergence_points.extend(contra_divergences)
        
        return divergence_points
    
    def _detect_topic_divergence(
        self,
        fragments: List[PreprocessedFragment]
    ) -> List[DivergencePoint]:
        """Detect when topics split into divergent branches."""
        divergences = []
        
        # Group fragments by time windows
        if len(fragments) < self._config.min_fragments_for_divergence:
            return divergences
        
        # Sort by timestamp
        sorted_frags = sorted(fragments, key=lambda f: f.temporal_features.timestamp)
        
        # Track topic evolution
        topic_history: Dict[str, List[str]] = {}  # topic -> fragment_ids
        
        for frag in sorted_frags:
            for topic_id in frag.semantic_features.topic_ids:
                if topic_id not in topic_history:
                    topic_history[topic_id] = []
                topic_history[topic_id].append(frag.fragment_id)
        
        # Check for topic splits (simplified)
        for topic_id, frag_ids in topic_history.items():
            if len(frag_ids) >= self._config.min_fragments_for_divergence:
                # Could analyze for divergence patterns here
                pass
        
        return divergences
    
    def _detect_temporal_gaps(
        self,
        fragments: List[PreprocessedFragment]
    ) -> List[DivergencePoint]:
        """Detect significant temporal gaps that might indicate divergence."""
        divergences = []
        
        if len(fragments) < 2:
            return divergences
        
        sorted_frags = sorted(fragments, key=lambda f: f.temporal_features.timestamp)
        
        for i in range(1, len(sorted_frags)):
            gap = (
                sorted_frags[i].temporal_features.timestamp -
                sorted_frags[i-1].temporal_features.timestamp
            ).total_seconds()
            
            if gap > self._config.temporal_gap_threshold_seconds:
                divergence_id = hashlib.sha256(
                    f"gap_{sorted_frags[i-1].fragment_id}_{sorted_frags[i].fragment_id}".encode()
                ).hexdigest()[:12]
                
                divergences.append(DivergencePoint(
                    divergence_id=f"div_{divergence_id}",
                    timestamp=sorted_frags[i-1].temporal_features.timestamp,
                    topic_id="temporal_gap",
                    fragment_ids=(
                        sorted_frags[i-1].fragment_id,
                        sorted_frags[i].fragment_id
                    ),
                    divergence_type="temporal_gap",
                    confidence=min(1.0, gap / (self._config.temporal_gap_threshold_seconds * 3))
                ))
        
        return divergences
    
    def _detect_contradiction_divergence(
        self,
        fragments: List[PreprocessedFragment],
        contradiction_map: Dict[str, List[str]]
    ) -> List[DivergencePoint]:
        """Detect divergence caused by accumulating contradictions."""
        divergences = []
        
        # Count contradictions per topic
        topic_contradictions: Dict[str, int] = {}
        frag_map = {f.fragment_id: f for f in fragments}
        
        for frag_id, contra_ids in contradiction_map.items():
            if frag_id in frag_map:
                frag = frag_map[frag_id]
                for topic_id in frag.semantic_features.topic_ids:
                    topic_contradictions[topic_id] = \
                        topic_contradictions.get(topic_id, 0) + len(contra_ids)
        
        # Mark divergence for topics with high contradiction count
        for topic_id, count in topic_contradictions.items():
            if count >= self._config.min_fragments_for_divergence:
                divergence_id = hashlib.sha256(
                    f"contra_div_{topic_id}_{count}".encode()
                ).hexdigest()[:12]
                
                divergences.append(DivergencePoint(
                    divergence_id=f"div_{divergence_id}",
                    timestamp=datetime.now(),
                    topic_id=topic_id,
                    fragment_ids=tuple(
                        fid for fid, f in frag_map.items()
                        if topic_id in f.semantic_features.topic_ids
                    )[:5],  # Limit to first 5
                    divergence_type="contradiction_branch",
                    confidence=min(1.0, count / 10.0)
                ))
        
        return divergences
    
    def create_annotations(
        self,
        divergence_points: List[DivergencePoint]
    ) -> Dict[str, List[Annotation]]:
        """
        Create annotations from divergence points.
        
        Returns mapping: fragment_id -> list of annotations
        """
        annotations: Dict[str, List[Annotation]] = {}
        now = datetime.now()
        
        for point in divergence_points:
            annotation = Annotation(
                annotation_id=f"ann_{point.divergence_id}",
                annotation_type=AnnotationType.DIVERGENCE,
                confidence=point.confidence,
                evidence=point.fragment_ids,
                annotated_at=now,
                annotator_version=self._config.marker_version
            )
            
            for frag_id in point.fragment_ids:
                if frag_id not in annotations:
                    annotations[frag_id] = []
                annotations[frag_id].append(annotation)
        
        return annotations
