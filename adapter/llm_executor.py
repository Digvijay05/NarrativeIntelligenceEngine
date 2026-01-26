"""
LLM Model Executor
==================

Real LLM executor implementing ModelExecutorInterface.

BOUNDARY ENFORCEMENT:
- Read-only access (frozen snapshot input)
- Overlay-only output (annotations/scores)
- Deterministic envelope (snapshot_hash + model_version + seed)
- Reproducible failure (explicit error overlays)

This executor bridges the abstract ModelExecutorInterface to 
concrete LLM providers via the provider abstraction layer.
"""

from __future__ import annotations
from typing import List, Tuple, Optional
from datetime import datetime, timezone
import hashlib
import json
import time

from .contracts import (
    ModelAnalysisRequest,
    ModelAnalysisResponse,
    ModelVersionInfo,
    InvocationMetadata,
    ModelAnnotation,
    ModelScore,
    UncertaintyRange,
    ModelError,
    ModelErrorCode,
)
from .pipeline import ModelExecutorInterface
from .prompts import CanonicalPrompt
from .providers.base import (
    LLMProvider,
    ProviderResponse,
    ProviderErrorCode,
    InvocationParams,
)


# Task types supported by LLM executor
LLM_SUPPORTED_TASKS = frozenset({
    "contradiction_detection",
    "divergence_scoring",
    "coherence_analysis",
    "lifecycle_prediction",
})


