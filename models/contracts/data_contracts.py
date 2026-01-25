"""
Data Contracts

Defines immutable data structures for Phase 1 (Data Foundation) outputs.
These contracts are consumed by all downstream phases.

NO PHASE-SPECIFIC LOGIC HERE - only data definitions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Optional, FrozenSet
from datetime import datetime
from enum import Enum, auto


# =============================================================================
# ENUMS
# =============================================================================

class AnnotationType(Enum):
    """Types of annotations applied during preprocessing."""
    CONTRADICTION = "contradiction"
    PRESENCE = "presence"
    ABSENCE = "absence"
    DIVERGENCE = "divergence"
    CONTINUATION = "continuation"


class DataQuality(Enum):
    """Quality assessment of data point."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


# =============================================================================
# RAW DATA CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class RawDataPoint:
    """
    Raw data point before any preprocessing.
    
    This is the input to Phase 1 - represents data as received
    from the backend ingestion layer.
    """
    data_id: str
    source_id: str
    timestamp: datetime
    payload: str
    source_type: str
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


# =============================================================================
# FEATURE CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class FeatureVector:
    """
    Immutable feature vector for ML processing.
    
    Used for all vectorized representations in the system.
    Dimension and values are fixed after creation.
    """
    vector_id: str
    values: Tuple[float, ...]
    dimension: int
    feature_type: str  # "semantic", "temporal", "combined"
    source_id: str
    created_at: datetime
    
    def __post_init__(self):
        if len(self.values) != self.dimension:
            raise ValueError(f"Vector values length {len(self.values)} != dimension {self.dimension}")


@dataclass(frozen=True)
class TemporalFeatures:
    """Temporal features extracted from a data point."""
    timestamp: datetime
    time_since_last: Optional[float]  # seconds
    time_window_position: float  # 0.0 to 1.0 within window
    day_of_week: int
    hour_of_day: int
    is_weekend: bool


@dataclass(frozen=True)
class SemanticFeatures:
    """Semantic features extracted from content."""
    embedding: FeatureVector
    topic_ids: Tuple[str, ...]
    entity_ids: Tuple[str, ...]
    language: str
    content_hash: str


# =============================================================================
# PREPROCESSED DATA CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class PreprocessedFragment:
    """
    Output from preprocessing pipeline.
    
    Contains extracted features but NO annotations yet.
    This is the intermediate step before annotation.
    """
    fragment_id: str
    source_data_id: str  # Reference to RawDataPoint
    temporal_features: TemporalFeatures
    semantic_features: SemanticFeatures
    quality: DataQuality
    preprocessing_version: str
    preprocessed_at: datetime


# =============================================================================
# ANNOTATION CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class Annotation:
    """Single annotation applied to a fragment."""
    annotation_id: str
    annotation_type: AnnotationType
    confidence: float  # 0.0 to 1.0
    evidence: Tuple[str, ...]  # IDs of supporting evidence
    annotated_at: datetime
    annotator_version: str
    
    def __post_init__(self):
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class AnnotatedFragment:
    """
    Fully annotated fragment ready for model consumption.
    
    This is the PRIMARY OUTPUT of Phase 1.
    All downstream phases consume this contract.
    """
    fragment_id: str
    preprocessed_fragment: PreprocessedFragment
    annotations: Tuple[Annotation, ...]
    is_duplicate: bool
    duplicate_of: Optional[str]  # fragment_id if duplicate
    contradiction_targets: Tuple[str, ...]  # fragment_ids this contradicts
    lineage_version: str
    finalized_at: datetime


# =============================================================================
# LINEAGE CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class DataLineageRecord:
    """
    Tracks the transformation history of data.
    
    Enables replay and audit of data preprocessing.
    """
    record_id: str
    entity_id: str  # ID of the data entity
    entity_type: str  # "fragment", "annotation", etc.
    operation: str  # "preprocess", "annotate", "merge", etc.
    input_versions: Tuple[str, ...]
    output_version: str
    timestamp: datetime
    operator_version: str
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class DataVersion:
    """Version information for data entities."""
    version_id: str
    entity_id: str
    sequence_number: int
    parent_version: Optional[str]
    created_at: datetime
    content_hash: str


# =============================================================================
# BATCH CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class PreprocessingBatch:
    """Batch of preprocessed fragments."""
    batch_id: str
    fragments: Tuple[PreprocessedFragment, ...]
    source_ids: FrozenSet[str]
    created_at: datetime
    batch_version: str


@dataclass(frozen=True)
class AnnotationBatch:
    """Batch of annotated fragments."""
    batch_id: str
    fragments: Tuple[AnnotatedFragment, ...]
    annotation_stats: Tuple[Tuple[str, int], ...]  # annotation_type -> count
    created_at: datetime
    batch_version: str
