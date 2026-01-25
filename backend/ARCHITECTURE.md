# Narrative Intelligence Engine - Backend Architecture

## Overview

This backend implements a **strictly layered architecture** for the Narrative Intelligence Engine with **hard boundaries** between system responsibilities. All layers communicate through **immutable contracts**, ensuring:

- **No cross-layer shortcuts**
- **No shared mutable state**
- **No implicit coupling**
- **Deterministic behavior**
- **Append-only data models**

---

## Layer Structure

```
backend/
├── __init__.py              # Package documentation
├── engine.py                # Unified orchestration interface
├── contracts/               # Layer contracts (immutable, shared)
│   ├── __init__.py
│   ├── base.py             # Base types: IDs, timestamps, errors
│   └── events.py           # Layer-specific event contracts
├── ingestion/              # Layer 1: Data Ingestion
│   └── __init__.py
├── normalization/          # Layer 2: Normalization & Canonicalization
│   └── __init__.py
├── core/                   # Layer 3: Core Narrative State Engine
│   └── __init__.py
├── storage/                # Layer 4: Temporal Storage
│   └── __init__.py
├── query/                  # Layer 5: Query & Analysis
│   └── __init__.py
└── observability/          # Layer 6: Observability & Audit
    └── __init__.py
```

---

## Layer Responsibilities

### Layer 1: Ingestion (`ingestion/`)

**Responsibility**: Raw data capture from external sources

| Allowed Inputs | Outputs | MUST NOT |
|----------------|---------|----------|
| External API calls | `RawIngestionEvent` | Transform data |
| File uploads | | Normalize data |
| Push/pull collectors | | Deduplicate |
| | | Interpret meaning |

### Layer 2: Normalization (`normalization/`)

**Responsibility**: Transform raw events into canonical fragments

| Allowed Inputs | Outputs | MUST NOT |
|----------------|---------|----------|
| `RawIngestionEvent` | `NormalizedFragment` | Store data |
| | | Manage threads |
| | | Make truth judgments |
| | | **Resolve contradictions** |

### Layer 3: Core Engine (`core/`)

**Responsibility**: Thread construction, lifecycle, divergence detection

| Allowed Inputs | Outputs | MUST NOT |
|----------------|---------|----------|
| `NormalizedFragment` | `NarrativeStateEvent` | Persist data |
| | `ThreadStateSnapshot` | Query history |
| | | Rank importance |
| | | **Make predictions** |

### Layer 4: Storage (`storage/`)

**Responsibility**: Append-only versioned persistence

| Allowed Inputs | Outputs | MUST NOT |
|----------------|---------|----------|
| Any immutable event | `VersionedSnapshot` | Transform data |
| | `Timeline` | Execute business logic |
| | | **Modify existing data** |

### Layer 5: Query (`query/`)

**Responsibility**: Read-only access to stored data

| Allowed Inputs | Outputs | MUST NOT |
|----------------|---------|----------|
| `QueryRequest` | `QueryResult` | Mutate state |
| | | Interpret results |
| | | **Silent fallbacks** |

### Layer 6: Observability (`observability/`)

**Responsibility**: Logging, metrics, replay, lineage

| Allowed Inputs | Outputs | MUST NOT |
|----------------|---------|----------|
| Event streams | `AuditLogEntry` | Modify behavior |
| | `MetricPoint` | Filter events |
| | `ReplayCheckpoint` | **Block operations** |

---

## Key Design Principles

### 1. Immutability-First

All data structures are **frozen dataclasses**:

```python
@dataclass(frozen=True)
class NormalizedFragment:
    fragment_id: FragmentId
    content_signature: ContentSignature
    # ... all fields immutable
```

### 2. Append-Only Operations

State changes create **new versions**, never mutate:

```python
# Old way (WRONG):
thread.fragments.append(fragment)  # Mutation!

# New way (CORRECT):
new_snapshot = ThreadStateSnapshot(
    version_id=new_version_id,
    member_fragment_ids=current.member_fragment_ids + (fragment_id,),
    # ...
)
```

### 3. Explicit Error States

No silent fallbacks - all errors are enumerated:

```python
class ErrorCode(Enum):
    INSUFFICIENT_DATA = auto()
    TEMPORAL_AMBIGUITY = auto()
    STRUCTURAL_INCONSISTENCY = auto()
    # Every error state is explicit
```

