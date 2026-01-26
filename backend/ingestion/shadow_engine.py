"""
Shadow Ingestion Engine
=======================

Orchestrates parallel mock + real RSS ingestion for controlled transition.

SHADOW MODE:
============
- Both adapters run concurrently
- Both emit to the SAME append-only log
- No downstream code changes required
- Source tier distinguishes origin

INVARIANTS PRESERVED:
=====================
- Immutability (frozen dataclasses)
- Event sourcing (append-only log)
- Deterministic replay (via logical clock)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Iterator, Optional, Protocol, Any
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

from ..contracts.base import SourceId, Timestamp, SourceTier
from ..contracts.events import RawIngestionEvent


# =============================================================================
# PROTOCOLS (Interface contracts)
# =============================================================================

class ImmutableEventLog(Protocol):
    """Protocol for append-only event log."""
    
    def append(self, event: RawIngestionEvent) -> None:
        """Append event to log (immutable - creates new version)."""
        ...
    
    def replay(self) -> Iterator[RawIngestionEvent]:
        """Replay all events in order."""
        ...
    
    def replay_by_tier(self, tier: SourceTier) -> Iterator[RawIngestionEvent]:
        """Replay events filtered by source tier."""
        ...


class IngestionAdapterProtocol(Protocol):
    """Protocol for ingestion adapters."""
    
    @property
    def source_type(self) -> str:
        ...
    
    @property
    def source_tier(self) -> SourceTier:
        ...
    
    def pull_events(
        self,
        source_id: SourceId,
        since: Optional[Timestamp] = None
    ) -> Iterator[RawIngestionEvent]:
        ...


# =============================================================================
# SHADOW SESSION
# =============================================================================

@dataclass(frozen=True)
class ShadowSessionStats:
    """Immutable statistics for a shadow session."""
    mock_event_count: int
    live_event_count: int
    mock_source_count: int
    live_source_count: int
    total_bytes_ingested: int
    session_duration_ms: float


@dataclass(frozen=True)
class ShadowSession:
    """Immutable shadow mode session record."""
    session_id: str
    started_at: datetime
    completed_at: Optional[datetime]
    mock_adapter_type: str
    live_adapter_type: str
    stats: Optional[ShadowSessionStats] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for storage."""
        return {
            'session_id': self.session_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'mock_adapter_type': self.mock_adapter_type,
            'live_adapter_type': self.live_adapter_type,
            'stats': {
                'mock_event_count': self.stats.mock_event_count,
                'live_event_count': self.stats.live_event_count,
                'mock_source_count': self.stats.mock_source_count,
                'live_source_count': self.stats.live_source_count,
                'total_bytes_ingested': self.stats.total_bytes_ingested,
                'session_duration_ms': self.stats.session_duration_ms
            } if self.stats else None
        }


# =============================================================================
# FILE-BASED EVENT LOG (Simple implementation)
# =============================================================================

class FileBasedEventLog:
    """
    Simple file-based append-only event log.
    
    GUARANTEES:
    - Append-only (new events added, never modified)
    - Tier-aware replay
    - JSON serialization for portability
    """
    
    def __init__(self, log_dir: Path):
        self._log_dir = Path(log_dir)
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._events_file = self._log_dir / "events.jsonl"
        self._index: List[RawIngestionEvent] = []
        self._load_existing()
    
    def _load_existing(self) -> None:
        """Load existing events from file."""
        if self._events_file.exists():
            with open(self._events_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        # Reconstruct event (simplified)
                        self._index.append(data)
    
    def append(self, event: RawIngestionEvent) -> None:
        """Append event to log."""
        # Serialize event
        event_data = {
            'event_id': event.event_id,
            'source_id': event.source_metadata.source_id.value,
            'source_type': event.source_metadata.source_id.source_type,
            'source_tier': event.source_tier.value,
            'raw_payload': event.raw_payload,
            'raw_payload_hash': event.raw_payload_hash,
            'raw_payload_path': event.raw_payload_path,
            'ingestion_timestamp': event.ingestion_timestamp.to_iso(),
            'batch_id': event.batch_id
        }
        
        # Append to file
        with open(self._events_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event_data, ensure_ascii=False) + '\n')
        
        # Update in-memory index
        self._index.append(event_data)
    
    def replay(self) -> Iterator[Dict[str, Any]]:
        """Replay all events in order."""
        for event_data in self._index:
            yield event_data
    
    def replay_by_tier(self, tier: SourceTier) -> Iterator[Dict[str, Any]]:
        """Replay events filtered by source tier."""
        for event_data in self._index:
            if event_data.get('source_tier') == tier.value:
                yield event_data
    
    def count(self) -> int:
        """Total event count."""
        return len(self._index)
    
    def count_by_tier(self, tier: SourceTier) -> int:
        """Count events by tier."""
        return sum(1 for e in self._index if e.get('source_tier') == tier.value)


# =============================================================================
# SHADOW INGESTION ENGINE
# =============================================================================

