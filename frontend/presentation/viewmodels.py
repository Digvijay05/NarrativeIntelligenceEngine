"""
Presentation Contracts

Responsibility:
Define ViewModel contracts for pure UI components.
Strictly decoupled from business logic or valid data.
"""

from dataclasses import dataclass
from typing import List, Optional
from frontend.state import AvailabilityState

@dataclass(frozen=True)
class ThreadCardViewModel:
    """ViewModel for a Thread Card component."""
    thread_id: str
    title: str
    subtitle: Optional[str]
    status_color: str    # e.g., "red-500"
    status_label: str    # e.g., "Active"
    fragment_count: int
    is_selected: bool
    is_loading: bool

@dataclass(frozen=True)
class LoadingStateViewModel:
    """Unified loading state."""
    message: str
    progress: Optional[float]
    is_blocking: bool
