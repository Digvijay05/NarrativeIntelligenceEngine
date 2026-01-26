"""
Model Overlay Reference DTO

Reference to model outputs (advisory signals).

REFERENCE ONLY:
===============
Contains IDs and metadata, not actual model outputs.
Frontend cannot interpret model signals.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Tuple, Optional
from datetime import datetime

from .core import DTOVersion, AvailabilityState


@dataclass(frozen=True)
class ScoreRefDTO:
    """
    Reference to a model score.
    
    REFERENCE ONLY:
    ===============
    Value is included for display, but frontend MUST NOT:
    - Compare scores
    - Rank by score
    - Threshold scores
    - Aggregate scores
    """
    score_type: str
    value: float
    lower_bound: float
    upper_bound: float
    confidence_level: float
    
    # Display hint (backend-controlled)
    display_category: str  # "low", "medium", "high" - backend decides
    display_label: Optional[str]


@dataclass(frozen=True)
class AnnotationRefDTO:
    """
    Reference to a model annotation.
    
    DISPLAY ONLY:
    =============
    Annotation is for display, not interpretation.
    """
    annotation_type: str
    value: str
    confidence: float
    display_label: Optional[str]


@dataclass(frozen=True)
class ModelOverlayRefDTO:
    """
    Reference to a model overlay.
    
    READ-ONLY CONTRACT:
    ===================
    - Model outputs are ADVISORY
    - Frontend displays, never interprets
    - No comparison between overlays
    - No aggregation across overlays
    
    PROHIBITED:
    ===========
    - aggregate_score: float
    - combined_confidence: float
    - is_reliable: bool
    - rank: int
    """
    # Version
    dto_version: DTOVersion
    
    # Identity
    overlay_id: str
    entity_id: str
    entity_type: str  # "thread", "segment", "fragment"
    entity_version: str
    
    # Model metadata (for display only)
    model_version: str
    model_id: str
    
    # Scores (display only)
    scores: Tuple[ScoreRefDTO, ...]
    
    # Annotations (display only)
    annotations: Tuple[AnnotationRefDTO, ...]
    
    # Timestamps
    created_at: datetime
    
    # Availability
    availability: AvailabilityState
    
    # Display metadata
    display_label: Optional[str]
    
    def __post_init__(self):
        if self.dto_version != DTOVersion.current():
            raise ValueError(f"Unknown DTO version: {self.dto_version}")
