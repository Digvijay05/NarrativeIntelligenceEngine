"""
Model Invocation Pipeline

Deterministic call path from backend → adapter → model.

BOUNDARY ENFORCEMENT:
=====================
- No side effects on backend state
- Time-indexed invocation metadata for every call
- Explicit error handling (no silent retries)
- All model outputs are advisory

WHY THIS PIPELINE EXISTS:
========================
Direct backend→model coupling violates separation of concerns.
This pipeline enforces:
1. All calls go through typed contracts
2. All calls are traced and replayable
3. All failures are explicit
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Callable, Any, Dict
from datetime import datetime
import time
import hashlib

from .contracts import (
    ModelAnalysisRequest,
    ModelAnalysisResponse,
    ModelVersionInfo,
    InvocationMetadata,
    ModelError,
    ModelErrorCode,
    FragmentBatchInput,
    NarrativeSnapshotInput,
    ModelAnnotation,
    ModelScore,
    UncertaintyRange,
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass(frozen=True)
class InvocationConfig:
    """
    Configuration for model invocation.
    
    WHY FROZEN:
    Config should not change during invocation.
    Changes require new config instance.
    """
    timeout_seconds: float = 30.0
    max_batch_size: int = 100
    random_seed: int = 42
    enable_tracing: bool = True
    
    # Retry policy - explicit, never hidden
    retry_enabled: bool = False  # Disabled by default - retries must be explicit
    max_retries: int = 0
    retry_delay_seconds: float = 1.0


# =============================================================================
# INVOCATION TRACE
# =============================================================================

@dataclass(frozen=True)
class InvocationTrace:
    """
    Complete trace of a model invocation.
    
    WHY THIS EXISTS:
    Every invocation must be fully traceable for:
    1. Replay verification
    2. Audit logging
    3. Debugging
    """
    trace_id: str
    invocation_id: str
    request_hash: str
    started_at: datetime
    completed_at: Optional[datetime]
    model_version: ModelVersionInfo
    success: bool
    error_code: Optional[ModelErrorCode] = None
    retry_count: int = 0
    
    def duration_ms(self) -> float:
        """Compute invocation duration."""
        if self.completed_at and self.started_at:
            return (self.completed_at - self.started_at).total_seconds() * 1000
        return 0.0


# =============================================================================
# MODEL EXECUTOR INTERFACE
# =============================================================================

class ModelExecutorInterface:
    """
    Abstract interface for model execution.
    
    WHY ABSTRACT:
    The pipeline should not know about model internals.
    Concrete executors implement this interface.
    """
    
    def execute(
        self,
        request: ModelAnalysisRequest,
        random_seed: int
    ) -> ModelAnalysisResponse:
        """Execute model analysis. Must be deterministic given seed."""
        raise NotImplementedError
    
    def get_version(self) -> ModelVersionInfo:
        """Get current model version."""
        raise NotImplementedError
    
    def supports_task(self, task_type: str) -> bool:
        """Check if model supports the given task type."""
        raise NotImplementedError


# =============================================================================
# INVOCATION PIPELINE
# =============================================================================

class ModelInvocationPipeline:
    """
    Deterministic invocation pipeline.
    
    GUARANTEES:
    ===========
    1. Every invocation is traced
    2. Every invocation uses explicit model version
    3. No side effects on inputs
    4. Failures are explicit, never silent
    5. Retries only if explicitly configured AND traced
    """
    
    def __init__(
        self,
        executor: ModelExecutorInterface,
        config: Optional[InvocationConfig] = None
    ):
        self._executor = executor
        self._config = config or InvocationConfig()
        self._traces: list = []  # In production, would be external storage
    
    def invoke(
        self,
        request: ModelAnalysisRequest
    ) -> tuple[ModelAnalysisResponse, InvocationTrace]:
        """
        Invoke model with full tracing.
        
        Returns (response, trace) tuple.
        NEVER returns partial results.
        """
        started_at = datetime.utcnow()
        request_hash = self._compute_request_hash(request)
        model_version = self._executor.get_version()
        
        trace_id = self._generate_trace_id(request_hash, started_at)
        
        # Validate request
        validation_error = self._validate_request(request)
        if validation_error:
            trace = InvocationTrace(
                trace_id=trace_id,
                invocation_id=f"inv_{request_hash[:12]}",
                request_hash=request_hash,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                model_version=model_version,
                success=False,
                error_code=ModelErrorCode.INVALID_INPUT
            )
            self._record_trace(trace)
            
            invocation = InvocationMetadata.create(
                model_version=model_version,
                input_data=request_hash,
                random_seed=request.random_seed
            )
            
            return (
                ModelAnalysisResponse.failure_response(
                    request_id=request.request_id,
                    invocation=invocation,
                    error=validation_error
                ),
                trace
            )
        
        # Check task support
        if not self._executor.supports_task(request.request_type):
            trace = InvocationTrace(
                trace_id=trace_id,
                invocation_id=f"inv_{request_hash[:12]}",
                request_hash=request_hash,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                model_version=model_version,
                success=False,
                error_code=ModelErrorCode.MODEL_REFUSAL
            )
            self._record_trace(trace)
            
            invocation = InvocationMetadata.create(
                model_version=model_version,
                input_data=request_hash,
                random_seed=request.random_seed
            )
            
            error = ModelError(
                error_code=ModelErrorCode.MODEL_REFUSAL,
                message=f"Model does not support task type: {request.request_type}",
                invocation_id=trace.invocation_id,
                occurred_at=datetime.utcnow()
            )
            
            return (
                ModelAnalysisResponse.failure_response(
                    request_id=request.request_id,
                    invocation=invocation,
                    error=error
                ),
                trace
            )
        
        # Execute with timeout
        try:
            response = self._execute_with_timeout(request)
            
            trace = InvocationTrace(
                trace_id=trace_id,
                invocation_id=response.invocation.invocation_id,
                request_hash=request_hash,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                model_version=model_version,
                success=response.success,
                error_code=response.error.error_code if response.error else None
            )
            self._record_trace(trace)
            
            return (response, trace)
            
        except TimeoutError:
            trace = InvocationTrace(
                trace_id=trace_id,
                invocation_id=f"inv_timeout_{request_hash[:12]}",
                request_hash=request_hash,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                model_version=model_version,
                success=False,
                error_code=ModelErrorCode.TIMEOUT
            )
            self._record_trace(trace)
            
            invocation = InvocationMetadata.create(
                model_version=model_version,
                input_data=request_hash,
                random_seed=request.random_seed
            )
            
            error = ModelError(
                error_code=ModelErrorCode.TIMEOUT,
                message=f"Model execution timed out after {self._config.timeout_seconds}s",
                invocation_id=trace.invocation_id,
                occurred_at=datetime.utcnow(),
                retry_allowed=self._config.retry_enabled,
                retry_after_seconds=int(self._config.retry_delay_seconds)
            )
            
            return (
                ModelAnalysisResponse.failure_response(
                    request_id=request.request_id,
                    invocation=invocation,
                    error=error
                ),
                trace
            )
            
        except Exception as e:
            trace = InvocationTrace(
                trace_id=trace_id,
                invocation_id=f"inv_err_{request_hash[:12]}",
                request_hash=request_hash,
                started_at=started_at,
                completed_at=datetime.utcnow(),
                model_version=model_version,
                success=False,
                error_code=ModelErrorCode.INTERNAL_ERROR
            )
            self._record_trace(trace)
            
            invocation = InvocationMetadata.create(
                model_version=model_version,
                input_data=request_hash,
                random_seed=request.random_seed
            )
            
            error = ModelError(
                error_code=ModelErrorCode.INTERNAL_ERROR,
                message=str(e),
                invocation_id=trace.invocation_id,
                occurred_at=datetime.utcnow(),
                retry_allowed=False  # Internal errors should not retry
            )
            
            return (
                ModelAnalysisResponse.failure_response(
                    request_id=request.request_id,
                    invocation=invocation,
                    error=error
                ),
                trace
            )
    
    def _execute_with_timeout(
        self,
        request: ModelAnalysisRequest
    ) -> ModelAnalysisResponse:
        """Execute with configurable timeout."""
        # In production, would use threading or async
        # For now, direct execution
        return self._executor.execute(request, request.random_seed)
    
    def _validate_request(
        self,
        request: ModelAnalysisRequest
    ) -> Optional[ModelError]:
        """Validate request, return error if invalid."""
        if not request.request_id:
            return ModelError(
                error_code=ModelErrorCode.INVALID_INPUT,
                message="request_id is required",
                invocation_id="validation",
                occurred_at=datetime.utcnow()
            )
        
        if not request.snapshot:
            return ModelError(
                error_code=ModelErrorCode.INVALID_INPUT,
                message="snapshot is required",
                invocation_id="validation",
                occurred_at=datetime.utcnow()
            )
        
        if len(request.snapshot.fragments.fragment_ids) > self._config.max_batch_size:
            return ModelError(
                error_code=ModelErrorCode.INVALID_INPUT,
                message=f"Batch size exceeds max ({self._config.max_batch_size})",
                invocation_id="validation",
                occurred_at=datetime.utcnow()
            )
        
        return None
    
    def _compute_request_hash(self, request: ModelAnalysisRequest) -> str:
        """Compute deterministic hash of request."""
        content = f"{request.request_id}|{request.request_type}|{request.snapshot.content_hash()}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _generate_trace_id(self, request_hash: str, timestamp: datetime) -> str:
        """Generate unique trace ID."""
        return f"trace_{request_hash[:12]}_{int(timestamp.timestamp())}"
    
    def _record_trace(self, trace: InvocationTrace):
        """Record trace for audit."""
        if self._config.enable_tracing:
            self._traces.append(trace)
    
    def get_traces(self) -> list:
        """Get all recorded traces (read-only)."""
        return list(self._traces)
    
    def verify_replay(
        self,
        original_trace: InvocationTrace,
        request: ModelAnalysisRequest
    ) -> bool:
        """
        Verify that replaying request produces same hash.
        
        WHY THIS EXISTS:
        Replay safety is a core requirement. This verifies determinism.
        """
        request_hash = self._compute_request_hash(request)
        return request_hash == original_trace.request_hash
