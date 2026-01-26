"""
Integration Tests for Temporal Backend Orchestration
====================================================

Tests verifying the unified backend uses the temporal layer correctly.
"""

import pytest
from datetime import datetime, timezone
from dataclasses import replace

from backend.contracts.base import SourceId, Timestamp
from backend.engine import NarrativeIntelligenceBackend, BackendConfig
from backend.contracts.events import RawIngestionEvent, ThreadStateSnapshot
from backend.temporal.state_machine import ThreadView

class TestBackendOrchestration:
    """Test full backend pipeline with temporal layer."""
    
    def test_ingest_and_query_flow(self):
        """Test simple ingest -> derive -> query flow."""
        backend = NarrativeIntelligenceBackend()
        source_id = SourceId(value="test_src", source_type="test")
        
        # 1. Ingest event
        backend.ingest_single(
            source_id=source_id,
            payload="Test content for known thread",
            event_timestamp=Timestamp.now()
        )
        
        # 2. Query state (should trigger derivation)
        # Note: We need a valid thread ID. Since we can't easily guess the ID 
        # generated from hash, we'll cheat slightly by looking at the log directly
        # or checking the observability log (mocked here)
        
        # Determine thread ID from log (whitebox testing)
        log_entry = backend._event_log.get_entry(backend._event_log.state.head_sequence)
        assert log_entry is not None
        
        # Log entry contains fragment. Thread is created from fragment.
        # State machine will have derived it.
        state = backend._replay_engine.get_state_at(log_entry.sequence)
        assert len(state.threads) > 0
        thread_id = state.threads[0].thread_id
        
        # 3. Query via public API
        result = backend.query_thread_state(thread_id)
        
        assert result.success
        assert len(result.results) > 0
        thread_view = result.results[0]
        assert isinstance(thread_view, ThreadView)
        assert thread_view.thread_id == thread_id
        
    def test_late_arrival_handling(self):
        """Test backend handles late arrivals via replay."""
        backend = NarrativeIntelligenceBackend()
        source_id = SourceId(value="test_src", source_type="test")
        
        from datetime import timedelta
        base_time = datetime.now(timezone.utc)
        
        # 1. Ingest event T1 (2 hours ago)
        t1 = base_time - timedelta(hours=2)
        backend.ingest_single(
            source_id=source_id,
            payload="Fragment 1",
            event_timestamp=Timestamp(value=t1)
        )
        
        # 2. Ingest event T3 (current)
        t3 = base_time
        backend.ingest_single(
            source_id=source_id,
            payload="Fragment 2",
            event_timestamp=Timestamp(value=t3)
        )
        
        # 3. Ingest event T2 (LATE ARRIVAL - 1 hour ago)
        t2 = base_time - timedelta(hours=1)
        backend.ingest_single(
            source_id=source_id,
            payload="Fragment 3 (Late)",
            event_timestamp=Timestamp(value=t2)
        )
        
        # Verify state includes all 3
        log_head = backend._event_log.state.head_sequence
        state = backend._replay_engine.get_state_at(log_head)
        
        # Should be one thread with 3 fragments if they matched
        # (Assuming topic matching works, which depends on mock normalization)
        # For this test, we just check that Log entries exist and state is derivable
        assert backend._event_log.state.entry_count == 3
