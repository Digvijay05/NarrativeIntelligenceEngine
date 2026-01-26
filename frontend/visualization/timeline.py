"""
Timeline Visualization Contracts

Responsibility:
Deterministic transformation of Narrative States into Renderable Timeline Views.
Input: NarrativeThreadDTO (State) -> Output: TimelineView (Visualization)
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple
from enum import Enum
from datetime import datetime

from frontend.state import DTOVersion, AvailabilityState, ContinuityState, SilenceType

@dataclass(frozen=True)
class RenderedSegment:
    """A visual segment ready for rendering."""
    visual_id: str
    start_x: float          # Normalized 0-1 or pixel offset
    width: float            # Normalized 0-1 or pixel width
    color_token: str        # Design system color token
    label: str
    is_interactive: bool
    continuity_left: ContinuityState
    continuity_right: ContinuityState
    silence_marker: Optional[SilenceType]

@dataclass(frozen=True)
class TimeAxis:
    """The rendered time axis."""
    start_time: datetime
    end_time: datetime
    ticks: Tuple[Tuple[float, str], ...] # (position, label)
    label: str

@dataclass(frozen=True)
class TimelineView:
    """
    Fully calculated timeline visualization.
    
    DETERMINISTIC:
    Same thread + same viewport = identical view.
    No layout logic allowed in React component - all pre-calculated here.
    """
    view_id: str
    segments: Tuple[RenderedSegment, ...]
    axis: TimeAxis
    viewport_start: datetime
    viewport_end: datetime
    availability: AvailabilityState
    generated_at: datetime
