"""
Learning Subpackage

Task-specific learning modules for:
- Contradiction detection
- Divergence patterns
- Temporal ordering
"""

from .contradiction_detector import ContradictionLearner
from .divergence_learner import DivergenceLearner
from .temporal_ordering import TemporalOrderLearner

__all__ = ['ContradictionLearner', 'DivergenceLearner', 'TemporalOrderLearner']
