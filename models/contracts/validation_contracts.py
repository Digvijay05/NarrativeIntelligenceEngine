"""
Validation Contracts

Defines immutable data structures for Phase 4 (Validation).
All metrics, monitoring, and error analysis use these contracts.

NO VALIDATION LOGIC HERE - only data definitions.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Tuple, Optional
from datetime import datetime
from enum import Enum, auto


# =============================================================================
# ENUMS
# =============================================================================

class MetricType(Enum):
    """Types of validation metrics."""
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1 = "f1"
    COHERENCE = "coherence"
    COMPLETENESS = "completeness"
    LATENCY = "latency"
    THROUGHPUT = "throughput"


class AlertSeverity(Enum):
    """Severity levels for alerts."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class DriftType(Enum):
    """Types of drift detected."""
    DATA_DRIFT = "data_drift"
    CONCEPT_DRIFT = "concept_drift"
    PREDICTION_DRIFT = "prediction_drift"
    TEMPORAL_DRIFT = "temporal_drift"


class ErrorSeverity(Enum):
    """Severity of errors."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# =============================================================================
# METRIC CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class MetricResult:
    """
    Single metric computation result.
    
    Immutable snapshot of a metric at a point in time.
    """
    metric_id: str
    metric_type: MetricType
    metric_name: str
    value: float
    threshold: Optional[float]
    is_passing: bool
    computed_at: datetime
    model_version: str
    data_version: str
    metadata: Tuple[Tuple[str, str], ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class CoherenceScore:
    """Temporal coherence score for a sequence."""
    score_id: str
    entity_id: str
    entity_type: str
    coherence_value: float  # 0.0 to 1.0
    gap_penalty: float
    anomaly_penalty: float
    computed_at: datetime
    model_version: str


@dataclass(frozen=True)
class CompletenessScore:
    """Narrative completeness score."""
    score_id: str
    thread_id: str
    completeness_value: float  # 0.0 to 1.0
    expected_fragments: int
    actual_fragments: int
    missing_topics: Tuple[str, ...]
    computed_at: datetime


@dataclass(frozen=True)
class AccuracyScore:
    """Accuracy metrics for model predictions."""
    score_id: str
    model_id: str
    task_type: str
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    sample_size: int
    computed_at: datetime


# =============================================================================
# MONITORING CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class DegradationMetric:
    """Metric tracking model degradation over time."""
    metric_id: str
    model_id: str
    metric_name: str
    baseline_value: float
    current_value: float
    change_percent: float
    is_degraded: bool
    first_observed: datetime
    last_observed: datetime


@dataclass(frozen=True)
class DriftAlert:
    """
    Alert for detected drift.
    
    Signals when model behavior changes unexpectedly.
    """
    alert_id: str
    drift_type: DriftType
    severity: AlertSeverity
    model_id: str
    description: str
    drift_magnitude: float
    baseline_reference: str
    detected_at: datetime
    acknowledged: bool = False
    resolved_at: Optional[datetime] = None


@dataclass(frozen=True)
class PatternDivergenceAlert:
    """Alert for pattern divergence from expected behavior."""
    alert_id: str
    pattern_id: str
    expected_pattern: str
    observed_pattern: str
    divergence_score: float
    severity: AlertSeverity
    detected_at: datetime


# =============================================================================
# VALIDATION REPORT CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class ValidationReport:
    """
    Comprehensive validation report for a model.
    
    Aggregates all validation results.
    """
    report_id: str
    model_id: str
    model_version: str
    overall_status: str  # "passed", "warnings", "failed"
    metrics: Tuple[MetricResult, ...]
    alerts: Tuple[DriftAlert, ...]
    passing_count: int
    failing_count: int
    warning_count: int
    generated_at: datetime
    data_version: str
    recommendations: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ComparisonReport:
    """Comparison between two model versions."""
    report_id: str
    model_a_version: str
    model_b_version: str
    metric_comparisons: Tuple[Tuple[str, float, float], ...]  # (metric, value_a, value_b)
    winner: Optional[str]  # None if inconclusive
    confidence: float
    generated_at: datetime


# =============================================================================
# ERROR ANALYSIS CONTRACTS
# =============================================================================

@dataclass(frozen=True)
class ErrorCategory:
    """
    Categorization of an error type.
    """
    category_id: str
    category_name: str
    description: str
    severity: ErrorSeverity
    count: int
    first_occurrence: datetime
    last_occurrence: datetime
    example_ids: Tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class InferenceFailure:
    """Record of an inference failure."""
    failure_id: str
    request_id: str
    model_id: str
    model_version: str
    failure_type: str
    error_message: str
    input_hash: str
    occurred_at: datetime
    stack_trace: Optional[str] = None


@dataclass(frozen=True)
class RootCauseAnalysis:
    """
    Root cause analysis for a failure pattern.
    """
    analysis_id: str
    failure_pattern: str
    root_cause: str
    contributing_factors: Tuple[str, ...]
    affected_count: int
    recommendation: str
    confidence: float
    analyzed_at: datetime


@dataclass(frozen=True)
class DataQualityIssue:
    """Record of a data quality issue."""
    issue_id: str
    issue_type: str  # "missing", "invalid", "inconsistent"
    affected_field: str
    affected_count: int
    sample_ids: Tuple[str, ...]
    severity: ErrorSeverity
    detected_at: datetime


@dataclass(frozen=True)
class TemporalInconsistency:
    """Record of temporal inconsistency in data."""
    inconsistency_id: str
    entity_id: str
    expected_sequence: Tuple[str, ...]
    actual_sequence: Tuple[str, ...]
    severity: ErrorSeverity
    detected_at: datetime
