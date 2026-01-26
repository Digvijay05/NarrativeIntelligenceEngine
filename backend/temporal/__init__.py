"""
Temporal Immutability Layer
===========================

Event-sourced state management for narrative intelligence.

INVARIANTS:
- All state is derived from append-only fragment log
- No mutation of stored data
- Same log → same derived state (deterministic)
- Late arrivals trigger recomputation, not mutation

Modules:
- event_log: Append-only fragment storage
- state_machine: Pure function state derivation
- versioning: Thread version lineage
- replay: Late-arrival recomputation
"""

from .event_log import ImmutableEventLog, LogEntry, LogSequence
from .state_machine import StateMachine, DerivedState
from .versioning import VersionedThread, ThreadLineage

__all__ = [
    'ImmutableEventLog',
    'LogEntry',
    'LogSequence',
    'StateMachine',
    'DerivedState',
    'VersionedThread',
    'ThreadLineage',
]
