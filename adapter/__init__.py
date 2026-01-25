"""
Model Adapter Package

ARCHITECTURAL BOUNDARY:
=======================
This package is the ONLY allowed interface between backend and model layers.
All communication MUST flow through this adapter.

DIRECTION OF DEPENDENCY:
========================
backend → adapter → model

NEVER:
- Model importing from backend (except via adapter contracts)
- Backend importing from model (except via adapter contracts)
- Circular dependencies of any kind

DESIGN PRINCIPLES:
==================
1. Pure interface - no business logic
2. Typed request/response schemas only
3. Explicit version tags on all inputs/outputs
4. Model outputs are ADVISORY, never facts
5. Backend state is IMMUTABLE to model outputs
"""

# Core contracts (always available)
from .contracts import (
    ModelAnalysisRequest,
    NarrativeSnapshotInput,
    FragmentBatchInput,
    ModelAnalysisResponse,
    ModelAnnotation,
    ModelScore,
    UncertaintyRange,
    ModelError,
    ModelErrorCode,
    ModelVersionInfo,
    InvocationMetadata,
)

from .pipeline import (
    ModelInvocationPipeline,
    InvocationConfig,
    InvocationTrace,
    ModelExecutorInterface,
)

from .overlay import (
    ModelOverlay,
    OverlayStore,
    OverlayQuery,
    OverlayQueryResult,
)

# These require model layer - import lazily in facade
# from .facade import BackendModelFacade, AnalysisResult
# from .executor import NarrativeModelExecutor
# from .converter import SnapshotConverter

__all__ = [
    # Contracts
    'ModelAnalysisRequest', 'NarrativeSnapshotInput', 'FragmentBatchInput',
    'ModelAnalysisResponse', 'ModelAnnotation', 'ModelScore', 'UncertaintyRange',
    'ModelError', 'ModelErrorCode',
    'ModelVersionInfo', 'InvocationMetadata',
    # Pipeline
    'ModelInvocationPipeline', 'InvocationConfig', 'InvocationTrace',
    'ModelExecutorInterface',
    # Overlay
    'ModelOverlay', 'OverlayStore', 'OverlayQuery', 'OverlayQueryResult',
]


def get_facade():
    """
    Get backend façade (lazy import to avoid circular dependencies).
    
    Usage:
        from adapter import get_facade
        facade = get_facade()
        result = facade.analyze_thread(...)
    """
    from .facade import BackendModelFacade
    return BackendModelFacade()
