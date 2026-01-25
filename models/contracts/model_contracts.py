"""
Model Contracts

Defines immutable data structures for Phase 2 (Core AI Models) outputs.
These contracts represent knowledge graphs, embeddings, and trained models.

NO LEARNING LOGIC HERE - only data definitions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Optional, FrozenSet, Dict
from datetime import datetime
from enum import Enum, auto


# =============================================================================
# ENUMS
# =============================================================================

class EdgeType(Enum):
    """Types of edges in knowledge graph."""
    CO_OCCURRENCE = "co_occurrence"
    TEMPORAL_SEQUENCE = "temporal_sequence"
    CONTRADICTION = "contradiction"
    REFERENCE = "reference"
    DEPENDENCY = "dependency"
    VALIDATION = "validation"


class NodeType(Enum):
    """Types of nodes in knowledge graph."""
    ENTITY = "entity"
    TOPIC = "topic"
    FRAGMENT = "fragment"
    THREAD = "thread"
    SOURCE = "source"


class LearningTaskType(Enum):
    """Types of learning tasks."""
    CONTRADICTION_DETECTION = "contradiction_detection"
    DIVERGENCE_DETECTION = "divergence_detection"
    TEMPORAL_ORDERING = "temporal_ordering"
    SEQUENCE_PREDICTION = "sequence_prediction"
    MULTI_SOURCE_VALIDATION = "multi_source_validation"


class ModelStatus(Enum):
    """Status of a trained model."""
    TRAINING = "training"
    TRAINED = "trained"
    VALIDATED = "validated"
    DEPLOYED = "deployed"
    DEPRECATED = "deprecated"


# =============================================================================
# GRAPH CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class GraphNode:
    """
    Immutable node in the knowledge graph.
    
    Represents an entity, topic, fragment, or other graph element.
    """
    node_id: str
    node_type: NodeType
    label: str
    properties: Tuple[Tuple[str, str], ...]
    embedding_id: Optional[str] = None  # Reference to EmbeddingVector
    created_at: datetime = field(default_factory=datetime.now)


@dataclass(frozen=True)
class GraphEdge:
    """
    Immutable edge in the knowledge graph.
    
    Represents relationships between nodes with temporal properties.
    """
    edge_id: str
    source_node_id: str
    target_node_id: str
    edge_type: EdgeType
    weight: float
    temporal_decay: float  # Decay factor for temporal weighting
    confidence: float
    timestamp: datetime
    properties: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)
    
    def __post_init__(self):
        if not 0.0 <= self.weight:
            raise ValueError("weight must be non-negative")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class TemporalEdgeProperties:
    """Temporal properties for knowledge graph edges."""
    lifecycle_stage: str  # "emerging", "active", "dormant", "terminated"
    decay_rate: float
    last_activation: datetime
    activation_count: int
    state_transition_probability: float


@dataclass(frozen=True)
class KnowledgeGraphSnapshot:
    """
    Immutable snapshot of the knowledge graph at a point in time.
    
    This is a PRIMARY OUTPUT of Phase 2 graph construction.
    """
    snapshot_id: str
    version: str
    nodes: Tuple[GraphNode, ...]
    edges: Tuple[GraphEdge, ...]
    node_count: int
    edge_count: int
    created_at: datetime
    parent_snapshot_id: Optional[str] = None
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


# =============================================================================
# EMBEDDING CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class EmbeddingVector:
    """
    Learned embedding vector for an entity.
    
    Immutable representation learned by embedding models.
    """
    embedding_id: str
    entity_id: str
    entity_type: str
    vector: Tuple[float, ...]
    dimension: int
    model_version: str
    created_at: datetime
    
    def __post_init__(self):
        if len(self.vector) != self.dimension:
            raise ValueError(f"Vector length {len(self.vector)} != dimension {self.dimension}")


@dataclass(frozen=True)
class EmbeddingSpace:
    """Collection of embeddings in a shared space."""
    space_id: str
    embeddings: Tuple[EmbeddingVector, ...]
    dimension: int
    model_version: str
    entity_types: FrozenSet[str]
    created_at: datetime


# =============================================================================
# LEARNING TASK CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class LearningTask:
    """
    Definition of a learning task.
    
    Specifies what to learn without containing learning logic.
    """
    task_id: str
    task_type: LearningTaskType
    input_schema: str  # Reference to expected input contract
    output_schema: str  # Reference to expected output contract
    hyperparameters: Tuple[Tuple[str, str], ...]
    description: str


@dataclass(frozen=True)
class TrainingConfig:
    """Configuration for model training."""
    config_id: str
    task_id: str
    batch_size: int
    learning_rate: float
    epochs: int
    optimizer: str
    loss_function: str
    random_seed: int  # For determinism
    additional_params: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class TrainingRun:
    """Record of a training run."""
    run_id: str
    task_id: str
    config_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    final_loss: Optional[float]
    final_metrics: Tuple[Tuple[str, float], ...]
    status: str  # "running", "completed", "failed"
    error_message: Optional[str] = None


# =============================================================================
# TRAINED MODEL CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class TrainedModelArtifact:
    """
    Immutable artifact representing a trained model.
    
    This is a PRIMARY OUTPUT of Phase 2 learning.
    Contains NO weights directly - only metadata and references.
    """
    model_id: str
    model_version: str
    task_type: LearningTaskType
    weights_hash: str  # Hash of serialized weights
    weights_path: str  # Path to weights file
    training_run_id: str
    input_schema: str
    output_schema: str
    status: ModelStatus
    created_at: datetime
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ModelRegistry:
    """Registry of all trained models."""
    registry_id: str
    models: Tuple[TrainedModelArtifact, ...]
    active_versions: Tuple[Tuple[str, str], ...]  # task_type -> model_id
    updated_at: datetime


# =============================================================================
# MULTI-TASK LEARNING CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class MultiTaskHead:
    """Definition of a head in multi-task learning."""
    head_id: str
    task_type: LearningTaskType
    input_dimension: int
    output_dimension: int
    architecture: str  # "linear", "mlp", etc.


@dataclass(frozen=True)
class MultiTaskModel:
    """Multi-task model with shared backbone and task heads."""
    model_id: str
    backbone_id: str
    heads: Tuple[MultiTaskHead, ...]
    shared_embedding_dim: int
    model_version: str
    created_at: datetime
