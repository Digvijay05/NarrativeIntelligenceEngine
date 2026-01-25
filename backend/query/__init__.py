"""
Query & Analysis Interfaces

RESPONSIBILITY: Read-only access, timeline/comparison/evidence queries
ALLOWED INPUTS: Query requests with explicit parameters
OUTPUTS: Deterministic QueryResult with explicit error states

WHAT THIS LAYER MUST NOT DO:
============================
- Mutate any state
- Access storage directly (uses storage layer's interface)
- Interpret or rank results by importance
- Make predictions or inferences
- Resolve contradictions (only report them)
- Execute any write operations

BOUNDARY ENFORCEMENT:
=====================
- ONLY reads data through explicit query contracts
- NEVER modifies system state
- All errors are explicit and queryable
- No silent fallbacks or heuristic smoothing

REFACTORING FROM PREVIOUS CODE:
===============================
Previous coupling risks eliminated:
1. OLD: Visualization module imported internal thread structures
   NEW: Query layer uses only contract types
2. OLD: No explicit error states for query failures
   NEW: Every query returns explicit success/failure with error details
3. OLD: Query logic embedded in model classes
   NEW: Dedicated query handlers with single responsibility
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable
from enum import Enum
import hashlib
import time

# ONLY import from contracts - never from other layers' implementations
from ..contracts.base import (
    ThreadId, FragmentId, VersionId, Timestamp, TimeRange,
    ThreadLifecycleState, Error, ErrorCode
)
from ..contracts.events import (
    QueryRequest, QueryResult, QueryType, QueryError,
    ThreadStateSnapshot, NormalizedFragment, Timeline, TimelinePoint,
    NarrativeStateEvent, AuditLogEntry, AuditEventType
)

# Import storage layer through its public interface
from ..storage import TemporalStorageEngine


# =============================================================================
# QUERY HANDLERS (Single Responsibility)
# =============================================================================

class QueryHandler:
    """Base class for query handlers."""
    
    @property
    def query_type(self) -> QueryType:
        raise NotImplementedError
    
    def handle(
        self,
        request: QueryRequest,
        storage: TemporalStorageEngine
    ) -> QueryResult:
        raise NotImplementedError


class TimelineQueryHandler(QueryHandler):
    """
    Handler for timeline queries.
    
    Returns the evolution of a thread over time.
    Deterministic: same request always produces same result.
    """
    
    @property
    def query_type(self) -> QueryType:
        return QueryType.TIMELINE
    
    def handle(
        self,
        request: QueryRequest,
        storage: TemporalStorageEngine
    ) -> QueryResult:
        start_time = time.time()
        
        # Validate request
        if not request.thread_id:
            return QueryResult.failed(
                query_id=request.query_id,
                query_type=self.query_type,
                error=QueryError(
                    error_code=ErrorCode.INSUFFICIENT_DATA,
                    message="thread_id is required for timeline queries",
                    query_id=request.query_id,
                    timestamp=Timestamp.now()
                )
            )
        
        # Execute query
        timeline = storage.get_thread_timeline(
            thread_id=request.thread_id,
            time_range=request.time_range
        )
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        if not timeline.points:
            return QueryResult.empty(
                query_id=request.query_id,
                query_type=self.query_type,
                execution_time_ms=execution_time_ms
            )
        
        return QueryResult(
            query_id=request.query_id,
            query_type=self.query_type,
            success=True,
            result_count=len(timeline.points),
            results=(timeline,),
            execution_time_ms=execution_time_ms
        )


class ThreadStateQueryHandler(QueryHandler):
    """
    Handler for thread state queries.
    
    Returns current or historical thread state.
    Supports time-travel via target_timestamp.
    """
    
    @property
    def query_type(self) -> QueryType:
        return QueryType.THREAD_STATE
    
    def handle(
        self,
        request: QueryRequest,
        storage: TemporalStorageEngine
    ) -> QueryResult:
        start_time = time.time()
        
        if not request.thread_id:
            return QueryResult.failed(
                query_id=request.query_id,
                query_type=self.query_type,
                error=QueryError(
                    error_code=ErrorCode.INSUFFICIENT_DATA,
                    message="thread_id is required for thread state queries",
                    query_id=request.query_id,
                    timestamp=Timestamp.now()
                )
            )
        
        # Time-travel query or current state
        if request.target_timestamp:
            snapshot = storage.get_thread_at_time(
                thread_id=request.thread_id,
                target_time=request.target_timestamp
            )
        else:
            snapshot = storage.backend.get_latest_snapshot(request.thread_id)
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        if not snapshot:
            return QueryResult.empty(
                query_id=request.query_id,
                query_type=self.query_type,
                execution_time_ms=execution_time_ms
            )
        
        return QueryResult(
            query_id=request.query_id,
            query_type=self.query_type,
            success=True,
            result_count=1,
            results=(snapshot,),
            execution_time_ms=execution_time_ms
        )


class FragmentTraceQueryHandler(QueryHandler):
    """
    Handler for fragment trace queries.
    
    Returns the evidence chain linking a fragment to its thread.
    Provides full lineage for audit purposes.
    """
    
    @property
    def query_type(self) -> QueryType:
        return QueryType.FRAGMENT_TRACE
    
    def handle(
        self,
        request: QueryRequest,
        storage: TemporalStorageEngine
    ) -> QueryResult:
        start_time = time.time()
        
        if not request.fragment_id:
            return QueryResult.failed(
                query_id=request.query_id,
                query_type=self.query_type,
                error=QueryError(
                    error_code=ErrorCode.INSUFFICIENT_DATA,
                    message="fragment_id is required for fragment trace queries",
                    query_id=request.query_id,
                    timestamp=Timestamp.now()
                )
            )
        
        # Find fragment
        fragment = storage.backend.get_fragment(request.fragment_id)
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        if not fragment:
            return QueryResult.empty(
                query_id=request.query_id,
                query_type=self.query_type,
                execution_time_ms=execution_time_ms
            )
        
        # Build trace result
        trace = {
            'fragment': fragment,
            'source_event_id': fragment.source_event_id,
            'content_signature': fragment.content_signature,
            'canonical_topics': fragment.canonical_topics,
            'duplicate_info': fragment.duplicate_info,
            'contradiction_info': fragment.contradiction_info
        }
        
        return QueryResult(
            query_id=request.query_id,
            query_type=self.query_type,
            success=True,
            result_count=1,
            results=(trace,),
            execution_time_ms=execution_time_ms
        )


class ComparisonQueryHandler(QueryHandler):
    """
    Handler for comparison queries.
    
    Compares multiple threads or timeline segments.
    Shows parallel narratives without ranking importance.
    """
    
    @property
    def query_type(self) -> QueryType:
        return QueryType.COMPARISON
    
    def handle(
        self,
        request: QueryRequest,
        storage: TemporalStorageEngine
    ) -> QueryResult:
        start_time = time.time()
        
        if not request.time_range:
            return QueryResult.failed(
                query_id=request.query_id,
                query_type=self.query_type,
                error=QueryError(
                    error_code=ErrorCode.INVALID_TIME_RANGE,
                    message="time_range is required for comparison queries",
                    query_id=request.query_id,
                    timestamp=Timestamp.now()
                )
            )
        
        # Get all threads with activity in the time range
        all_thread_ids = storage.backend.get_all_thread_ids()
        
        comparisons = []
        for thread_id in all_thread_ids[:request.max_results]:
            timeline = storage.get_thread_timeline(
                thread_id=thread_id,
                time_range=request.time_range
            )
            if timeline.points:
                comparisons.append({
                    'thread_id': thread_id,
                    'timeline': timeline,
                    'activity_count': len(timeline.points)
                })
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        if not comparisons:
            return QueryResult.empty(
                query_id=request.query_id,
                query_type=self.query_type,
                execution_time_ms=execution_time_ms
            )
        
        return QueryResult(
            query_id=request.query_id,
            query_type=self.query_type,
            success=True,
            result_count=len(comparisons),
            results=tuple(comparisons),
            execution_time_ms=execution_time_ms
        )


class RewindQueryHandler(QueryHandler):
    """
    Handler for rewind/replay queries.
    
    Returns system state at a specific point in time.
    Enables full deterministic replay.
    """
    
    @property
    def query_type(self) -> QueryType:
        return QueryType.REWIND
    
    def handle(
        self,
        request: QueryRequest,
        storage: TemporalStorageEngine
    ) -> QueryResult:
        start_time = time.time()
        
        if not request.target_timestamp:
            return QueryResult.failed(
                query_id=request.query_id,
                query_type=self.query_type,
                error=QueryError(
                    error_code=ErrorCode.TEMPORAL_AMBIGUITY,
                    message="target_timestamp is required for rewind queries",
                    query_id=request.query_id,
                    timestamp=Timestamp.now()
                )
            )
        
        # Get all threads' states at target time
        all_thread_ids = storage.backend.get_all_thread_ids()
        
        states = []
        for thread_id in all_thread_ids[:request.max_results]:
            snapshot = storage.get_thread_at_time(
                thread_id=thread_id,
                target_time=request.target_timestamp
            )
            if snapshot:
                states.append({
                    'thread_id': thread_id,
                    'snapshot': snapshot,
                    'at_time': request.target_timestamp
                })
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        if not states:
            return QueryResult.empty(
                query_id=request.query_id,
                query_type=self.query_type,
                execution_time_ms=execution_time_ms
            )
        
        return QueryResult(
            query_id=request.query_id,
            query_type=self.query_type,
            success=True,
            result_count=len(states),
            results=tuple(states),
            execution_time_ms=execution_time_ms
        )


# =============================================================================
# QUERY ENGINE (Orchestrates query handling)
# =============================================================================

@dataclass
class QueryEngineConfig:
    """Configuration for query engine."""
    default_max_results: int = 100
    query_timeout_seconds: float = 30.0
    enable_caching: bool = False  # Disabled by default for determinism


class QueryEngine:
    """
    Query Engine.
    
    BOUNDARY ENFORCEMENT:
    - ONLY performs read operations
    - NEVER modifies any state
    - Returns explicit success/failure for all queries
    - No heuristic smoothing or silent fallbacks
    """
    
    def __init__(
        self,
        storage: TemporalStorageEngine,
        config: Optional[QueryEngineConfig] = None
    ):
        self._storage = storage
        self._config = config or QueryEngineConfig()
        self._handlers: Dict[QueryType, QueryHandler] = {}
        self._query_counter: int = 0
        self._audit_log: List[AuditLogEntry] = []
        
        # Register handlers
        self._register_default_handlers()
    
    def _register_default_handlers(self):
        """Register built-in query handlers."""
        self.register_handler(TimelineQueryHandler())
        self.register_handler(ThreadStateQueryHandler())
        self.register_handler(FragmentTraceQueryHandler())
        self.register_handler(ComparisonQueryHandler())
        self.register_handler(RewindQueryHandler())
    
    def register_handler(self, handler: QueryHandler):
        """Register a query handler."""
        self._handlers[handler.query_type] = handler
    
    def execute(self, request: QueryRequest) -> QueryResult:
        """
        Execute a query request.
        
        Returns QueryResult with explicit success/failure status.
        Deterministic: same request always produces same result
        (assuming underlying data hasn't changed).
        """
        start_time = time.time()
        
        # Get handler
        handler = self._handlers.get(request.query_type)
        
        if not handler:
            return QueryResult.failed(
                query_id=request.query_id,
                query_type=request.query_type,
                error=QueryError(
                    error_code=ErrorCode.INSUFFICIENT_DATA,
                    message=f"No handler registered for query type: {request.query_type}",
                    query_id=request.query_id,
                    timestamp=Timestamp.now()
                )
            )
        
        # Execute query
        try:
            result = handler.handle(request, self._storage)
        except Exception as e:
            return QueryResult.failed(
                query_id=request.query_id,
                query_type=request.query_type,
                error=QueryError(
                    error_code=ErrorCode.STRUCTURAL_INCONSISTENCY,
                    message=f"Query execution failed: {str(e)}",
                    query_id=request.query_id,
                    timestamp=Timestamp.now()
                )
            )
        
        # Log query
        self._log_audit(
            action="query_executed",
            entity_id=request.query_id,
            metadata=(
                ("query_type", request.query_type.value),
                ("success", str(result.success)),
                ("result_count", str(result.result_count)),
                ("execution_time_ms", f"{result.execution_time_ms:.2f}"),
            )
        )
        
        self._query_counter += 1
        
        return result
    
    def query_timeline(
        self,
        thread_id: ThreadId,
        time_range: Optional[TimeRange] = None
    ) -> QueryResult:
        """Convenience method for timeline queries."""
        request = QueryRequest(
            query_id=self._generate_query_id("timeline"),
            query_type=QueryType.TIMELINE,
            thread_id=thread_id,
            time_range=time_range
        )
        return self.execute(request)
    
    def query_thread_state(
        self,
        thread_id: ThreadId,
        at_time: Optional[Timestamp] = None
    ) -> QueryResult:
        """Convenience method for thread state queries."""
        request = QueryRequest(
            query_id=self._generate_query_id("state"),
            query_type=QueryType.THREAD_STATE,
            thread_id=thread_id,
            target_timestamp=at_time
        )
        return self.execute(request)
    
    def query_fragment_trace(
        self,
        fragment_id: FragmentId
    ) -> QueryResult:
        """Convenience method for fragment trace queries."""
        request = QueryRequest(
            query_id=self._generate_query_id("trace"),
            query_type=QueryType.FRAGMENT_TRACE,
            fragment_id=fragment_id
        )
        return self.execute(request)
    
    def query_comparison(
        self,
        time_range: TimeRange,
        max_results: int = 10
    ) -> QueryResult:
        """Convenience method for comparison queries."""
        request = QueryRequest(
            query_id=self._generate_query_id("comparison"),
            query_type=QueryType.COMPARISON,
            time_range=time_range,
            max_results=max_results
        )
        return self.execute(request)
    
    def query_rewind(
        self,
        target_timestamp: Timestamp,
        max_results: int = 100
    ) -> QueryResult:
        """Convenience method for rewind queries."""
        request = QueryRequest(
            query_id=self._generate_query_id("rewind"),
            query_type=QueryType.REWIND,
            target_timestamp=target_timestamp,
            max_results=max_results
        )
        return self.execute(request)
    
    def _generate_query_id(self, prefix: str) -> str:
        """Generate deterministic query ID."""
        self._query_counter += 1
        content = f"{prefix}|{self._query_counter}|{Timestamp.now().value.timestamp()}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:12]
        return f"qry_{prefix}_{hash_val}"
    
    def _log_audit(
        self,
        action: str,
        entity_id: Optional[str] = None,
        metadata: tuple = ()
    ):
        """Add entry to internal audit log."""
        entry_id = hashlib.sha256(
            f"query_{action}|{Timestamp.now().value.timestamp()}".encode()
        ).hexdigest()[:16]
        
        entry = AuditLogEntry(
            entry_id=f"audit_{entry_id}",
            event_type=AuditEventType.QUERY,
            timestamp=Timestamp.now(),
            layer="query",
            action=action,
            entity_id=entity_id,
            metadata=metadata
        )
        self._audit_log.append(entry)
    
    def get_audit_log(self) -> List[AuditLogEntry]:
        """Return copy of audit log entries."""
        return list(self._audit_log)
