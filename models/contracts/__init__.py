"""
Contracts Module

Defines explicit data contracts for inter-phase communication.
All phases MUST use these contracts - no direct coupling allowed.

DESIGN PRINCIPLES:
==================
1. All contracts are immutable (frozen dataclasses)
2. Contracts define WHAT, not HOW
3. No phase-specific logic in contracts
4. Version identifiers on all model state
"""

from .data_contracts import (
    RawDataPoint,
    PreprocessedFragment,
    AnnotatedFragment,
    DataLineageRecord,
    FeatureVector,
)

from .model_contracts import (
    GraphNode,
    GraphEdge,
    KnowledgeGraphSnapshot,
    EmbeddingVector,
    TrainedModelArtifact,
    LearningTask,
)

from .temporal_contracts import (
    TemporalState,
    PredictionResult,
    UncertaintyEstimate,
    AlignmentResult,
    ReplayCheckpoint,
)

from .inference_contracts import (
    InferenceRequest,
    InferenceResponse,
    BatchJob,
    CacheEntry,
    ModelVersion,
)

from .validation_contracts import (
    MetricResult,
    ValidationReport,
    DriftAlert,
    ErrorCategory,
)

__all__ = [
    # Data contracts
    'RawDataPoint', 'PreprocessedFragment', 'AnnotatedFragment',
    'DataLineageRecord', 'FeatureVector',
    # Model contracts
    'GraphNode', 'GraphEdge', 'KnowledgeGraphSnapshot',
    'EmbeddingVector', 'TrainedModelArtifact', 'LearningTask',
    # Temporal contracts
    'TemporalState', 'PredictionResult', 'UncertaintyEstimate',
    'AlignmentResult', 'ReplayCheckpoint',
    # Inference contracts
    'InferenceRequest', 'InferenceResponse', 'BatchJob',
    'CacheEntry', 'ModelVersion',
    # Validation contracts
    'MetricResult', 'ValidationReport', 'DriftAlert', 'ErrorCategory',
]
