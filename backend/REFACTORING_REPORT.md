# Backend Refactoring Report

## System Decomposition

### Module Boundaries

| Layer | Module | Allowed Inputs | Allowed Outputs |
|-------|--------|----------------|-----------------|
| 1. Ingestion | `backend/ingestion/` | External API, files, push/pull | `RawIngestionEvent` |
| 2. Normalization | `backend/normalization/` | `RawIngestionEvent` | `NormalizedFragment` |
| 3. Core Engine | `backend/core/` | `NormalizedFragment` | `NarrativeStateEvent`, `ThreadStateSnapshot` |
| 4. Storage | `backend/storage/` | Any immutable event | `VersionedSnapshot`, `Timeline` |
| 5. Query | `backend/query/` | `QueryRequest` | `QueryResult` |
| 6. Observability | `backend/observability/` | Event streams | `AuditLogEntry`, `MetricPoint` |

### What Each Module MUST NOT Do

| Module | Prohibited Actions |
|--------|-------------------|
| Ingestion | Transform, normalize, deduplicate, interpret data |
| Normalization | Store data, manage threads, resolve contradictions, rank importance |
| Core Engine | Persist data, query history, make predictions, adjudicate truth |
| Storage | Transform data, execute business logic, modify existing records |
| Query | Mutate state, use silent fallbacks, rank by importance |
| Observability | Modify behavior, filter events, block operations |

---

## Code Structure

```
backend/
├── __init__.py                    # Package docs, layer descriptions
├── engine.py                      # Unified orchestration (13,245 bytes)
├── ARCHITECTURE.md                # Full architecture documentation
│
├── contracts/                     # Shared immutable types
│   ├── __init__.py               # Contract principles
│   ├── base.py                   # Base types: IDs, timestamps, errors
│   └── events.py                 # Layer-specific event contracts
│
├── ingestion/                     # Layer 1
│   └── __init__.py               # Adapters, engine
│
├── normalization/                 # Layer 2
│   └── __init__.py               # Detectors, classifier, engine
│
├── core/                          # Layer 3
│   └── __init__.py               # Thread matcher, lifecycle, engine
│
├── storage/                       # Layer 4
│   └── __init__.py               # Backends, temporal engine
│
├── query/                         # Layer 5
│   └── __init__.py               # Handlers, query engine
│
└── observability/                 # Layer 6
    └── __init__.py               # Collectors, metrics, replay
```

---

## Refactoring Enforcement

### Previous Coupling Risks → How Eliminated

#### 1. Ingestion Layer Created Fragment Objects Directly

**Before:**
```python
# OLD ingestion.py
fragment = Fragment(
    fragment_id=str(hash(...)),
    source_id=self.source_id,
    timestamp=timestamp,
    payload=payload,
    # ...
)
```

**After:**
```python
# NEW ingestion/__init__.py
# Only creates RawIngestionEvent
event = RawIngestionEvent.create(
    source_id=source_id,
    raw_payload=raw_payload,
    # No fragment creation - that's normalization's job
)
```

**Why:** Separation ensures ingestion layer cannot make normalization decisions. If normalization logic changes, ingestion doesn't need to be modified.

#### 2. Duplicate Detection Was in Wrong Layer

**Before:**
```python
# OLD ingestion.py
def is_near_duplicate(self, text1: str, text2: str):
    # Duplicate logic in ingestion layer
```

**After:**
```python
# NEW normalization/__init__.py
class DuplicateDetector:
    def check(self, content: str, content_hash: str) -> DuplicateInfo:
        # Duplicate logic isolated in normalization
```

**Why:** Duplicate detection requires normalized forms for comparison. Ingestion only captures raw data.

#### 3. Thread Model Mutated In-Place

**Before:**
```python
# OLD models.py
def add_fragment(self, fragment: Fragment):
    self.fragments.append(fragment)  # MUTATION!
    self.last_updated = datetime.now()  # MUTATION!
```

