"""Completeness metrics computation."""

from __future__ import annotations
from typing import List, Set
from datetime import datetime
import hashlib

from ...contracts.validation_contracts import MetricResult, MetricType, CompletenessScore
from ...contracts.data_contracts import AnnotatedFragment


class CompletenessMetric:
    """Compute narrative completeness metrics."""
    
    def __init__(self, threshold: float = 0.6):
        self._threshold = threshold
        self._version = "1.0.0"
    
    def compute(
        self,
        fragments: List[AnnotatedFragment],
        expected_topics: Set[str] = None,
        model_version: str = "1.0.0",
        data_version: str = "1.0.0"
    ) -> MetricResult:
        """Compute completeness metric."""
        if not fragments:
            score = 0.0
        elif not expected_topics:
            score = 1.0  # No expectations, always complete
        else:
            # Find covered topics
            covered = set()
            for frag in fragments:
                covered.update(frag.preprocessed_fragment.semantic_features.topic_ids)
            
            coverage = len(covered & expected_topics) / len(expected_topics)
            score = coverage
        
        metric_id = hashlib.sha256(
            f"completeness|{len(fragments)}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return MetricResult(
            metric_id=f"metric_{metric_id}",
            metric_type=MetricType.COMPLETENESS,
            metric_name="narrative_completeness",
            value=score,
            threshold=self._threshold,
            is_passing=score >= self._threshold,
            computed_at=datetime.now(),
            model_version=model_version,
            data_version=data_version
        )
