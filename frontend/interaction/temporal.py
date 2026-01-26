"""
Interaction Contracts

Responsibility:
Define valid user actions and their intent.
No execution logic - just pure intent modeling.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Any
from datetime import datetime

class ActionType(Enum):
    """Types of user interaction."""
    # Temporal
    SEEK_TIME = "seek_time"
    SET_RANGE = "set_range"
    PLAY_FORWARD = "play_forward"
    PAUSE = "pause"
    STEP_FRAME = "step_frame"
    
    # Selection
    SELECT_THREAD = "select_thread"
    SELECT_FRAGMENT = "select_fragment"
    FOCUS_ENTITY = "focus_entity"
    
    # Comparison
    TOGGLE_DIFF = "toggle_diff"
    ALIGN_THREADS = "align_threads"

@dataclass(frozen=True)
class InteractionRequest:
    """A specific user intent."""
    request_id: str
    action: ActionType
    payload: dict
    timestamp: datetime
    source_component: str

@dataclass(frozen=True)
class TemporalControlState:
    """
    State of the time control UI.
    Separate from the rendered timeline.
    """
    current_time: datetime
    is_playing: bool
    playback_speed: float
    is_scrubbing: bool
    buffered_range_start: Optional[datetime]
    buffered_range_end: Optional[datetime]