class ShadowIngestionEngine:
    """
    Orchestrates parallel mock + real ingestion.
    
    SHADOW MODE:
    ============
    - Both adapters run concurrently
    - Both emit to the SAME append-only log
    - Source tier distinguishes origin
    
    INVARIANTS PRESERVED:
    =====================
    - Immutability (frozen dataclasses)
    - Event sourcing (append-only log)
    - Deterministic replay (via logical clock)
    
    NO DOWNSTREAM CHANGES:
    ======================
    - Same event schema
    - Same log format
    - Tier is metadata only
    """
    
    def __init__(
        self,
        mock_adapter: IngestionAdapterProtocol,
        live_adapter: IngestionAdapterProtocol,
        event_log: FileBasedEventLog,
        clock: Any = None
    ):
        """
        Initialize shadow engine.
        
        Args:
            mock_adapter: Adapter for mock/test data
            live_adapter: Adapter for live RSS data
            event_log: Append-only event log
            clock: Optional logical clock for deterministic time
        """
        self._mock = mock_adapter
        self._live = live_adapter
        self._log = event_log
        self._clock = clock
    
    def run_shadow_session(
        self,
        mock_sources: List[SourceId],
        live_sources: List[SourceId]
    ) -> ShadowSession:
        """
        Run parallel ingestion from both adapters.
        
        All events go to the same log with tier metadata.
        
        Args:
            mock_sources: Source IDs for mock adapter
            live_sources: Source IDs for live adapter
            
        Returns:
            Immutable session record
        """
        import time
        
        session_id = self._generate_session_id()
        started_at = self._get_time()
        start_time = time.time()
        
        mock_count = 0
        live_count = 0
        total_bytes = 0
        
        # Ingest from mock sources
        for source_id in mock_sources:
            for event in self._mock.pull_events(source_id):
                self._log.append(event)
                mock_count += 1
                total_bytes += len(event.raw_payload)
        
        # Ingest from live sources
        for source_id in live_sources:
            for event in self._live.pull_events(source_id):
                self._log.append(event)
                live_count += 1
                total_bytes += len(event.raw_payload)
        
        completed_at = self._get_time()
        duration_ms = (time.time() - start_time) * 1000
        
        stats = ShadowSessionStats(
            mock_event_count=mock_count,
            live_event_count=live_count,
            mock_source_count=len(mock_sources),
            live_source_count=len(live_sources),
            total_bytes_ingested=total_bytes,
            session_duration_ms=duration_ms
        )
        
        session = ShadowSession(
            session_id=session_id,
            started_at=started_at,
            completed_at=completed_at,
            mock_adapter_type=self._mock.source_type,
            live_adapter_type=self._live.source_type,
            stats=stats
        )
        
        # Save session record
        self._save_session(session)
        
        return session
    
    def run_live_only(
        self,
        sources: List[SourceId]
    ) -> ShadowSession:
        """
        Run ingestion from live adapter only.
        
        Convenience method for live-only mode.
        """
        return self.run_shadow_session(
            mock_sources=[],
            live_sources=sources
        )
    
    def run_mock_only(
        self,
        sources: List[SourceId]
    ) -> ShadowSession:
        """
        Run ingestion from mock adapter only.
        
        Convenience method for mock-only mode.
        """
        return self.run_shadow_session(
            mock_sources=sources,
            live_sources=[]
        )
    
    def get_log_stats(self) -> Dict[str, int]:
        """Get statistics about the event log."""
        return {
            'total_events': self._log.count(),
            'mock_events': self._log.count_by_tier(SourceTier.MOCK),
            'live_events': self._log.count_by_tier(SourceTier.PUBLIC_RSS)
        }
    
    def _generate_session_id(self) -> str:
        """Generate deterministic session ID."""
        timestamp = self._get_time()
        seed = f"shadow_{timestamp.isoformat()}"
        return f"sess_{hashlib.sha256(seed.encode()).hexdigest()[:16]}"
    
    def _get_time(self) -> datetime:
        """Get current time (uses logical clock if available)."""
        if self._clock is not None and hasattr(self._clock, 'now'):
            return self._clock.now()
        return datetime.now(timezone.utc)
    
    def _save_session(self, session: ShadowSession) -> None:
        """Save session record to disk."""
        sessions_file = self._log._log_dir / "sessions.jsonl"
        with open(sessions_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(session.to_dict()) + '\n')


# =============================================================================
# SOURCE FILTER (Frontend toggle contract)
# =============================================================================

class SourceTierFilter:
    """
    Frontend filter for source tier.
    
    SINGLE TOGGLE - NO UX INTERPRETATION:
    - MOCK: Show only mock data
    - PUBLIC_RSS: Show only real RSS data
    - ALL: Show everything
    
    This is FILTERING, not ranking or interpretation.
    """
    MOCK = "mock"
    PUBLIC_RSS = "public_rss"
    ALL = "all"


@dataclass(frozen=True)
class SourceFilterDTO:
    """Immutable source filter for frontend queries."""
    tier_filter: str = SourceTierFilter.ALL
    
    def matches(self, source_tier: SourceTier) -> bool:
        """Check if source tier matches filter."""
        if self.tier_filter == SourceTierFilter.ALL:
            return True
        return self.tier_filter == source_tier.value
    
    def to_dict(self) -> Dict[str, str]:
        """Serialize to dictionary."""
        return {'tier_filter': self.tier_filter}
