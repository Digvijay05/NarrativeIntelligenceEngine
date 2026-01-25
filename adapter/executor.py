"""
Model Executor Implementation

Bridges adapter contracts to actual model layer.

BOUNDARY ENFORCEMENT:
=====================
This is the ONLY module that imports from both adapter and models.
It translates between the two without leaking abstractions.

WHY THIS EXISTS:
================
1. Adapter contracts are backend-facing
2. Model contracts are model-internal
3. This executor translates between them
"""

from __future__ import annotations
from typing import List, Tuple, Optional, Any
from datetime import datetime
import hashlib
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

# Import from model layer - using actual exported types
from models.contracts.data_contracts import (
    RawDataPoint, PreprocessedFragment, AnnotatedFragment,
    SemanticFeatures, TemporalFeatures, DataQuality,
    FeatureVector, Annotation, AnnotationType,
)
from models.contracts.temporal_contracts import (
    LifecycleState, TemporalState, LifecyclePrediction,
    DivergencePrediction, TemporalCoherence,
)


# =============================================================================
# SUPPORTED TASK TYPES
# =============================================================================

SUPPORTED_TASKS = frozenset({
    "contradiction_detection",
    "divergence_scoring",
    "coherence_analysis",
    "lifecycle_prediction",
})


# =============================================================================
# MODEL EXECUTOR
# =============================================================================

