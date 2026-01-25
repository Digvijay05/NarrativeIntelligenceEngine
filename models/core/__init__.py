"""
Core AI Models Package (Phase 2)

RESPONSIBILITY: Knowledge graph construction, embeddings, learning

WHAT THIS PHASE MUST NOT DO:
============================
- Perform temporal prediction (Phase 3)
- Run inference on live data (Phase 5)
- Implement validation metrics (Phase 4)
- Access raw preprocessing logic (Phase 1)

BOUNDARY ENFORCEMENT:
=====================
- Consumes AnnotatedFragment from data phase
- Produces trained models via contracts
- No imports from temporal/, validation/, inference/
"""

from .graph import KnowledgeGraphBuilder, TemporalEdgeManager
from .embeddings import GraphEmbedder, SequenceEmbedder
from .learning import (
    ContradictionLearner,
    DivergenceLearner,
    TemporalOrderLearner,
)

__all__ = [
    'KnowledgeGraphBuilder', 'TemporalEdgeManager',
    'GraphEmbedder', 'SequenceEmbedder',
    'ContradictionLearner', 'DivergenceLearner', 'TemporalOrderLearner',
]
