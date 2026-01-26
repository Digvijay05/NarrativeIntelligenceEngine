"""
Temporal Alignment Engine
=========================

Timeline alignment using Dynamic Time Warping (DTW).

ML FENCE POST:
==============
This engine computes ALIGNMENT (geometry), not CAUSALITY (inference).

ALLOWED:
- Computing DTW distance between timelines
- Finding optimal alignment path
- Handling temporal shifts/distortions
- Returning raw alignment data

FORBIDDEN:
- "Completeness" scoring
- "First-mover" authority bonuses
- Inferring causality from temporal precedence
- Judging "correctness" of one timeline over another
"""

from __future__ import annotations
from typing import List, Tuple, Optional, Union
from dataclasses import dataclass
import numpy as np

# Lazy import tslearn to allow graceful degradation/startup
try:
    from tslearn.metrics import dtw, dtw_path
    _TSLEARN_AVAILABLE = True
except ImportError:
    _TSLEARN_AVAILABLE = False


@dataclass(frozen=True)
class AlignmentResult:
    """
    Immutable result of temporal alignment.
    
    ML FENCE POST:
    - distance: Geometric distance (lower = more similar shape)
    - path: Geometric mapping of points
    - NO JUDGMENT about which timeline is superior
    """
    distance: float
    path: Tuple[Tuple[int, int], ...]
    is_valid: bool
    error_message: Optional[str] = None


class TemporalAlignmentEngine:
    """
    Engine for temporal alignment of narrative timelines.
    
    Wraps tslearn to explicitly allow only forensic/geometric operations
    and ban interpretive/ranking operations.
    """
    
    def __init__(self):
        self._available = _TSLEARN_AVAILABLE
    
    def is_available(self) -> bool:
        """Check if tslearn is available."""
        return self._available
    
    def compute_alignment(
        self,
        timeline_a: List[float],
        timeline_b: List[float]
    ) -> AlignmentResult:
        """
        Compute DTW alignment between two scalar timelines.
        
        Args:
            timeline_a: List of scalar values (e.g., intensity, sentiment, activity)
            timeline_b: List of scalar values
            
        Returns:
            AlignmentResult with distance and path
        
        ML FENCE POST:
        - Returns raw geometric alignment
        - Does NOT standardize or normalize input (caller responsibility)
        - Does NOT interpret the meaning of the distance
        """
        if not self._available:
            return AlignmentResult(
                distance=-1.0,
                path=(),
                is_valid=False,
                error_message="tslearn library not available"
            )
            
        if not timeline_a or not timeline_b:
            return AlignmentResult(
                distance=-1.0, 
                path=(), 
                is_valid=False,
                error_message="Empty timeline(s) provided"
            )
            
        try:
            # Convert to numpy arrays if needed
            ts_a = np.array(timeline_a, dtype=float)
            ts_b = np.array(timeline_b, dtype=float)
            
            # Compute path and distance
            path, distance = dtw_path(ts_a, ts_b)
            
            return AlignmentResult(
                distance=float(distance),
                path=tuple(tuple(p) for p in path),
                is_valid=True
            )
            
        except Exception as e:
            return AlignmentResult(
                distance=-1.0,
                path=(),
                is_valid=False,
                error_message=str(e)
            )
            
    def compute_distance(
        self,
        timeline_a: List[float],
        timeline_b: List[float]
    ) -> float:
        """
        Compute only the DTW distance (faster if path not needed).
        
        Returns raw distance or -1.0 on error.
        """
        if not self._available:
            return -1.0
            
        if not timeline_a or not timeline_b:
            return -1.0
            
        try:
            ts_a = np.array(timeline_a, dtype=float)
            ts_b = np.array(timeline_b, dtype=float)
            return float(dtw(ts_a, ts_b))
        except Exception:
            return -1.0
