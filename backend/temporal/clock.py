"""
Logical Clock for Deterministic Replay
======================================

Injectable clock that enables deterministic execution and replay.

GUARANTEES:
- Same inputs + same clock sequence = byte-identical outputs
- Never reads system time implicitly in replay mode
- All clock ticks are logged for perfect replay
"""

from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional
from pathlib import Path
import json


class ClockExhausted(Exception):
    """Raised when replay clock runs out of ticks."""
    pass


@dataclass
class LogicalClock:
    """
    Injectable clock for deterministic execution.
    
    MODES:
    ======
    1. LIVE mode: Uses real system time, logs all ticks
    2. REPLAY mode: Uses pre-recorded tick sequence
    
    GUARANTEES:
    ===========
    - Given same tick sequence, produces identical results
    - All time reads go through this clock
    - Tick log enables perfect replay
    """
    _ticks: List[datetime] = field(default_factory=list)
    _current_index: int = 0
    _is_live: bool = True
    _start_time: Optional[datetime] = None
    
    def now(self) -> datetime:
        """
        Get current logical time.
        
        In LIVE mode: reads system time and logs it
        In REPLAY mode: returns next tick from recorded sequence
        """
        if self._is_live:
            current = datetime.now(timezone.utc)
            self._ticks.append(current)
            self._current_index = len(self._ticks)
            return current
        else:
            if self._current_index >= len(self._ticks):
                raise ClockExhausted(
                    f"Replay clock exhausted at index {self._current_index}. "
                    f"Original execution had {len(self._ticks)} ticks."
                )
            tick = self._ticks[self._current_index]
            self._current_index += 1
            return tick
    
    def tick_count(self) -> int:
        """Number of ticks recorded/consumed."""
        return self._current_index
    
    def is_live(self) -> bool:
        """Whether clock is in live mode."""
        return self._is_live
    
    def get_start_time(self) -> Optional[datetime]:
        """Get the start time of this clock session."""
        if self._ticks:
            return self._ticks[0]
        return self._start_time
    
    @classmethod
    def live(cls) -> 'LogicalClock':
        """Create clock in LIVE mode (uses system time)."""
        clock = cls(_is_live=True)
        clock._start_time = datetime.now(timezone.utc)
        return clock
    
    @classmethod
    def from_log(cls, tick_log_path: Path) -> 'LogicalClock':
        """
        Create clock in REPLAY mode from recorded log.
        
        Args:
            tick_log_path: Path to JSON file containing tick sequence
            
        Returns:
            LogicalClock configured for replay
        """
        with open(tick_log_path, 'r') as f:
            data = json.load(f)
        
        ticks = [
            datetime.fromisoformat(t) for t in data['ticks']
        ]
        
        clock = cls(
            _ticks=ticks,
            _current_index=0,
            _is_live=False
        )
        if ticks:
            clock._start_time = ticks[0]
        
        return clock
    
    def save_log(self, tick_log_path: Path) -> None:
        """
        Save tick log for future replay.
        
        Args:
            tick_log_path: Path to write JSON tick sequence
        """
        tick_log_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = {
            'version': '1.0',
            'mode': 'live' if self._is_live else 'replay',
            'tick_count': len(self._ticks),
            'start_time': self._ticks[0].isoformat() if self._ticks else None,
            'end_time': self._ticks[-1].isoformat() if self._ticks else None,
            'ticks': [t.isoformat() for t in self._ticks]
        }
        
        with open(tick_log_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def __repr__(self) -> str:
        mode = "LIVE" if self._is_live else "REPLAY"
        return f"LogicalClock({mode}, ticks={len(self._ticks)}, index={self._current_index})"


@dataclass(frozen=True)
class ClockSnapshot:
    """Immutable snapshot of clock state at a point in time."""
    timestamp: datetime
    tick_index: int
    is_live: bool
    
    def to_dict(self) -> dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'tick_index': self.tick_index,
            'is_live': self.is_live
        }