class LLMModelExecutor(ModelExecutorInterface):
    """
    LLM-backed executor with seeded sampling.
    
    GUARANTEES:
    ===========
    1. Deterministic given (snapshot_hash, model_version, seed)
       - Where provider supports seeded sampling
    2. Prompt derived only from frozen snapshot
       - No UI context, no analyst hints
    3. All outputs are advisory overlays
       - Never entities, never threads, never timelines
    4. Failures are explicit error responses
       - No silent retries, no fallbacks
    
    EXPLICIT FAILURE STATES:
    - Provider timeout → TIMEOUT error
    - Provider rate limit → error overlay with retry guidance
    - Parse failure → INVALID_OUTPUT error
    - Provider error → mapped to ModelErrorCode
    """
    
    def __init__(
        self,
        provider: LLMProvider,
        temperature: float = 0.0,
        max_tokens: int = 4096,
        timeout_seconds: float = 30.0
    ):
        """
        Initialize LLM executor.
        
        Args:
            provider: LLM provider implementation
            temperature: Sampling temperature (0.0 for max determinism)
            max_tokens: Maximum response tokens
            timeout_seconds: Request timeout
        """
        self._provider = provider
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout_seconds = timeout_seconds
        self._version = self._compute_version()
    
    def get_version(self) -> ModelVersionInfo:
        """Get version info for deterministic envelope."""
        return self._version
    
    def supports_task(self, task_type: str) -> bool:
        """Check if task type is supported."""
        return task_type in LLM_SUPPORTED_TASKS
    
    def execute(
        self,
        request: ModelAnalysisRequest,
        random_seed: int
    ) -> ModelAnalysisResponse:
        """
        Execute LLM analysis with full tracing.
        
        DETERMINISM:
        Same (request.snapshot.content_hash(), self._version, random_seed)
        → Same response (where provider supports seeded sampling)
        """
        start_time = time.time()
        
        # Create invocation metadata
        invocation = InvocationMetadata.create(
            model_version=self._version,
            input_data=request.snapshot.content_hash(),
            random_seed=random_seed
        )
        
        try:
            # 1. Generate canonical prompt (pure function of snapshot)
            prompt = CanonicalPrompt.create(
                task_type=request.request_type,
                snapshot=request.snapshot
            )
            
            # 2. Create invocation params
            params = InvocationParams(
                seed=random_seed,
                temperature=self._temperature,
                max_tokens=self._max_tokens,
                timeout_seconds=self._timeout_seconds
            )
            
            # 3. Invoke provider
            provider_response = self._provider.invoke(
                prompt=prompt.prompt_text,
                params=params
            )
            
            # 4. Handle provider failure
            if not provider_response.success:
                return self._create_failure_response(
                    request=request,
                    invocation=invocation,
                    provider_response=provider_response
                )
            
            # 5. Parse response into annotations/scores
            annotations, scores = self._parse_response(
                content=provider_response.content,
                task_type=request.request_type,
                thread_id=request.snapshot.thread_id
            )
            
            processing_time_ms = (time.time() - start_time) * 1000
            
            return ModelAnalysisResponse.success_response(
                request_id=request.request_id,
                invocation=invocation,
                annotations=tuple(annotations),
                scores=tuple(scores),
                processing_time_ms=processing_time_ms
            )
            
        except ValueError as e:
            # Parse errors become explicit failures
            error = ModelError(
                error_code=ModelErrorCode.INVALID_OUTPUT,
                message=f"Failed to parse LLM response: {str(e)}",
                invocation_id=invocation.invocation_id,
                occurred_at=datetime.now(timezone.utc)
            )
            return ModelAnalysisResponse.failure_response(
                request_id=request.request_id,
                invocation=invocation,
                error=error
            )
            
        except Exception as e:
            error = ModelError(
                error_code=ModelErrorCode.INTERNAL_ERROR,
                message=str(e),
                invocation_id=invocation.invocation_id,
                occurred_at=datetime.now(timezone.utc)
            )
            return ModelAnalysisResponse.failure_response(
                request_id=request.request_id,
                invocation=invocation,
                error=error
            )
    
    def _create_failure_response(
        self,
        request: ModelAnalysisRequest,
        invocation: InvocationMetadata,
        provider_response: ProviderResponse
    ) -> ModelAnalysisResponse:
        """Map provider failure to ModelAnalysisResponse."""
        
        # Map provider error codes to model error codes
        error_code_map = {
            ProviderErrorCode.TIMEOUT: ModelErrorCode.TIMEOUT,
            ProviderErrorCode.RATE_LIMITED: ModelErrorCode.RATE_LIMITED,
            ProviderErrorCode.INVALID_RESPONSE: ModelErrorCode.INVALID_OUTPUT,
            ProviderErrorCode.CONTENT_FILTERED: ModelErrorCode.MODEL_REFUSAL,
            ProviderErrorCode.API_ERROR: ModelErrorCode.INTERNAL_ERROR,
            ProviderErrorCode.NETWORK_ERROR: ModelErrorCode.INTERNAL_ERROR,
            ProviderErrorCode.SEED_NOT_SUPPORTED: ModelErrorCode.INTERNAL_ERROR,
        }
        
        error = ModelError(
            error_code=error_code_map.get(
                provider_response.error_code, 
                ModelErrorCode.INTERNAL_ERROR
            ),
            message=provider_response.error_message or "Provider error",
            invocation_id=invocation.invocation_id,
            occurred_at=datetime.now(timezone.utc)
        )
        
        return ModelAnalysisResponse.failure_response(
            request_id=request.request_id,
            invocation=invocation,
            error=error
        )
    
    def _parse_response(
        self,
        content: str,
        task_type: str,
        thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """
        Parse LLM response content into structured annotations/scores.
        
        Raises ValueError if parsing fails.
        """
        try:
            data = json.loads(content)
        except json.JSONDecodeError as e:
            raise ValueError(f"Response is not valid JSON: {e}")
        
        annotations = []
        scores = []
        
        # Parse based on task type
        if task_type == "contradiction_detection":
            annotations, scores = self._parse_contradiction_response(data, thread_id)
        elif task_type == "divergence_scoring":
            annotations, scores = self._parse_divergence_response(data, thread_id)
        elif task_type == "coherence_analysis":
            annotations, scores = self._parse_coherence_response(data, thread_id)
        elif task_type == "lifecycle_prediction":
            annotations, scores = self._parse_lifecycle_response(data, thread_id)
        else:
            # Mock response format (for testing)
            if "scores" in data:
                for s in data["scores"]:
                    scores.append(ModelScore(
                        score_type=s.get("name", "unknown"),
                        value=float(s.get("value", 0.0)),
                        uncertainty=UncertaintyRange(
                            lower=max(0, float(s.get("value", 0.0)) - float(s.get("uncertainty", 0.1))),
                            upper=min(1, float(s.get("value", 0.0)) + float(s.get("uncertainty", 0.1))),
                            confidence_level=0.9
                        ),
                        entity_id=thread_id,
                        entity_type="thread"
                    ))
        
        return annotations, scores
    
    def _parse_contradiction_response(
        self, data: dict, thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Parse contradiction detection response."""
        annotations = []
        scores = []
        
        for i, c in enumerate(data.get("contradictions", [])):
            ann_id = hashlib.sha256(
                f"contradiction|{c.get('fragment_a')}|{c.get('fragment_b')}".encode()
            ).hexdigest()[:12]
            
            annotations.append(ModelAnnotation(
                annotation_id=f"ann_{ann_id}",
                annotation_type="contradiction",
                entity_id=f"{c.get('fragment_a')}:{c.get('fragment_b')}",
                entity_type="fragment_pair",
                value=json.dumps({
                    "claim_a": c.get("claim_a"),
                    "claim_b": c.get("claim_b")
                }),
                confidence=float(c.get("confidence", 0.5)),
                evidence_ids=(c.get("fragment_a"), c.get("fragment_b"))
            ))
        
        return annotations, scores
    
    def _parse_divergence_response(
        self, data: dict, thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Parse divergence scoring response."""
        annotations = []
        scores = []
        
        scores.append(ModelScore(
            score_type="divergence_risk",
            value=float(data.get("divergence_risk", 0.0)),
            uncertainty=UncertaintyRange(
                lower=max(0, float(data.get("divergence_risk", 0.0)) - float(data.get("uncertainty", 0.1))),
                upper=min(1, float(data.get("divergence_risk", 0.0)) + float(data.get("uncertainty", 0.1))),
                confidence_level=0.9
            ),
            entity_id=thread_id,
            entity_type="thread"
        ))
        
        for ind in data.get("indicators", []):
            ann_id = hashlib.sha256(
                f"divergence|{thread_id}|{ind.get('type')}".encode()
            ).hexdigest()[:12]
            
            annotations.append(ModelAnnotation(
                annotation_id=f"ann_{ann_id}",
                annotation_type=f"divergence_indicator_{ind.get('type')}",
                entity_id=thread_id,
                entity_type="thread",
                value=ind.get("description", ""),
                confidence=0.8,
                evidence_ids=tuple(ind.get("evidence_fragments", []))
            ))
        
        return annotations, scores
    
    def _parse_coherence_response(
        self, data: dict, thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Parse coherence analysis response."""
        annotations = []
        scores = []
        
        scores.append(ModelScore(
            score_type="temporal_coherence",
            value=float(data.get("coherence_score", 0.0)),
            uncertainty=UncertaintyRange(
                lower=max(0, float(data.get("coherence_score", 0.0)) - float(data.get("uncertainty", 0.1))),
                upper=min(1, float(data.get("coherence_score", 0.0)) + float(data.get("uncertainty", 0.1))),
                confidence_level=0.9
            ),
            entity_id=thread_id,
            entity_type="thread"
        ))
        
        for gap in data.get("gaps", []):
            frags = gap.get("between_fragments", [])
            ann_id = hashlib.sha256(
                f"gap|{thread_id}|{'|'.join(frags)}".encode()
            ).hexdigest()[:12]
            
            annotations.append(ModelAnnotation(
                annotation_id=f"ann_{ann_id}",
                annotation_type=f"temporal_gap_{gap.get('gap_type', 'unknown')}",
                entity_id=thread_id,
                entity_type="thread",
                value=f"Severity: {gap.get('severity', 0.0)}",
                confidence=float(gap.get("severity", 0.5)),
                evidence_ids=tuple(frags)
            ))
        
        return annotations, scores
    
    def _parse_lifecycle_response(
        self, data: dict, thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Parse lifecycle prediction response."""
        annotations = []
        scores = []
        
        ann_id = hashlib.sha256(f"lifecycle|{thread_id}".encode()).hexdigest()[:12]
        annotations.append(ModelAnnotation(
            annotation_id=f"ann_{ann_id}",
            annotation_type="lifecycle_state",
            entity_id=thread_id,
            entity_type="thread",
            value=data.get("assessed_state", "unknown"),
            confidence=float(data.get("confidence", 0.5)),
            evidence_ids=tuple(data.get("evidence", []))
        ))
        
        # State probabilities as scores
        for state, prob in data.get("state_probabilities", {}).items():
            scores.append(ModelScore(
                score_type=f"lifecycle_prob_{state}",
                value=float(prob),
                uncertainty=UncertaintyRange(lower=0.0, upper=1.0, confidence_level=0.8),
                entity_id=thread_id,
                entity_type="thread"
            ))
        
        return annotations, scores
    
    def _compute_version(self) -> ModelVersionInfo:
        """Compute version info for deterministic envelope."""
        provider_version = self._provider.get_version()
        
        # Version string includes provider info
        version_str = f"llm-{provider_version.model_id}-{provider_version.api_version}"
        
        # Config hash captures executor settings
        config = json.dumps({
            "temperature": self._temperature,
            "max_tokens": self._max_tokens,
            "timeout_seconds": self._timeout_seconds
        }, sort_keys=True)
        config_hash = hashlib.sha256(config.encode()).hexdigest()[:16]
        
        return ModelVersionInfo(
            model_id=provider_version.provider_id,
            model_version=version_str,
            weights_hash=provider_version.model_id,
            config_hash=config_hash,
            created_at=datetime.now(timezone.utc)
        )
