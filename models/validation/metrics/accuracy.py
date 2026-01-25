"""Accuracy metrics computation."""

from __future__ import annotations
from typing import List, Tuple
from datetime import datetime
import hashlib

from ...contracts.validation_contracts import MetricResult, MetricType, AccuracyScore


class AccuracyMetric:
    """Compute prediction accuracy metrics."""
    
    def __init__(self, threshold: float = 0.7):
        self._threshold = threshold
        self._version = "1.0.0"
    
    def compute(
        self,
        predictions: List[Tuple[float, float]],  # (predicted, actual)
        model_id: str,
        task_type: str = "classification"
    ) -> AccuracyScore:
        """Compute accuracy metrics from predictions."""
        if not predictions:
            return self._empty_score(model_id)
        
        tp = fp = tn = fn = 0
        
        for pred, actual in predictions:
            pred_binary = 1 if pred >= 0.5 else 0
            actual_binary = 1 if actual >= 0.5 else 0
            
            if pred_binary == 1 and actual_binary == 1:
                tp += 1
            elif pred_binary == 1 and actual_binary == 0:
                fp += 1
            elif pred_binary == 0 and actual_binary == 0:
                tn += 1
            else:
                fn += 1
        
        accuracy = (tp + tn) / len(predictions) if predictions else 0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        score_id = hashlib.sha256(
            f"accuracy|{model_id}|{len(predictions)}".encode()
        ).hexdigest()[:12]
        
        return AccuracyScore(
            score_id=f"acc_{score_id}",
            model_id=model_id,
            task_type=task_type,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1,
            sample_size=len(predictions),
            computed_at=datetime.now()
        )
    
    def _empty_score(self, model_id: str) -> AccuracyScore:
        """Return empty accuracy score."""
        return AccuracyScore(
            score_id=f"acc_empty_{datetime.now().timestamp()}",
            model_id=model_id,
            task_type="unknown",
            accuracy=0.0,
            precision=0.0,
            recall=0.0,
            f1_score=0.0,
            sample_size=0,
            computed_at=datetime.now()
        )
