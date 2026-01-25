"""
Continuation Predictor

Predict expected narrative continuation.

BOUNDARY ENFORCEMENT:
- Deterministic prediction
- NO model training
- Replay-safe
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
import hashlib

from ...contracts.temporal_contracts import ContinuationPrediction
from ...contracts.data_contracts import AnnotatedFragment


@dataclass
class ContinuationConfig:
    """Configuration for continuation prediction."""
    min_pattern_length: int = 2
    max_topics_predicted: int = 5
    max_entities_predicted: int = 5


class ContinuationPredictor:
    """
    Predict expected narrative continuation.
    
    Based on pattern analysis of historical sequences.
    
    BOUNDARY ENFORCEMENT:
    - Deterministic pattern matching
    - NO model training
    - Replay-safe
    """
    
    def __init__(self, config: Optional[ContinuationConfig] = None):
        self._config = config or ContinuationConfig()
        self._version = "1.0.0"
    
    def predict(
        self,
        fragments: List[AnnotatedFragment]
    ) -> ContinuationPrediction:
        """
        Predict continuation based on fragment history.
        
        Deterministic: same fragments = same prediction.
        """
        if not fragments:
            return self._empty_prediction()
        
        # Sort by timestamp
        sorted_frags = sorted(
            fragments,
            key=lambda f: f.preprocessed_fragment.temporal_features.timestamp
        )
        
        # Analyze topic patterns
        expected_topics = self._predict_topics(sorted_frags)
        
        # Analyze entity patterns
        expected_entities = self._predict_entities(sorted_frags)
        
        # Estimate timeframe
        timeframe = self._estimate_timeframe(sorted_frags)
        
        # Compute probability
        probability = self._compute_probability(sorted_frags)
        
        pred_id = hashlib.sha256(
            f"{sorted_frags[-1].fragment_id}|{','.join(expected_topics)}".encode()
        ).hexdigest()[:12]
        
        return ContinuationPrediction(
            prediction_id=f"cont_{pred_id}",
            thread_id=sorted_frags[0].fragment_id[:16],
            expected_topic_ids=expected_topics,
            expected_entity_ids=expected_entities,
            expected_timeframe=timeframe,
            probability=probability,
            model_version=self._version,
            timestamp=datetime.now()
        )
    
    def _predict_topics(
        self,
        fragments: List[AnnotatedFragment]
    ) -> Tuple[str, ...]:
        """Predict likely continuation topics."""
        # Count topic frequencies in recent fragments
        topic_counts: Dict[str, int] = {}
        
        # Weight recent fragments more
        for i, frag in enumerate(fragments):
            weight = (i + 1)  # Later fragments get higher weight
            for topic in frag.preprocessed_fragment.semantic_features.topic_ids:
                topic_counts[topic] = topic_counts.get(topic, 0) + weight
        
        # Sort by count descending
        sorted_topics = sorted(
            topic_counts.items(),
            key=lambda x: (-x[1], x[0])  # Sort by count desc, then alphabetically
        )
        
        return tuple(
            t[0] for t in sorted_topics[:self._config.max_topics_predicted]
        )
    
    def _predict_entities(
        self,
        fragments: List[AnnotatedFragment]
    ) -> Tuple[str, ...]:
        """Predict likely continuation entities."""
        entity_counts: Dict[str, int] = {}
        
        for i, frag in enumerate(fragments):
            weight = (i + 1)
            for entity in frag.preprocessed_fragment.semantic_features.entity_ids:
                entity_counts[entity] = entity_counts.get(entity, 0) + weight
        
        sorted_entities = sorted(
            entity_counts.items(),
            key=lambda x: (-x[1], x[0])
        )
        
        return tuple(
            e[0] for e in sorted_entities[:self._config.max_entities_predicted]
        )
    
    def _estimate_timeframe(
        self,
        fragments: List[AnnotatedFragment]
    ) -> Tuple[float, float]:
        """Estimate time window for next activity."""
        if len(fragments) < 2:
            return (0.0, 86400.0)  # 0 to 24 hours default
        
        # Compute inter-arrival times
        timestamps = [
            f.preprocessed_fragment.temporal_features.timestamp
            for f in fragments
        ]
        
        gaps = []
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i-1]).total_seconds()
            gaps.append(gap)
        
        if not gaps:
            return (0.0, 86400.0)
        
        avg_gap = sum(gaps) / len(gaps)
        min_gap = min(gaps)
        max_gap = max(gaps)
        
        # Predict range based on historical pattern
        lower = max(0, min_gap * 0.5)
        upper = max_gap * 1.5
        
        return (lower, upper)
    
    def _compute_probability(
        self,
        fragments: List[AnnotatedFragment]
    ) -> float:
        """Compute prediction probability."""
        # Higher confidence with more data
        n = len(fragments)
        if n < 3:
            return 0.3
        elif n < 10:
            return 0.5
        else:
            return min(0.8, 0.5 + n * 0.02)
    
    def _empty_prediction(self) -> ContinuationPrediction:
        """Create empty prediction."""
        return ContinuationPrediction(
            prediction_id=f"cont_empty_{datetime.now().timestamp()}",
            thread_id="unknown",
            expected_topic_ids=(),
            expected_entity_ids=(),
            expected_timeframe=(0.0, 86400.0),
            probability=0.0,
            model_version=self._version,
            timestamp=datetime.now()
        )