class NarrativeModelExecutor(ModelExecutorInterface):
    """
    Concrete executor bridging adapter to model layer.
    
    GUARANTEES:
    ===========
    1. Deterministic given same input + seed
    2. No side effects on model state
    3. All outputs have explicit uncertainty
    4. Failed analysis returns explicit errors
    """
    
    def __init__(self):
        self._version = self._compute_version()
    
    def get_version(self) -> ModelVersionInfo:
        """Get current model version."""
        return self._version
    
    def supports_task(self, task_type: str) -> bool:
        """Check if task type is supported."""
        return task_type in SUPPORTED_TASKS
    
    def execute(
        self,
        request: ModelAnalysisRequest,
        random_seed: int
    ) -> ModelAnalysisResponse:
        """
        Execute model analysis.
        
        Deterministic given same input + seed.
        """
        start_time = time.time()
        
        # Create invocation metadata
        invocation = InvocationMetadata.create(
            model_version=self._version,
            input_data=request.snapshot.content_hash(),
            random_seed=random_seed
        )
        
        try:
            # Execute based on task type
            annotations, scores = self._execute_task(
                task_type=request.request_type,
                request=request,
                random_seed=random_seed
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
            error = ModelError(
                error_code=ModelErrorCode.INSUFFICIENT_DATA,
                message=str(e),
                invocation_id=invocation.invocation_id,
                occurred_at=datetime.utcnow()
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
                occurred_at=datetime.utcnow()
            )
            return ModelAnalysisResponse.failure_response(
                request_id=request.request_id,
                invocation=invocation,
                error=error
            )
    
    def _execute_task(
        self,
        task_type: str,
        request: ModelAnalysisRequest,
        random_seed: int
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Execute specific task type."""
        thread_id = request.snapshot.thread_id
        fragments = request.snapshot.fragments
        
        if task_type == "contradiction_detection":
            return self._detect_contradictions(fragments, thread_id)
        
        elif task_type == "divergence_scoring":
            return self._score_divergence(fragments, thread_id)
        
        elif task_type == "coherence_analysis":
            return self._analyze_coherence(fragments, thread_id)
        
        elif task_type == "lifecycle_prediction":
            return self._predict_lifecycle(fragments, thread_id)
        
        return [], []
    
    def _detect_contradictions(
        self,
        fragments: Any,
        thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Detect contradictions between fragments."""
        annotations = []
        scores = []
        
        # Analyze fragment pairs
        n = len(fragments.fragment_ids)
        for i in range(n):
            for j in range(i+1, n):
                # Simple heuristic: check if contents differ significantly
                # In production, would use actual contradiction model
                frag_a = fragments.fragment_ids[i]
                frag_b = fragments.fragment_ids[j]
                
                ann_id = hashlib.sha256(
                    f"contra|{frag_a}|{frag_b}".encode()
                ).hexdigest()[:12]
                
                # Simulated contradiction detection (would be real model)
                prob = 0.3  # Low default
                
                scores.append(ModelScore(
                    score_type="contradiction_probability",
                    value=prob,
                    uncertainty=UncertaintyRange(
                        lower=max(0, prob - 0.15),
                        upper=min(1, prob + 0.15),
                        confidence_level=0.9
                    ),
                    entity_id=f"{frag_a}:{frag_b}",
                    entity_type="fragment_pair"
                ))
        
        return annotations, scores
    
    def _score_divergence(
        self,
        fragments: Any,
        thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Score divergence risk for thread."""
        annotations = []
        scores = []
        
        n = len(fragments.fragment_ids)
        if n == 0:
            return annotations, scores
        
        # Simulated divergence scoring
        divergence_prob = min(0.9, n * 0.1)
        
        scores.append(ModelScore(
            score_type="divergence_risk",
            value=divergence_prob,
            uncertainty=UncertaintyRange(
                lower=max(0, divergence_prob - 0.15),
                upper=min(1, divergence_prob + 0.15),
                confidence_level=0.9
            ),
            entity_id=thread_id,
            entity_type="thread"
        ))
        
        if divergence_prob > 0.5:
            ann_id = hashlib.sha256(f"div|{thread_id}".encode()).hexdigest()[:12]
            annotations.append(ModelAnnotation(
                annotation_id=f"ann_{ann_id}",
                annotation_type="divergence_risk_factor",
                entity_id=thread_id,
                entity_type="thread",
                value="high_fragment_count",
                confidence=divergence_prob,
                evidence_ids=tuple(fragments.fragment_ids[:3])
            ))
        
        return annotations, scores
    
    def _analyze_coherence(
        self,
        fragments: Any,
        thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Analyze temporal coherence."""
        annotations = []
        scores = []
        
        n = len(fragments.fragment_ids)
        if n == 0:
            return annotations, scores
        
        # Simulated coherence analysis
        coherence = max(0.3, 1.0 - (n * 0.05))
        gaps = max(0, n - 3)
        
        scores.append(ModelScore(
            score_type="temporal_coherence",
            value=coherence,
            uncertainty=UncertaintyRange(
                lower=max(0, coherence - 0.1),
                upper=min(1, coherence + 0.1),
                confidence_level=0.95
            ),
            entity_id=thread_id,
            entity_type="thread"
        ))
        
        if gaps > 0:
            ann_id = hashlib.sha256(f"gaps|{thread_id}".encode()).hexdigest()[:12]
            annotations.append(ModelAnnotation(
                annotation_id=f"ann_{ann_id}",
                annotation_type="temporal_gaps",
                entity_id=thread_id,
                entity_type="thread",
                value=f"{gaps} gaps detected",
                confidence=0.8,
                evidence_ids=()
            ))
        
        return annotations, scores
    
    def _predict_lifecycle(
        self,
        fragments: Any,
        thread_id: str
    ) -> Tuple[List[ModelAnnotation], List[ModelScore]]:
        """Predict lifecycle state."""
        annotations = []
        scores = []
        
        n = len(fragments.fragment_ids)
        if n == 0:
            return annotations, scores
        
        # Simulated lifecycle prediction
        if n < 3:
            state = "emerging"
            transition_prob = 0.7
        elif n < 10:
            state = "active"
            transition_prob = 0.3
        else:
            state = "dormant"
            transition_prob = 0.5
        
        scores.append(ModelScore(
            score_type="lifecycle_state",
            value=float(n) / 20.0,
            uncertainty=UncertaintyRange(lower=0.5, upper=0.9, confidence_level=0.9),
            entity_id=thread_id,
            entity_type="thread"
        ))
        
        scores.append(ModelScore(
            score_type="transition_probability",
            value=transition_prob,
            uncertainty=UncertaintyRange(
                lower=max(0, transition_prob - 0.2),
                upper=min(1, transition_prob + 0.2),
                confidence_level=0.85
            ),
            entity_id=thread_id,
            entity_type="thread"
        ))
        
        ann_id = hashlib.sha256(f"lifecycle|{thread_id}".encode()).hexdigest()[:12]
        annotations.append(ModelAnnotation(
            annotation_id=f"ann_{ann_id}",
            annotation_type="lifecycle_state",
            entity_id=thread_id,
            entity_type="thread",
            value=state,
            confidence=0.8,
            evidence_ids=tuple(fragments.fragment_ids[-3:]) if n >= 3 else tuple(fragments.fragment_ids)
        ))
        
        return annotations, scores
    
    def _compute_version(self) -> ModelVersionInfo:
        """Compute current model version."""
        version_str = "1.0.0"
        weights_hash = hashlib.sha256(b"narrative_model_weights_v1").hexdigest()[:16]
        config_hash = hashlib.sha256(b"narrative_model_config_v1").hexdigest()[:16]
        
        return ModelVersionInfo(
            model_id="narrative_intelligence_model",
            model_version=version_str,
            weights_hash=weights_hash,
            config_hash=config_hash,
            created_at=datetime.utcnow()
        )
