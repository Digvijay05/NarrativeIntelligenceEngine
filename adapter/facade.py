"""
Backend Façade

Clean interface for backend to invoke model analysis.

BOUNDARY ENFORCEMENT:
=====================
Backend imports ONLY this façade.
Backend NEVER imports directly from model layer.

WHY A FAÇADE:
=============
1. Single point of integration
2. Encapsulates all adapter complexity
3. Provides simple, typed API to backend
4. Enforces that model outputs are overlays, not mutations
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Tuple
from datetime import datetime
import hashlib

from .contracts import (
    ModelAnalysisRequest,
    ModelAnalysisResponse,
    NarrativeSnapshotInput,
    FragmentBatchInput,
    ModelVersionInfo,
)
from .pipeline import ModelInvocationPipeline, InvocationConfig, InvocationTrace
from .overlay import ModelOverlay, OverlayStore, OverlayQuery, OverlayQueryResult
from .executor import NarrativeModelExecutor


# =============================================================================
# BACKEND-FACING TYPES
# =============================================================================

@dataclass(frozen=True)
class AnalysisResult:
    """
    Simplified result for backend consumption.
    
    WHY THIS EXISTS:
    Backend doesn't need full adapter complexity.
    This provides a clean, simple interface.
    """
    success: bool
    overlay: Optional[ModelOverlay]
    trace_id: str
    processing_time_ms: float
    error_message: Optional[str] = None


# =============================================================================
# BACKEND FAÇADE
# =============================================================================

class BackendModelFacade:
    """
    Façade for backend to invoke model analysis.
    
    USAGE:
    ======
    ```python
    facade = BackendModelFacade()
    
    result = facade.analyze_thread(
        thread_id="thread_123",
        thread_lifecycle="active",
        fragment_ids=["frag_1", "frag_2"],
        fragment_contents=["content 1", "content 2"],
        ...
    )
    
    if result.success:
        overlay = result.overlay
        # Use overlay annotations/scores as ADVISORY signals
    else:
        # Handle error explicitly
        print(result.error_message)
    ```
    
    GUARANTEES:
    ===========
    1. All analysis results are stored as overlays
    2. All invocations are traced
    3. Backend state is NEVER mutated
    4. Errors are explicit, never silent
    """
    
    def __init__(self, config: Optional[InvocationConfig] = None):
        self._executor = NarrativeModelExecutor()
        self._pipeline = ModelInvocationPipeline(
            executor=self._executor,
            config=config or InvocationConfig()
        )
        self._overlay_store = OverlayStore()
    
    # =========================================================================
    # ANALYSIS METHODS
    # =========================================================================
    
    def analyze_thread(
        self,
        thread_id: str,
        thread_version: str,
        thread_lifecycle: str,
        fragment_ids: List[str],
        fragment_contents: List[str],
        fragment_timestamps: List[datetime],
        topic_ids: Optional[List[List[str]]] = None,
        entity_ids: Optional[List[List[str]]] = None,
        source_ids: Optional[List[str]] = None,
        task_type: str = "divergence_scoring",
        random_seed: int = 42
    ) -> AnalysisResult:
        """
        Analyze a narrative thread.
        
        Returns AnalysisResult with overlay if successful.
        Overlay contains ADVISORY annotations and scores.
        """
        # Build request
        request = self._build_request(
            thread_id=thread_id,
            thread_lifecycle=thread_lifecycle,
            fragment_ids=fragment_ids,
            fragment_contents=fragment_contents,
            fragment_timestamps=fragment_timestamps,
            topic_ids=topic_ids or [[] for _ in fragment_ids],
            entity_ids=entity_ids or [[] for _ in fragment_ids],
            source_ids=source_ids or ["unknown"] * len(fragment_ids),
            task_type=task_type,
            random_seed=random_seed
        )
        
        # Invoke pipeline
        response, trace = self._pipeline.invoke(request)
        
        # Store as overlay if successful
        overlay = None
        if response.success:
            overlay = self._overlay_store.store(
                response=response,
                entity_id=thread_id,
                entity_type="thread",
                entity_version=thread_version
            )
        
        return AnalysisResult(
            success=response.success,
            overlay=overlay,
            trace_id=trace.trace_id,
            processing_time_ms=response.processing_time_ms,
            error_message=response.error.message if response.error else None
        )
    
    def detect_contradictions(
        self,
        thread_id: str,
        thread_version: str,
        fragment_ids: List[str],
        fragment_contents: List[str],
        fragment_timestamps: List[datetime],
        random_seed: int = 42
    ) -> AnalysisResult:
        """Detect contradictions in thread fragments."""
        return self.analyze_thread(
            thread_id=thread_id,
            thread_version=thread_version,
            thread_lifecycle="active",
            fragment_ids=fragment_ids,
            fragment_contents=fragment_contents,
            fragment_timestamps=fragment_timestamps,
            task_type="contradiction_detection",
            random_seed=random_seed
        )
    
    def score_coherence(
        self,
        thread_id: str,
        thread_version: str,
        fragment_ids: List[str],
        fragment_contents: List[str],
        fragment_timestamps: List[datetime],
        random_seed: int = 42
    ) -> AnalysisResult:
        """Score temporal coherence of thread."""
        return self.analyze_thread(
            thread_id=thread_id,
            thread_version=thread_version,
            thread_lifecycle="active",
            fragment_ids=fragment_ids,
            fragment_contents=fragment_contents,
            fragment_timestamps=fragment_timestamps,
            task_type="coherence_analysis",
            random_seed=random_seed
        )
    
    def predict_lifecycle(
        self,
        thread_id: str,
        thread_version: str,
        thread_lifecycle: str,
        fragment_ids: List[str],
        fragment_contents: List[str],
        fragment_timestamps: List[datetime],
        random_seed: int = 42
    ) -> AnalysisResult:
        """Predict lifecycle state of thread."""
        return self.analyze_thread(
            thread_id=thread_id,
            thread_version=thread_version,
            thread_lifecycle=thread_lifecycle,
            fragment_ids=fragment_ids,
            fragment_contents=fragment_contents,
            fragment_timestamps=fragment_timestamps,
            task_type="lifecycle_prediction",
            random_seed=random_seed
        )
    
    # =========================================================================
    # OVERLAY QUERIES
    # =========================================================================
    
    def get_latest_overlay(
        self,
        entity_id: str,
        model_version: Optional[str] = None
    ) -> Optional[ModelOverlay]:
        """Get latest overlay for an entity."""
        return self._overlay_store.get_latest_for_entity(
            entity_id=entity_id,
            model_version=model_version
        )
    
    def get_overlay_history(
        self,
        entity_id: str,
        max_results: int = 50
    ) -> Tuple[ModelOverlay, ...]:
        """Get overlay history for an entity."""
        return self._overlay_store.get_history(
            entity_id=entity_id,
            max_results=max_results
        )
    
    def query_overlays(self, query: OverlayQuery) -> OverlayQueryResult:
        """Query overlays with filters."""
        return self._overlay_store.query(query)
    
    # =========================================================================
    # VERSION AND TRACE INFO
    # =========================================================================
    
    def get_model_version(self) -> ModelVersionInfo:
        """Get current model version."""
        return self._executor.get_version()
    
    def get_traces(self) -> List[InvocationTrace]:
        """Get all invocation traces."""
        return self._pipeline.get_traces()
    
    # =========================================================================
    # INTERNAL HELPERS
    # =========================================================================
    
    def _build_request(
        self,
        thread_id: str,
        thread_lifecycle: str,
        fragment_ids: List[str],
        fragment_contents: List[str],
        fragment_timestamps: List[datetime],
        topic_ids: List[List[str]],
        entity_ids: List[List[str]],
        source_ids: List[str],
        task_type: str,
        random_seed: int
    ) -> ModelAnalysisRequest:
        """Build analysis request from parameters."""
        # Create fragment batch
        batch = FragmentBatchInput(
            batch_id=self._generate_batch_id(fragment_ids),
            fragment_ids=tuple(fragment_ids),
            fragment_contents=tuple(fragment_contents),
            fragment_timestamps=tuple(fragment_timestamps),
            topic_ids=tuple(tuple(t) for t in topic_ids),
            entity_ids=tuple(tuple(e) for e in entity_ids),
            source_ids=tuple(source_ids)
        )
        
        # Create snapshot
        snapshot = NarrativeSnapshotInput(
            snapshot_id=self._generate_snapshot_id(thread_id),
            snapshot_version="v1",
            captured_at=datetime.utcnow(),
            thread_id=thread_id,
            thread_lifecycle=thread_lifecycle,
            thread_topics=tuple(set(t for topics in topic_ids for t in topics)),
            fragments=batch,
            existing_annotations=()
        )
        
        # Create request
        request_id = self._generate_request_id(thread_id, task_type)
        
        return ModelAnalysisRequest(
            request_id=request_id,
            request_type=task_type,
            snapshot=snapshot,
            random_seed=random_seed
        )
    
    def _generate_batch_id(self, fragment_ids: List[str]) -> str:
        """Generate batch ID."""
        content = f"batch|{','.join(fragment_ids)}|{datetime.utcnow().isoformat()}"
        return f"batch_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    
    def _generate_snapshot_id(self, thread_id: str) -> str:
        """Generate snapshot ID."""
        content = f"snap|{thread_id}|{datetime.utcnow().isoformat()}"
        return f"snap_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
    
    def _generate_request_id(self, thread_id: str, task_type: str) -> str:
        """Generate request ID."""
        content = f"req|{thread_id}|{task_type}|{datetime.utcnow().isoformat()}"
        return f"req_{hashlib.sha256(content.encode()).hexdigest()[:12]}"
