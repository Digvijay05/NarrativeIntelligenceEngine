"""
Inference Contracts

Defines immutable data structures for Phase 5 (Inference & Serving).
All serving requests, responses, and optimization use these contracts.

NO INFERENCE LOGIC HERE - only data definitions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Optional, Any
from datetime import datetime
from enum import Enum, auto


# =============================================================================
# ENUMS
# =============================================================================

class InferenceMode(Enum):
    """Mode of inference execution."""
    REALTIME = "realtime"
    BATCH = "batch"
    STREAMING = "streaming"


class CacheStrategy(Enum):
    """Caching strategy for inference results."""
    NO_CACHE = "no_cache"
    WRITE_THROUGH = "write_through"
    WRITE_BACK = "write_back"
    READ_ONLY = "read_only"


class JobStatus(Enum):
    """Status of a batch job."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


# =============================================================================
# MODEL VERSION CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class ModelVersion:
    """
    Version information for a deployed model.
    
    Used for version-aware inference.
    """
    version_id: str
    model_id: str
    version_number: str
    deployed_at: datetime
    is_active: bool
    weights_hash: str
    config_hash: str
    compatible_versions: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ModelEndpoint:
    """Endpoint configuration for model serving."""
    endpoint_id: str
    model_version: ModelVersion
    endpoint_type: str  # "grpc", "rest", "internal"
    host: str
    port: int
    is_healthy: bool
    last_health_check: datetime


# =============================================================================
# INFERENCE REQUEST/RESPONSE CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class InferenceRequest:
    """
    Immutable inference request.
    
    This is the INPUT contract for Phase 5 serving.
    """
    request_id: str
    model_id: str
    model_version: Optional[str]  # None = use latest
    input_data: Tuple[Tuple[str, Any], ...]  # Serializable key-value pairs
    inference_mode: InferenceMode
    timeout_ms: int
    cache_strategy: CacheStrategy
    requested_at: datetime
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InferenceResponse:
    """
    Immutable inference response.
    
    This is the OUTPUT contract for Phase 5 serving.
    """
    response_id: str
    request_id: str
    model_id: str
    model_version: str
    output_data: Tuple[Tuple[str, Any], ...]
    confidence: float
    latency_ms: float
    cache_hit: bool
    responded_at: datetime
    error: Optional[str] = None
    warnings: Tuple[str, ...] = field(default_factory=tuple)


# =============================================================================
# BATCH PROCESSING CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class BatchJob:
    """
    Definition of a batch inference job.
    """
    job_id: str
    model_id: str
    model_version: Optional[str]
    input_source: str  # Path or URI to input data
    output_destination: str  # Path or URI for results
    batch_size: int
    priority: int
    created_at: datetime
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class BatchJobStatus:
    """Status of a batch job execution."""
    job_id: str
    status: JobStatus
    total_items: int
    processed_items: int
    failed_items: int
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_summary: Optional[str] = None


@dataclass(frozen=True)
class BatchResult:
    """Results of a batch job."""
    result_id: str
    job_id: str
    successful_count: int
    failed_count: int
    output_path: str
    processing_time_seconds: float
    model_version_used: str
    completed_at: datetime


# =============================================================================
# CACHING CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class CacheEntry:
    """
    Entry in the inference cache.
    """
    cache_key: str
    request_hash: str
    response_data: Tuple[Tuple[str, Any], ...]
    model_version: str
    created_at: datetime
    expires_at: datetime
    hit_count: int = 0


@dataclass(frozen=True)
class CacheStats:
    """Statistics for cache performance."""
    total_entries: int
    hit_count: int
    miss_count: int
    eviction_count: int
    memory_usage_bytes: int
    hit_rate: float
    computed_at: datetime


# =============================================================================
# OPTIMIZATION CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class DistillationConfig:
    """Configuration for model distillation."""
    config_id: str
    teacher_model_id: str
    student_architecture: str
    temperature: float
    compression_ratio: float
    target_latency_ms: float


@dataclass(frozen=True)
class DistilledModel:
    """Result of model distillation."""
    model_id: str
    teacher_model_id: str
    config_id: str
    compression_achieved: float
    quality_retained: float  # 0.0 to 1.0
    latency_ms: float
    created_at: datetime


@dataclass(frozen=True)
class IndexConfig:
    """Configuration for temporal index acceleration."""
    index_id: str
    index_type: str  # "btree", "hash", "temporal"
    indexed_fields: Tuple[str, ...]
    partition_strategy: str
    created_at: datetime


@dataclass(frozen=True)
class IndexStats:
    """Statistics for an index."""
    index_id: str
    entry_count: int
    size_bytes: int
    query_speedup: float
    last_rebuild: datetime