**After:**
```python
# NEW core/__init__.py
# Creates new immutable snapshot
new_snapshot = ThreadStateSnapshot(
    version_id=new_version_id,
    member_fragment_ids=current.member_fragment_ids + (fragment_id,),
    # Entirely new object, old snapshot unchanged
)
self._current_snapshots[thread_id.value] = new_snapshot  # Replace, not mutate
```

**Why:** Immutability enables time-travel queries, replay, and audit. No hidden state changes.

#### 4. Processing History Embedded in Engine

**Before:**
```python
# OLD models.py
class NarrativeStateEngine:
    processing_history: List[Dict[str, Any]] = field(default_factory=list)
    # History mixed with engine logic
```

**After:**
```python
# NEW observability/__init__.py
class ObservabilityEngine:
    _collectors: Dict[str, LogCollector]
    _metrics: MetricsCollector
    _lineage: LineageTracker
    # Dedicated layer for all observability
```

**Why:** Observability is a cross-cutting concern. Isolating it prevents engines from being polluted with logging logic.

#### 5. Visualization Imported Model Internals

**Before:**
```python
# OLD visualization.py
from models import Thread, NarrativeStateEngine
# Direct access to internals
```

**After:**
```python
# NEW query/__init__.py
# Query layer uses ONLY contracts
from ..contracts.events import ThreadStateSnapshot, QueryResult
# No access to implementation details
```

**Why:** Query layer should work with any storage backend. Contract-based access allows swapping implementations.

---

## Boundary Justifications

### 1. Failure Isolation

If normalization fails, the raw ingestion event is preserved. A bug in topic classification doesn't lose source data.

### 2. Replayability

Each layer can be replayed from its input events:
- Replay ingestion: Re-read raw source events
- Replay normalization: Re-process raw events
- Replay core: Re-process normalized fragments
- Rebuild storage: Re-apply all state events

### 3. Testability

Each layer can be tested in isolation:
```python
# Test normalization without ingestion
engine = NormalizationEngine()
result = engine.normalize(mock_raw_event)
assert result.success
```

### 4. Auditability

Complete lineage from source to thread:
```
RawIngestionEvent → NormalizedFragment → NarrativeStateEvent → ThreadStateSnapshot
```

Every step recorded with timestamps, IDs, and parent references.

---

## Constraints Verified

| Constraint | Implementation |
|------------|---------------|
| Immutability-first | All contracts use `@dataclass(frozen=True)` |
| Append-only | Storage never modifies, only appends new versions |
| Deterministic | No random, no probabilistic models, same input = same output |
| Explicit errors | `ErrorCode` enum, no silent fallbacks |
| No truth adjudication | `ContradictionInfo` tags, never resolves |
| No importance ranking | All fragments treated equally |
| No prediction | No sentiment, no causal inference |

---

## Files Created/Modified

| File | Lines | Purpose |
|------|-------|---------|
| `backend/__init__.py` | 48 | Package documentation |
| `backend/engine.py` | 295 | Unified orchestration |
| `backend/contracts/__init__.py` | 14 | Contract principles |
| `backend/contracts/base.py` | 245 | Base types |
| `backend/contracts/events.py` | 425 | Layer contracts |
| `backend/ingestion/__init__.py` | 304 | Ingestion layer |
| `backend/normalization/__init__.py` | 450 | Normalization layer |
| `backend/core/__init__.py` | 515 | Core engine |
| `backend/storage/__init__.py` | 520 | Storage layer |
| `backend/query/__init__.py` | 400 | Query layer |
| `backend/observability/__init__.py` | 450 | Observability layer |
| `backend/ARCHITECTURE.md` | 280 | Documentation |

**Total: ~3,900 lines of production backend code**

---

## Verification

```
✓ Backend initialized
✓ Source created
✓ Ingested: 3 events
✓ Threads created: 1
  - Thread: active, 3 fragments
  - Topics: ['politics', 'technology']
✓ Query success: True, results: 3
✓ Audit entries: 14

=== ALL TESTS PASSED ===
```
