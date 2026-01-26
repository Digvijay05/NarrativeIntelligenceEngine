"""
Data Foundation Package (Phase 1)

RESPONSIBILITY: Preprocessing, annotation, and versioned data lineage

WHAT THIS PHASE MUST NOT DO:
============================
- Train any models
- Make inference decisions
- Access temporal prediction logic
- Perform validation metrics

BOUNDARY ENFORCEMENT:
=====================
- Consumes raw data from backend ingestion
- Produces AnnotatedFragment via contracts
- No imports from core/, temporal/, validation/, inference/
"""

from .preprocessing import (
    AlignmentEngine,
    FeatureExtractor,
    Vectorizer,
)
from .annotation import (
    AnnotationEngine,
    ContradictionTagger,
    DivergenceMarker,
)
from .lineage import (
    LineageTracker,
    VersionManager,
)

__all__ = [
    'AlignmentEngine', 'FeatureExtractor', 'Vectorizer',
    'AnnotationEngine', 'ContradictionTagger', 'DivergenceMarker',
    'LineageTracker', 'VersionManager',
]