### 4. Contradictions Are Represented, Not Resolved

```python
@dataclass(frozen=True)
class ContradictionInfo:
    status: ContradictionStatus
    contradicting_fragment_ids: Tuple[FragmentId, ...]
    # Both sides preserved - no truth adjudication
```

### 5. Deterministic Behavior

Same input always produces same output:

```python
# Language detection is word-based, not probabilistic
# Duplicate detection uses Jaccard similarity with fixed threshold
# Topic classification uses keyword matching
```

---

## Data Flow

```
External Source
      │
      ▼
┌──────────────────┐
│  INGESTION       │ ──────▶ RawIngestionEvent
│  (adapters)      │
└──────────────────┘
      │
      ▼
┌──────────────────┐
│  NORMALIZATION   │ ──────▶ NormalizedFragment
│  (canonicalize)  │         (with duplicate/contradiction tags)
└──────────────────┘
      │
      ▼
┌──────────────────┐
│  CORE ENGINE     │ ──────▶ NarrativeStateEvent
│  (threads)       │         ThreadStateSnapshot
└──────────────────┘
      │
      ▼
┌──────────────────┐
│  STORAGE         │ ──────▶ Versioned persistence
│  (append-only)   │         Time-travel capability
└──────────────────┘
      │
      ▼
┌──────────────────┐
│  QUERY           │ ◀────── QueryRequest
│  (read-only)     │ ──────▶ QueryResult
└──────────────────┘
      │
      ▼
┌──────────────────┐
│  OBSERVABILITY   │ ──────▶ Audit logs, metrics
│  (all events)    │         Replay capability
└──────────────────┘
```

---

## Refactoring Summary

### Previous Coupling Risks Eliminated

| Previous Issue | How Eliminated |
|----------------|----------------|
| `ingestion.py` created `Fragment` directly | Separated: ingestion creates `RawIngestionEvent`, normalization creates `NormalizedFragment` |
| Duplicate detection in ingestion layer | Moved to dedicated `DuplicateDetector` in normalization |
| Thread model stored versions internally | Externalized to storage layer with `VersionedSnapshot` |
| `NarrativeStateEngine` mutated state | All changes now produce new immutable `ThreadStateSnapshot` |
| Processing history embedded in engine | Separate observability layer with `AuditLogEntry` |
| Visualization imported models | Query layer uses only contracts |
| No explicit error handling | All operations return explicit `Result` with `Error` |

### Boundary Justification

Each boundary exists for:

1. **Failure Isolation**: If normalization fails, ingestion events are preserved
2. **Replayability**: Any layer can be replayed from its input events
3. **Testability**: Each layer can be tested in isolation with mock contracts
4. **Auditability**: Complete lineage from raw event to thread state

---

## Usage Example

```python
from backend.engine import NarrativeIntelligenceBackend, BackendConfig
from backend.contracts.base import SourceId, Timestamp

# Initialize backend
backend = NarrativeIntelligenceBackend()

# Create source ID
source = SourceId(value="news_feed", source_type="in_memory")

# Ingest data
events = backend.ingest_batch(
    source_id=source,
    payloads=[
        '{"timestamp": "2024-01-01T10:00:00", "payload": "Climate policy announced"}',
        '{"timestamp": "2024-01-01T11:00:00", "payload": "Industry responds to climate policy"}',
    ]
)

# Query thread timeline
for thread_id in backend.get_all_threads():
    result = backend.query_timeline(ThreadId(value=thread_id))
    if result.success:
        print(f"Thread {thread_id}: {result.result_count} points")

# Get audit report
report = backend.get_audit_report()
print(f"Total events: {report['total_entries']}")
```

---

## Testing

Each layer can be tested independently:

```python
# Test normalization in isolation
from backend.normalization import NormalizationEngine
from backend.contracts.events import RawIngestionEvent

engine = NormalizationEngine()
result = engine.normalize(mock_raw_event)
assert result.success
assert result.fragment.duplicate_info.status == DuplicateStatus.UNIQUE
```

---

## Success Metrics

- ✅ Process multiple data sources simultaneously
- ✅ Deterministic outputs for identical inputs
- ✅ Time-travel queries and timeline reversion
- ✅ Handle incomplete, delayed, or conflicting data
- ✅ Maintain versioned narrative states
- ✅ Scalable architecture
- ✅ Full audit trail
