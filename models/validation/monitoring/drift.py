"""Drift detection for models."""

from __future__ import annotations
from typing import List
from datetime import datetime
import hashlib

from ...contracts.validation_contracts import DriftAlert, DriftType, AlertSeverity


class DriftDetector:
    """Detect drift in model behavior."""
    
    def __init__(self, significance_threshold: float = 0.1):
        self._threshold = significance_threshold
        self._baseline_distributions: dict = {}
    
    def set_baseline(self, name: str, values: List[float]):
        """Set baseline distribution for drift detection."""
        self._baseline_distributions[name] = {
            'mean': sum(values) / len(values) if values else 0,
            'std': self._std(values),
            'values': values
        }
    
    def detect(
        self,
        name: str,
        current_values: List[float],
        model_id: str
    ) -> DriftAlert:
        """Detect drift from baseline."""
        baseline = self._baseline_distributions.get(name)
        
        if not baseline or not current_values:
            return None
        
        current_mean = sum(current_values) / len(current_values)
        baseline_mean = baseline['mean']
        baseline_std = baseline['std']
        
        # Simple z-score based drift detection
        if baseline_std > 0:
            z_score = abs(current_mean - baseline_mean) / baseline_std
            magnitude = z_score / 3.0  # Normalize
        else:
            magnitude = abs(current_mean - baseline_mean)
        
        is_drift = magnitude > self._threshold
        
        if not is_drift:
            return None
        
        severity = (
            AlertSeverity.CRITICAL if magnitude > 0.5 else
            AlertSeverity.ERROR if magnitude > 0.3 else
            AlertSeverity.WARNING
        )
        
        alert_id = hashlib.sha256(
            f"drift|{name}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return DriftAlert(
            alert_id=f"alert_{alert_id}",
            drift_type=DriftType.DATA_DRIFT,
            severity=severity,
            model_id=model_id,
            description=f"Drift detected in {name}: magnitude {magnitude:.2f}",
            drift_magnitude=magnitude,
            baseline_reference=f"baseline_{name}",
            detected_at=datetime.now()
        )
    
    def _std(self, values: List[float]) -> float:
        """Compute standard deviation."""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1)
        return variance ** 0.5
