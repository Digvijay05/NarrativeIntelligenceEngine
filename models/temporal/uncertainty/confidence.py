"""Confidence estimation for predictions."""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
from datetime import datetime
import hashlib
import math

from ...contracts.temporal_contracts import (
    UncertaintyEstimate, PredictionResult, PredictionConfidence
)


class ConfidenceEstimator:
    """Estimate confidence intervals for predictions."""
    
    def __init__(self, confidence_level: float = 0.95):
        self._confidence_level = confidence_level
        self._version = "1.0.0"
    
    def estimate(
        self,
        prediction: PredictionResult,
        historical_accuracy: Optional[List[float]] = None
    ) -> UncertaintyEstimate:
        """Estimate uncertainty for a prediction."""
        mean = prediction.confidence
        
        # Compute interval based on historical accuracy
        if historical_accuracy and len(historical_accuracy) > 2:
            std = self._compute_std(historical_accuracy)
            z = 1.96 if self._confidence_level == 0.95 else 1.645
            margin = z * std / (len(historical_accuracy) ** 0.5)
        else:
            # Default margin based on confidence level
            margin = (1.0 - prediction.confidence) * 0.5
        
        lower = max(0.0, mean - margin)
        upper = min(1.0, mean + margin)
        
        est_id = hashlib.sha256(
            f"{prediction.prediction_id}|{mean:.4f}".encode()
        ).hexdigest()[:12]
        
        return UncertaintyEstimate(
            estimate_id=f"unc_{est_id}",
            prediction_id=prediction.prediction_id,
            mean=mean,
            lower_bound=lower,
            upper_bound=upper,
            confidence_level=self._confidence_level,
            distribution_type="normal",
            distribution_params=(("mean", mean), ("std", margin / 1.96)),
            is_calibrated=historical_accuracy is not None
        )
    
    def _compute_std(self, values: List[float]) -> float:
        """Compute standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return variance ** 0.5
