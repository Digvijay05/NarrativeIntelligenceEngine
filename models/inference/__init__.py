"""
Inference & Serving Package (Phase 5)

RESPONSIBILITY: Production serving, optimization

WHAT THIS PHASE MUST NOT DO:
============================
- Train or update models
- Compute validation metrics
- Access raw preprocessing logic

BOUNDARY ENFORCEMENT:
=====================
- Version-aware inference only
- Strict separation of real-time vs batch
- Read-only model access
"""

from .serving import RealtimeInference, BatchProcessor, VersionedModelServer
from .optimization import QueryCache, ModelDistiller, TemporalIndexer

__all__ = [
    'RealtimeInference', 'BatchProcessor', 'VersionedModelServer',
    'QueryCache', 'ModelDistiller', 'TemporalIndexer',
]
