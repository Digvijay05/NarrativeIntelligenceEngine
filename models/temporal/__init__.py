"""
Temporal Inference Package (Phase 3)

RESPONSIBILITY: State prediction, uncertainty modeling, temporal alignment

WHAT THIS PHASE MUST NOT DO:
============================
- Train models (that's Phase 2)
- Compute validation metrics (that's Phase 4)
- Handle serving concerns (that's Phase 5)

BOUNDARY ENFORCEMENT:
=====================
- Consumes trained models from Phase 2
- Produces predictions via contracts
- All functions MUST be replay-safe and deterministic
- No side effects on model state
"""

from .prediction import (
    LifecyclePredictor,
    ContinuationPredictor,
    DivergenceRiskPredictor,
)
from .uncertainty import (
    ConfidenceEstimator,
    CoherenceScorer,
    CredibilityAssessor,
)
from .alignment import (
    TimelineSynchronizer,
    GapHandler,
    StateReplayer,
)

__all__ = [
    'LifecyclePredictor', 'ContinuationPredictor', 'DivergenceRiskPredictor',
    'ConfidenceEstimator', 'CoherenceScorer', 'CredibilityAssessor',
    'TimelineSynchronizer', 'GapHandler', 'StateReplayer',
]
