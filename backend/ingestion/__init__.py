"""
Ingestion Layer

RESPONSIBILITY: Raw data capture from external sources
ALLOWED INPUTS: External API calls, file uploads, push/pull collectors  
OUTPUTS: RawIngestionEvent (immutable, append-only)

WHAT THIS LAYER MUST NOT DO:
============================
- Transform or normalize data
- Deduplicate content
- Classify topics or extract entities
- Make any interpretation of data meaning
- Store data persistently (that's storage layer's job)
- Access any other layer's internal state

BOUNDARY ENFORCEMENT:
=====================
This layer ONLY produces RawIngestionEvent objects.
It does NOT import from normalization, core, storage, or query layers.
The ONLY shared dependency is the contracts module.

REFACTORING FROM PREVIOUS CODE:
===============================
Previous coupling risks eliminated:
1. OLD: ingestion.py created Fragment objects directly
   NEW: Creates only RawIngestionEvent, normalization creates fragments
2. OLD: ingestion.py did duplicate detection  
   NEW: Duplicate detection moved to normalization layer
3. OLD: ingestion.py did language detection
   NEW: Language detection moved to normalization layer
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Iterator, Optional, Dict, Any
import json
import csv
import hashlib

# ONLY import from contracts - never from other layers
from ..contracts.base import SourceId, Timestamp, Error, ErrorCode, Result, SourceTier
from ..contracts.events import RawIngestionEvent, IngestionBatch, AuditLogEntry, AuditEventType


# =============================================================================
# INGESTION ADAPTERS (Strategy pattern for different sources)
# =============================================================================

class IngestionAdapter(ABC):
    """
    Abstract base for source-specific ingestion adapters.
    
    Each adapter knows how to pull/receive data from ONE type of source.
    Adapters produce raw events, never interpreted data.
    
    SHADOW MODE SUPPORT:
    - source_tier property classifies adapter output (MOCK, PUBLIC_RSS)
    - Tier is metadata only, no interpretive weighting
    """
    
    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the type of source this adapter handles."""
        pass
    
    @property
    @abstractmethod
    def source_tier(self) -> SourceTier:
        """Return the tier classification for this adapter."""
        pass
    
    @abstractmethod
    def validate_source(self, source_id: SourceId) -> Result:
        """Validate that the source exists and is accessible."""
        pass
    
    @abstractmethod
    def pull_events(self, source_id: SourceId, since: Optional[Timestamp] = None) -> Iterator[RawIngestionEvent]:
        """Pull events from the source since given timestamp."""
        pass


class JsonFileAdapter(IngestionAdapter):
    """Adapter for ingesting from JSON files."""
    
    @property
    def source_type(self) -> str:
        return "json_file"
    
    @property
    def source_tier(self) -> SourceTier:
        return SourceTier.MOCK  # File-based adapters are mock tier
    
    def validate_source(self, source_id: SourceId) -> Result:
        """Validate JSON file exists and is readable."""
        import os
        file_path = source_id.value
        
        if not os.path.exists(file_path):
            return Result.failure(Error(
                code=ErrorCode.SOURCE_UNREACHABLE,
                message=f"File not found: {file_path}",
                timestamp=Timestamp.now().value
            ))
        
        if not os.path.isfile(file_path):
            return Result.failure(Error(
                code=ErrorCode.INVALID_SOURCE_ID,
                message=f"Path is not a file: {file_path}",
                timestamp=Timestamp.now().value
            ))
        
        return Result.success(True)
    
    def pull_events(self, source_id: SourceId, since: Optional[Timestamp] = None) -> Iterator[RawIngestionEvent]:
        """Read events from JSON file."""
        validation = self.validate_source(source_id)
        if validation.is_failure:
            # Return empty iterator on validation failure
            # Error should be logged by caller
            return iter([])
        
        file_path = source_id.value
        
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if not isinstance(data, list):
            data = [data]
        
        for item in data:
            # Extract raw data without interpretation
            raw_payload = json.dumps(item) if isinstance(item, dict) else str(item)
            
            # Try to extract event timestamp if present (but don't require it)
            event_timestamp = None
            if isinstance(item, dict) and 'timestamp' in item:
                try:
                    event_timestamp = Timestamp.from_iso(item['timestamp'])
                except (ValueError, TypeError):
                    pass  # Leave as None if parsing fails
            
            # Filter by 'since' if provided
            if since and event_timestamp and event_timestamp.value <= since.value:
                continue
            
            yield RawIngestionEvent.create(
                source_id=source_id,
                raw_payload=raw_payload,
                source_confidence=1.0,  # File sources assumed fully reliable
                event_timestamp=event_timestamp
            )


