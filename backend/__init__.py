"""
Narrative Intelligence Engine Backend

This package implements a strictly layered backend architecture with
hard boundaries between system responsibilities. Each layer communicates
only through explicit contracts, never through shared mutable state.

LAYER STRUCTURE:
================

1. INGESTION LAYER (ingestion/)
   - Responsibility: Raw data capture from external sources
   - Allowed inputs: External API calls, file uploads, push/pull collectors
   - Outputs: RawIngestionEvent (immutable, append-only)
   - MUST NOT: Transform, normalize, deduplicate, or interpret data

2. NORMALIZATION LAYER (normalization/)
   - Responsibility: Canonicalize, deduplicate, tag contradictions
   - Allowed inputs: RawIngestionEvent from ingestion layer
   - Outputs: NormalizedFragment (immutable)
   - MUST NOT: Store data, manage threads, make truth judgments

3. CORE NARRATIVE STATE ENGINE (core/)
   - Responsibility: Thread construction, lifecycle, divergence detection
   - Allowed inputs: NormalizedFragment from normalization layer
   - Outputs: NarrativeStateEvent (immutable)
   - MUST NOT: Query past states, persist data, rank importance

4. TEMPORAL STORAGE LAYER (storage/)
   - Responsibility: Append-only versioned persistence, time-travel queries
   - Allowed inputs: Any immutable event from other layers
   - Outputs: VersionedSnapshot, HistoricalQuery results
   - MUST NOT: Transform data, execute business logic

5. QUERY & ANALYSIS INTERFACES (query/)
   - Responsibility: Read-only access, timeline/comparison/evidence queries
   - Allowed inputs: Query requests with explicit parameters
   - Outputs: Deterministic QueryResult with explicit error states
   - MUST NOT: Mutate state, access storage directly (use contracts)

6. OBSERVABILITY & AUDIT LAYER (observability/)
   - Responsibility: Logging, metrics, replay capability, lineage tracking
   - Allowed inputs: Any event stream
   - Outputs: AuditLog, Metrics, ReplayCapability
   - MUST NOT: Modify system behavior, filter or interpret events

CONSTRAINTS ENFORCED:
=====================
- Immutability-first: All data structures are frozen/immutable
- Append-only: No in-place mutation of any narrative state
- Deterministic: Identical inputs always produce identical outputs
- Explicit errors: No silent fallbacks, all error states are queryable
- No truth adjudication: Contradictions are represented, never resolved
- No importance ranking: All fragments are treated equally
- No prediction/sentiment: Pure structural analysis only
"""
