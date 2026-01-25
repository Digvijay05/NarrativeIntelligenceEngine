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
import hashlib

from .contracts.base import SourceId, Timestamp, TimeRange, ThreadId, FragmentId
from .contracts.events import (
    RawIngestionEvent, NormalizedFragment, NarrativeStateEvent,
    ThreadStateSnapshot, QueryResult, QueryType
)
from .ingestion import IngestionEngine, IngestionConfig
from .normalization import NormalizationEngine, NormalizationConfig
from .core import NarrativeStateEngine, NarrativeEngineConfig
from .storage import TemporalStorageEngine, TemporalStorageConfig
from .query import QueryEngine, QueryEngineConfig
from .observability import ObservabilityEngine, ObservabilityConfig


@dataclass
class BackendConfig:
    """Unified configuration for the entire backend."""
    ingestion: IngestionConfig = None
    normalization: NormalizationConfig = None
    core: NarrativeEngineConfig = None
    storage: TemporalStorageConfig = None
    query: QueryEngineConfig = None
    observability: ObservabilityConfig = None
    
    def __post_init__(self):
        self.ingestion = self.ingestion or IngestionConfig()
        self.normalization = self.normalization or NormalizationConfig()
        self.core = self.core or NarrativeEngineConfig()
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
        self._ingestion = IngestionEngine(self._config.ingestion)
        self._normalization = NormalizationEngine(self._config.normalization)
        self._core = NarrativeStateEngine(self._config.core)
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
        self._storage.store_fragment(fragment)
        
        # Layer 3: Core Engine
        outcome = self._core.process_fragment(fragment)
        
        if not outcome.state_event:
            return None
        
        state_event = outcome.state_event
        
        # Record lineage
        self._observability.record_lineage(
            entity_id=state_event.event_id,
            entity_type="state_event",
            parent_ids=[fragment.fragment_id.value],
            metadata={"thread_id": state_event.thread_id.value}
        )
        
        # Layer 4: Storage
        self._storage.store_event(state_event)
        
        # Collect metrics
        self._observability.collect_metric(
            "normalization_duration_ms",
            norm_result.processing_time_ms
        )
        self._observability.collect_metric(
            "fragments_processed_total",
            1.0,
            {"outcome": outcome.result.value}
        )
        
        return state_event
    
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
        """Query thread state (current or at specific time)."""
        return self._query.query_thread_state(thread_id, at_time)
    
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
        for entry in self._core.get_audit_log():
            self._observability.collect_audit(entry)
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
    def core_layer(self) -> NarrativeStateEngine:
        """Direct access to core narrative state engine."""
        return self._core
    
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
        """Get current state of all threads."""
        return self._core.get_all_current_snapshots()
    
    def get_thread(self, thread_id: ThreadId) -> Optional[ThreadStateSnapshot]:
        """Get current state of a specific thread."""
        return self._core.get_current_snapshot(thread_id)
    
    def get_event_log(self) -> List[NarrativeStateEvent]:
        """Get all state events from core engine."""
        return self._core.get_event_log()