class CsvFileAdapter(IngestionAdapter):
    """Adapter for ingesting from CSV files."""
    
    @property
    def source_type(self) -> str:
        return "csv_file"
    
    @property
    def source_tier(self) -> SourceTier:
        return SourceTier.MOCK  # File-based adapters are mock tier
    
    def validate_source(self, source_id: SourceId) -> Result:
        """Validate CSV file exists and is readable."""
        import os
        file_path = source_id.value
        
        if not os.path.exists(file_path):
            return Result.failure(Error(
                code=ErrorCode.SOURCE_UNREACHABLE,
                message=f"File not found: {file_path}",
                timestamp=Timestamp.now().value
            ))
        
        return Result.success(True)
    
    def pull_events(self, source_id: SourceId, since: Optional[Timestamp] = None) -> Iterator[RawIngestionEvent]:
        """Read events from CSV file."""
        validation = self.validate_source(source_id)
        if validation.is_failure:
            return iter([])
        
        file_path = source_id.value
        
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                raw_payload = json.dumps(dict(row))
                
                event_timestamp = None
                if 'timestamp' in row:
                    try:
                        event_timestamp = Timestamp.from_iso(row['timestamp'])
                    except (ValueError, TypeError):
                        pass
                
                if since and event_timestamp and event_timestamp.value <= since.value:
                    continue
                
                yield RawIngestionEvent.create(
                    source_id=source_id,
                    raw_payload=raw_payload,
                    source_confidence=1.0,
                    event_timestamp=event_timestamp
                )


class InMemoryAdapter(IngestionAdapter):
    """Adapter for push-based in-memory data ingestion."""
    
    @property
    def source_type(self) -> str:
        return "in_memory"
    
    @property
    def source_tier(self) -> SourceTier:
        return SourceTier.MOCK  # In-memory adapters are mock tier
    
    def validate_source(self, source_id: SourceId) -> Result:
        """In-memory sources are always valid."""
        return Result.success(True)
    
    def pull_events(self, source_id: SourceId, since: Optional[Timestamp] = None) -> Iterator[RawIngestionEvent]:
        """In-memory adapter doesn't pull - use push_event instead."""
        return iter([])
    
    def push_event(self, source_id: SourceId, payload: str, 
                   event_timestamp: Optional[Timestamp] = None,
                   source_confidence: float = 1.0) -> RawIngestionEvent:
        """Push a single event into the system."""
        return RawIngestionEvent.create(
            source_id=source_id,
            raw_payload=payload,
            source_confidence=source_confidence,
            event_timestamp=event_timestamp
        )


class RssFileAdapter(IngestionAdapter):
    """Adapter for ingesting from RSS feeds (via Capsule Force)."""
    
    def __init__(self, storage_dir: str = "./data/capsules"):
        from .rss_fetcher import RssFetcher
        from .extractor import RssExtractor
        self._fetcher = RssFetcher(storage_dir)
        self._extractor = RssExtractor()
        
    @property
    def source_type(self) -> str:
        return "rss"
    
    @property
    def source_tier(self) -> SourceTier:
        return SourceTier.MOCK  # File-based RSS adapter is mock tier
    
    def validate_source(self, source_id: SourceId) -> Result:
        """Validate source against Immutable Registry."""
        from .registry import get_source_by_id
        try:
            get_source_by_id(source_id.value)
            return Result.success(True)
        except ValueError:
            return Result.failure(Error(
                code=ErrorCode.INVALID_SOURCE_ID,
                message=f"Source {source_id.value} not in immutable registry",
                timestamp=Timestamp.now().value
            ))
            
    def pull_events(self, source_id: SourceId, since: Optional[Timestamp] = None) -> Iterator[RawIngestionEvent]:
        """
        Fetch -> Persist -> Extract -> Yield.
        """
        from .registry import get_source_by_id
        
        # 1. Validate
        try:
            reg_source = get_source_by_id(source_id.value)
        except ValueError:
            return iter([])
            
        # 2. Fetch (Persist Raw XML)
        capsule = self._fetcher.fetch_source(source_id.value, reg_source.url)
        if not capsule:
            return iter([])
            
        # 3. Extract (Deterministic)
        items = self._extractor.extract_capsule(capsule.file_path)
        
        # 4. Yield Events
        for item in items:
            # Construct deterministic payload
            # We use a simple dict serialization
            payload = {
                "title": item.title,
                "link": item.link,
                "summary": item.summary,
                "published": item.published_str,
                "guid": item.guid,
                "capsule_id": capsule.capsule_id # Link back to raw XML
            }
            
            raw_payload = json.dumps(payload)
            
            # Parse timestamp if possible, else None (System will use ingestion time)
            event_ts = None
            
            yield RawIngestionEvent.create(
                source_id=source_id,
                raw_payload=raw_payload,
                source_confidence=1.0, # Trusted source
                event_timestamp=event_ts
            )


# =============================================================================
# INGESTION ENGINE (Orchestrates adapters)
# =============================================================================

@dataclass
class IngestionConfig:
    """Configuration for ingestion engine."""
    batch_size: int = 100
    max_concurrent_sources: int = 5
    default_source_confidence: float = 1.0


