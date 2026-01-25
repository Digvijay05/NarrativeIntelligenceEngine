"""Coherence metrics computation."""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
import hashlib

from ...contracts.validation_contracts import MetricResult, MetricType, CoherenceScore
from ...contracts.data_contracts import AnnotatedFragment


class CoherenceMetric:
    """Compute temporal coherence metrics."""
    
    def __init__(self, threshold: float = 0.7):
        self._threshold = threshold
        self._version = "1.0.0"
    
    def compute(
        self,
        fragments: List[AnnotatedFragment],
        model_version: str = "1.0.0",
        data_version: str = "1.0.0"
    ) -> MetricResult:
        """Compute coherence metric."""
        if len(fragments) < 2:
            score = 1.0
        else:
            sorted_frags = sorted(
                fragments,
                key=lambda f: f.preprocessed_fragment.temporal_features.timestamp
            )
            
            # Compute gap regularity
            gaps = []
            for i in range(1, len(sorted_frags)):
                gap = (
                    sorted_frags[i].preprocessed_fragment.temporal_features.timestamp -
                    sorted_frags[i-1].preprocessed_fragment.temporal_features.timestamp
                ).total_seconds()
                gaps.append(gap)
            
            if gaps:
                avg = sum(gaps) / len(gaps)
                if avg > 0:
                    variance = sum((g - avg) ** 2 for g in gaps) / len(gaps)
                    cv = (variance ** 0.5) / avg
                    score = max(0.0, 1.0 - cv)
                else:
                    score = 1.0
            else:
                score = 1.0
        
        metric_id = hashlib.sha256(
            f"coherence|{len(fragments)}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return MetricResult(
            metric_id=f"metric_{metric_id}",
            metric_type=MetricType.COHERENCE,
            metric_name="temporal_coherence",
            value=score,
            threshold=self._threshold,
            is_passing=score >= self._threshold,
            computed_at=datetime.now(),
            model_version=model_version,
            data_version=data_version
        )
