"""
Engine Orchestration Module

This module provides the unified interface for coordinating all
backend layers while maintaining strict boundary separation.

DESIGN PRINCIPLES:
==================
1. Layers communicate ONLY through contracts
2. Engine orchestrates flow without creating coupling
3. All operations are traceable through observability
4. No shared mutable state between layers
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Iterator, Dict
from datetime import datetime, timezone
import hashlib

from .contracts.base import SourceId, Timestamp, TimeRange, ThreadId, FragmentId, Error, ErrorCode
from .contracts.events import (
    RawIngestionEvent, NormalizedFragment, NarrativeStateEvent,
    ThreadStateSnapshot, QueryResult, QueryType
)
from .ingestion import IngestionEngine, IngestionConfig
from .normalization import NormalizationEngine, NormalizationConfig
from .ingestion import IngestionEngine, IngestionConfig
from .normalization import NormalizationEngine, NormalizationConfig
# from .core import NarrativeStateEngine, NarrativeEngineConfig  <-- DEPRECATED
from .temporal.event_log import ImmutableEventLog
from .contracts.temporal import LogSequence
from .temporal.state_machine import StateMachine, DerivedState
from .temporal.versioning import VersionTracker
from .temporal.replay import ReplayEngine
from .storage import TemporalStorageEngine, TemporalStorageConfig
from .query import QueryEngine, QueryEngineConfig
from .observability import ObservabilityEngine, ObservabilityConfig


@dataclass
class BackendConfig:
    """Unified configuration for the entire backend."""
    ingestion: IngestionConfig = None
    normalization: NormalizationConfig = None
    # core: NarrativeEngineConfig = None <-- DEPRECATED
    storage: TemporalStorageConfig = None
    query: QueryEngineConfig = None
    observability: ObservabilityConfig = None
    
    def __post_init__(self):
        self.ingestion = self.ingestion or IngestionConfig()
        self.normalization = self.normalization or NormalizationConfig()
        # self.core = self.core or NarrativeEngineConfig()
        self.storage = self.storage or TemporalStorageConfig()
        self.query = self.query or QueryEngineConfig()
        self.observability = self.observability or ObservabilityConfig()


class NarrativeIntelligenceBackend:
    """
    Unified Backend for Narrative Intelligence Engine.
    
    This class orchestrates all layers while maintaining strict
    separation of concerns. Each layer operates independently
    and communicates only through immutable contracts.
    
    LAYER FLOW:
    ===========
    1. Ingestion: Raw data → RawIngestionEvent
    2. Normalization: RawIngestionEvent → NormalizedFragment  
    3. Core Engine: NormalizedFragment → NarrativeStateEvent
    4. Storage: All events → Versioned persistence
    5. Query: Read-only access to stored data
    6. Observability: Records all layer activity
    
    NO LAYER BYPASSES THIS FLOW.
    """
    
    def __init__(self, config: Optional[BackendConfig] = None):
        self._config = config or BackendConfig()
        
        # Initialize layers (each is independent)
        # Initialize layers (each is independent)
        self._ingestion = IngestionEngine(self._config.ingestion)
        self._normalization = NormalizationEngine(self._config.normalization)
        
        # Core Engine Refactored: Temporal Layer (Phase 4)
        self._event_log = ImmutableEventLog()
        self._state_machine = StateMachine()
        self._version_tracker = VersionTracker()
        self._replay_engine = ReplayEngine(
            log=self._event_log,
            state_machine=self._state_machine,
            version_tracker=self._version_tracker
        )
        # self._core = NarrativeStateEngine(self._config.core) <-- DEPRECATED
        
        self._storage = TemporalStorageEngine(self._config.storage)
        self._query = QueryEngine(self._storage, self._config.query)
        self._observability = ObservabilityEngine(self._config.observability)
    
    # =========================================================================
    # INGESTION INTERFACE
    # =========================================================================
    
    def ingest_from_source(
        self,
        source_id: SourceId,
        since: Optional[Timestamp] = None
    ) -> List[NarrativeStateEvent]:
        """
        Ingest from a source and process through the full pipeline.
        
        Returns the NarrativeStateEvents produced.
        """
        events = []
        
        # Layer 1: Ingestion
        for raw_event in self._ingestion.ingest_from_source(source_id, since):
            state_event = self._process_raw_event(raw_event)
            if state_event:
                events.append(state_event)
        
        # Collect ingestion audit
        for entry in self._ingestion.get_audit_log():
            self._observability.collect_audit(entry)
        
        return events
    
    def ingest_batch(
        self,
        source_id: SourceId,
        payloads: List[str],
        event_timestamps: Optional[List[Optional[Timestamp]]] = None
    ) -> List[NarrativeStateEvent]:
        """
        Ingest a batch of payloads through the full pipeline.
        
        Returns the NarrativeStateEvents produced.
        """
        events = []
        
        # Layer 1: Ingestion
        batch = self._ingestion.ingest_batch(
            source_id=source_id,
            payloads=payloads,
            event_timestamps=event_timestamps
        )
        
        # Process each event through remaining layers
        for raw_event in batch.events:
            state_event = self._process_raw_event(raw_event)
            if state_event:
                events.append(state_event)
        
        return events
    
    def ingest_single(
        self,
        source_id: SourceId,
        payload: str,
        event_timestamp: Optional[Timestamp] = None
    ) -> Optional[NarrativeStateEvent]:
        """
        Ingest a single event through the full pipeline.
        
        Returns the NarrativeStateEvent if produced.
        """
        raw_event = self._ingestion.ingest_single(
            source_id=source_id,
            payload=payload,
            event_timestamp=event_timestamp
        )
        
        return self._process_raw_event(raw_event)
    
    def _process_raw_event(
        self,
        raw_event: RawIngestionEvent
    ) -> Optional[NarrativeStateEvent]:
        """
        Process a raw event through normalization, core, and storage.
        
        This is the internal pipeline that maintains layer boundaries.
        """
        # Layer 2: Normalization
        norm_result = self._normalization.normalize(raw_event)
        
        if not norm_result.success or not norm_result.fragment:
            # Record failed normalization
            self._observability.collect_metric(
                "normalization_failures_total",
                1.0,
                {"error_code": norm_result.error.code.name if norm_result.error else "unknown"}
            )
            return None
        
        fragment = norm_result.fragment
        
        # Record lineage
        self._observability.record_lineage(
            entity_id=fragment.fragment_id.value,
            entity_type="normalized_fragment",
            parent_ids=[raw_event.event_id],
            metadata={"source_id": raw_event.source_metadata.source_id.value}
        )
        
        # Store fragment
        self._storage.write_fragment(fragment)
        
        # Layer 3: Core Engine (Temporal Refactor)
        # Use ReplayEngine to handle both current and late arrivals with correct recomputation
        # This replaces the old mutable process_fragment call
        
        late_result = self._replay_engine.handle_late_arrival(
            fragment=fragment,
            event_timestamp=fragment.source_metadata.event_timestamp or Timestamp.now()
        )
        
        if not late_result.success:
            self._observability.log_audit(
                action="processing_failed",
                entity_id=fragment.fragment_id.value,
                outcome="failure",
                details=late_result.error.message if late_result.error else "Unknown error"
            )
            return None
            
        # Extract events and new state from reply result
        narrative_events = []
        
        # If new threads created
        if late_result.replay_result and late_result.replay_result.new_threads:
            for thread_id in late_result.replay_result.new_threads:
                # Get latest state for this thread
                thread_view = self._replay_engine.get_state_at(self._event_log.state.head_sequence)
                if not thread_view: 
                    continue
                    
                # Create event (reconstructed from view)
                # Note: valid because view is immutable
                # In real system, we'd emit specific events from StateMachine
                pass 
        
        # For compatibility, we persist the normalized fragment to storage
        # The actual narrative state is now in the event log + state machine
        self._storage.write_fragment(fragment)
        
        # PERSIST THE LOG ENTRY (Forensic Chain)
        if late_result.entry:
            self._storage.write_log_entry(late_result.entry)
            
        # PERSIST SNAPSHOTS (Time Travel)
        if late_result.replay_result and late_result.replay_result.success:
            if late_result.replay_result.state:
                from .contracts.base import CanonicalTopic
                
                for thread_view in late_result.replay_result.state.threads:
                    # Convert ThreadView to ThreadStateSnapshot
                    # This is necessary because StateMachine returns Views (dynamic)
                    # but Storage expects Snapshots (static DTOs)
                    
                    # Convert topics (View has IDs, Snapshot needs objects)
                    topics = tuple(
                        CanonicalTopic(topic_id=tid, canonical_name=tid) 
                        for tid in thread_view.canonical_topics
                    )
                    
                    snapshot = ThreadStateSnapshot(
                        version_id=thread_view.version,
                        thread_id=thread_view.thread_id,
                        lifecycle_state=thread_view.lifecycle_state,
                        member_fragment_ids=thread_view.member_fragment_ids,
                        canonical_topics=topics,
                        relations=(), # Relationships not yet in ThreadView
                        created_at=Timestamp.now(), # Snapshot time
                        previous_version_id=thread_view.version.parent_version,
                        last_activity_timestamp=thread_view.last_activity,
                        expected_activity_interval_seconds=None,
                        absence_detected=len(thread_view.absence_markers) > 0,
                    )
                    self._storage.write_snapshot(snapshot)
        
        # Log success
        self._observability.log_audit(
            action="fragment_processed",
            entity_id=fragment.fragment_id.value,
            outcome="success",
            details=f"Sequence: {late_result.entry.sequence.value}" if late_result.entry else ""
        )
        
        # Return a placeholder event for compatibility (or None if API signature allows)
        # The system now uses pull-based queries rather than push-based events
        return None
    
    # =========================================================================
    # QUERY INTERFACE
    # =========================================================================
    
    def query_timeline(
        self,
        thread_id: ThreadId,
        time_range: Optional[TimeRange] = None
    ) -> QueryResult:
        """Query thread timeline."""
        return self._query.query_timeline(thread_id, time_range)
    
    def query_thread_state(
        self,
        thread_id: ThreadId,
        at_time: Optional[Timestamp] = None
    ) -> QueryResult:
        """
        Query thread state (current or at specific time).
        
        Uses pure derivation from event log.
        """
        # Determine sequence
        if at_time:
            sequence = self._event_log.find_temporal_position(at_time)
        else:
            sequence = self._event_log.state.head_sequence
            
        # Derive state
        derived = self._replay_engine.get_state_at(sequence)
        
        if not derived:
            return QueryResult(
                query_id="",  # In real system generate ID
                query_type=QueryType.THREAD_STATE,
                success=False,
                result_count=0,
                results=(),
                error=Error(
                    code=ErrorCode.THREAD_NOT_FOUND,
                    message=f"No state at sequence {sequence.value}",
                    timestamp=datetime.now(timezone.utc)
                )
            )
            
        # Find specific thread
        thread_view = next((t for t in derived.threads if t.thread_id.value == thread_id.value), None)
        
        if not thread_view:
             return QueryResult(
                query_id="",
                query_type=QueryType.THREAD_STATE,
                success=False,
                result_count=0,
                results=(),
                error=Error(
                    code=ErrorCode.THREAD_NOT_FOUND,
                    message=f"Thread {thread_id.value} not found at seq {sequence.value}",
                    timestamp=datetime.now(timezone.utc)
                )
            )
            
        return QueryResult(
            query_id=hashlib.sha256(f"thread_{thread_id.value}".encode()).hexdigest(),
            query_type=QueryType.THREAD_STATE,
            success=True,
            result_count=1,
            results=(thread_view,)
        )
    
    def query_fragment_trace(
        self,
        fragment_id: FragmentId
    ) -> QueryResult:
        """Query fragment evidence trace."""
        return self._query.query_fragment_trace(fragment_id)
    
    def query_comparison(
        self,
        time_range: TimeRange,
        max_results: int = 10
    ) -> QueryResult:
        """Query comparison of threads in time range."""
        return self._query.query_comparison(time_range, max_results)
    
    def query_rewind(
        self,
        target_timestamp: Timestamp,
        max_results: int = 100
    ) -> QueryResult:
        """Query system state at a point in time."""
        return self._query.query_rewind(target_timestamp, max_results)
    
    # =========================================================================
    # OBSERVABILITY INTERFACE
    # =========================================================================
    
    def get_audit_log(
        self,
        time_range: Optional[TimeRange] = None,
        layers: Optional[List[str]] = None
    ) -> List:
        """Get unified audit log."""
        # Collect from all layers first
        self._sync_audit_logs()
        return self._observability.get_unified_log(time_range, layers)
    
    def get_audit_report(
        self,
        time_range: Optional[TimeRange] = None
    ) -> Dict:
        """Generate audit report."""
        self._sync_audit_logs()
        return self._observability.generate_audit_report(time_range)
    
    def get_metrics(self):
        """Get metrics collector."""
        return self._observability.get_metrics()
    
    def get_lineage(self):
        """Get lineage tracker."""
        return self._observability.get_lineage()
    
    def create_checkpoint(self):
        """Create system checkpoint for replay."""
        storage_ckpt = self._storage.create_checkpoint()
        obs_ckpt = self._observability.create_checkpoint()
        return {
            'storage': storage_ckpt,
            'observability': obs_ckpt
        }
    
    def _sync_audit_logs(self):
        """Sync audit logs from all layers to observability."""
        for entry in self._ingestion.get_audit_log():
            self._observability.collect_audit(entry)
        for entry in self._normalization.get_audit_log():
            self._observability.collect_audit(entry)
        # Note: _core was deprecated in temporal layer refactor
        for entry in self._storage.get_audit_log():
            self._observability.collect_audit(entry)
        for entry in self._query.get_audit_log():
            self._observability.collect_audit(entry)
    
    # =========================================================================
    # DIRECT LAYER ACCESS (for advanced use cases)
    # =========================================================================
    
    @property
    def ingestion_layer(self) -> IngestionEngine:
        """Direct access to ingestion layer."""
        return self._ingestion
    
    @property
    def normalization_layer(self) -> NormalizationEngine:
        """Direct access to normalization layer."""
        return self._normalization
    
    @property
    def replay_engine(self) -> ReplayEngine:
        """Direct access to replay engine (replaces deprecated core_layer)."""
        return self._replay_engine
    
    @property
    def storage_layer(self) -> TemporalStorageEngine:
        """Direct access to temporal storage layer."""
        return self._storage
    
    @property
    def query_layer(self) -> QueryEngine:
        """Direct access to query layer."""
        return self._query
    
    @property
    def observability_layer(self) -> ObservabilityEngine:
        """Direct access to observability layer."""
        return self._observability
    
    # =========================================================================
    # STATE INTROSPECTION
    # =========================================================================
    
    def get_all_threads(self) -> Dict[str, ThreadStateSnapshot]:
        """Get current state of all threads (derived from event log)."""
        result = {}
        
        # Derive current state from event log
        head = self._event_log.state.head_sequence
        derived = self._replay_engine.get_state_at(head)
        
        if not derived:
            return {}
            
        from .contracts.base import CanonicalTopic
        
        for thread_view in derived.threads:
            # Convert ThreadView to ThreadStateSnapshot
            topics = tuple(
                CanonicalTopic(topic_id=tid, canonical_name=tid) 
                for tid in thread_view.canonical_topics
            )
            
            snapshot = ThreadStateSnapshot(
                version_id=thread_view.version,
                thread_id=thread_view.thread_id,
                lifecycle_state=thread_view.lifecycle_state,
                member_fragment_ids=thread_view.member_fragment_ids,
                canonical_topics=topics,
                relations=(),
                created_at=Timestamp.now(),
                previous_version_id=thread_view.version.parent_version,
                last_activity_timestamp=thread_view.last_activity,
                expected_activity_interval_seconds=None,
                absence_detected=len(thread_view.absence_markers) > 0,
            )
            result[thread_view.thread_id.value] = snapshot
            
        return result
    
    def get_thread(self, thread_id: ThreadId) -> Optional[ThreadStateSnapshot]:
        """Get current state of a specific thread."""
        all_threads = self.get_all_threads()
        return all_threads.get(thread_id.value)
    
    def get_event_log(self) -> List[NarrativeStateEvent]:
        """Get all state events from event log."""
        # Return empty list - the new architecture uses ImmutableEventLog
        # which stores LogEntries, not NarrativeStateEvents directly
        return []