class IngestionEngine:
    """
    Core ingestion engine that orchestrates data capture.
    
    BOUNDARY ENFORCEMENT:
    - This class ONLY produces RawIngestionEvent objects
    - It does NOT interpret, transform, or normalize data
    - It delegates to adapters for source-specific logic
    """
    
    def __init__(self, config: Optional[IngestionConfig] = None):
        self._config = config or IngestionConfig()
        self._adapters: Dict[str, IngestionAdapter] = {}
        self._audit_log: List[AuditLogEntry] = []
        
        # Register built-in adapters
        self._register_default_adapters()
    
    def _register_default_adapters(self):
        """Register built-in adapter implementations."""
        self.register_adapter(JsonFileAdapter())
        self.register_adapter(CsvFileAdapter())
        self.register_adapter(InMemoryAdapter())
        # Registry-based RSS adapter
        # We assume default storage dir for now, can be configured later
        self.register_adapter(RssFileAdapter())
    
    def register_adapter(self, adapter: IngestionAdapter):
        """Register an ingestion adapter for a source type."""
        self._adapters[adapter.source_type] = adapter
    
    def get_adapter(self, source_type: str) -> Optional[IngestionAdapter]:
        """Get adapter for source type."""
        return self._adapters.get(source_type)
    
    def ingest_from_source(
        self,
        source_id: SourceId,
        since: Optional[Timestamp] = None
    ) -> Iterator[RawIngestionEvent]:
        """
        Ingest events from a source using the appropriate adapter.
        
        This is the primary entry point for pull-based ingestion.
        Yields RawIngestionEvent objects as they are captured.
        """
        adapter = self._adapters.get(source_id.source_type)
        
        if adapter is None:
            # Log error and return empty
            self._log_audit(
                action="adapter_not_found",
                metadata=(("source_type", source_id.source_type),)
            )
            return iter([])
        
        # Validate source
        validation = adapter.validate_source(source_id)
        if validation.is_failure:
            self._log_audit(
                action="source_validation_failed",
                metadata=(
                    ("source_id", source_id.value),
                    ("error", validation.error.message if validation.error else "unknown")
                )
            )
            return iter([])
        
        # Pull events with audit logging
        event_count = 0
        for event in adapter.pull_events(source_id, since):
            event_count += 1
            yield event
        
        self._log_audit(
            action="ingestion_completed",
            metadata=(
                ("source_id", source_id.value),
                ("event_count", str(event_count)),
            )
        )
    
    def ingest_batch(
        self,
        source_id: SourceId,
        payloads: List[str],
        event_timestamps: Optional[List[Optional[Timestamp]]] = None,
        source_confidence: float = 1.0
    ) -> IngestionBatch:
        """
        Ingest a batch of payloads from a push-based source.
        
        This is the primary entry point for push-based ingestion.
        Returns an immutable IngestionBatch.
        """
        batch_id = self._generate_batch_id(source_id, len(payloads))
        events = []
        
        timestamps = event_timestamps or [None] * len(payloads)
        
        for payload, event_ts in zip(payloads, timestamps):
            event = RawIngestionEvent.create(
                source_id=source_id,
                raw_payload=payload,
                source_confidence=source_confidence,
                event_timestamp=event_ts,
                batch_id=batch_id
            )
            events.append(event)
        
        batch = IngestionBatch(
            batch_id=batch_id,
            events=tuple(events),
            created_at=Timestamp.now(),
            source_id=source_id
        )
        
        self._log_audit(
            action="batch_ingestion_completed",
            entity_id=batch_id,
            entity_type="batch",
            metadata=(
                ("source_id", source_id.value),
                ("event_count", str(len(events))),
            )
        )
        
        return batch
    
    def ingest_single(
        self,
        source_id: SourceId,
        payload: str,
        event_timestamp: Optional[Timestamp] = None,
        source_confidence: float = 1.0
    ) -> RawIngestionEvent:
        """
        Ingest a single event for push-based sources.
        
        Convenience method for single-event ingestion.
        """
        event = RawIngestionEvent.create(
            source_id=source_id,
            raw_payload=payload,
            source_confidence=source_confidence,
            event_timestamp=event_timestamp
        )
        
        self._log_audit(
            action="single_event_ingested",
            entity_id=event.event_id,
            entity_type="event",
            metadata=(("source_id", source_id.value),)
        )
        
        return event
    
    def _generate_batch_id(self, source_id: SourceId, count: int) -> str:
        """Generate deterministic batch ID."""
        now = Timestamp.now()
        content = f"{source_id.value}|{count}|{now.value.timestamp()}"
        hash_val = hashlib.sha256(content.encode()).hexdigest()[:16]
        return f"batch_{hash_val}"
    
    def _log_audit(
        self,
        action: str,
        entity_id: Optional[str] = None,
        entity_type: Optional[str] = None,
        metadata: tuple = ()
    ):
        """Add entry to internal audit log."""
        entry_id = hashlib.sha256(
            f"{action}|{Timestamp.now().value.timestamp()}".encode()
        ).hexdigest()[:16]
        
        entry = AuditLogEntry(
            entry_id=f"audit_{entry_id}",
            event_type=AuditEventType.INGESTION,
            timestamp=Timestamp.now(),
            layer="ingestion",
            action=action,
            entity_id=entity_id,
            entity_type=entity_type,
            metadata=metadata
        )
        self._audit_log.append(entry)
    
    def get_audit_log(self) -> List[AuditLogEntry]:
        """Return copy of audit log entries."""
        return list(self._audit_log)
