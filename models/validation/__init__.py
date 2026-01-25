"""
Validation Package (Phase 4)

RESPONSIBILITY: Metrics, monitoring, error analysis

WHAT THIS PHASE MUST NOT DO:
============================
- Modify any model weights
- Execute inference logic
- Handle data preprocessing

BOUNDARY ENFORCEMENT:
=====================
- Read-only access to model outputs
- Pure functions for metric computation
- Zero model mutation
"""

from .metrics import CoherenceMetric, CompletenessMetric, AccuracyMetric
from .monitoring import DegradationMonitor, DriftDetector, AlertManager
from .errors import ErrorCategorizer, RootCauseAnalyzer

__all__ = [
    'CoherenceMetric', 'CompletenessMetric', 'AccuracyMetric',
    'DegradationMonitor', 'DriftDetector', 'AlertManager',
    'ErrorCategorizer', 'RootCauseAnalyzer',
]
