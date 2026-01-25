"""Model degradation monitoring."""

from __future__ import annotations
from typing import Dict, List
from datetime import datetime
import hashlib

from ...contracts.validation_contracts import DegradationMetric, MetricResult


class DegradationMonitor:
    """Monitor model degradation over time."""
    
    def __init__(self, degradation_threshold: float = 0.1):
        self._threshold = degradation_threshold
        self._baselines: Dict[str, float] = {}
        self._history: Dict[str, List[float]] = {}
    
    def set_baseline(self, metric_name: str, value: float):
        """Set baseline value for a metric."""
        self._baselines[metric_name] = value
    
    def record(self, metric: MetricResult):
        """Record a metric observation."""
        key = f"{metric.metric_name}"
        if key not in self._history:
            self._history[key] = []
        self._history[key].append(metric.value)
    
    def check_degradation(self, metric_name: str) -> DegradationMetric:
        """Check for degradation in a metric."""
        baseline = self._baselines.get(metric_name, 1.0)
        history = self._history.get(metric_name, [])
        
        current = history[-1] if history else baseline
        change_percent = ((current - baseline) / baseline * 100) if baseline else 0
        
        is_degraded = change_percent < -self._threshold * 100
        
        metric_id = hashlib.sha256(
            f"degrad|{metric_name}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return DegradationMetric(
            metric_id=f"deg_{metric_id}",
            model_id="current",
            metric_name=metric_name,
            baseline_value=baseline,
            current_value=current,
            change_percent=change_percent,
            is_degraded=is_degraded,
            first_observed=datetime.now(),
            last_observed=datetime.now()
        )
