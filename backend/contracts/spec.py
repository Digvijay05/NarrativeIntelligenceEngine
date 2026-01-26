"""
Canonical Narrative State Model (Backend Contract)

AUTHORITATIVE SPECIFICATION
===========================
This file defines the strict data contract for the Narrative Intelligence Engine.
It guarantees the epistemic rules:
R1. Append-only truth
R2. Explicit silence
R3. Backend-determined structure
R4. No inference

DO NOT MODIFY WITHOUT UPDATING TYPESCRIPT MIRROR.
"""

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional
from datetime import datetime

# =============================================================================
# 1. ENUMS (Closed World)
# =============================================================================

class SegmentKind(Enum):
    """
    Distinguishes between observed presence and explicit absence.
    R2: Silence is explicit data, not missing data.
    """
    PRESENCE = "presence"
    ABSENCE = "absence"

class ThreadState(Enum):
    """
    Lifecycle state of a narrative thread.
    R4: Descriptive flags, not evaluative.
    """
    ACTIVE = "active"
    DORMANT = "dormant"
    TERMINATED = "terminated"
    DIVERGENT = "divergent"

# =============================================================================
# 2. DTOs
# =============================================================================

@dataclass(frozen=True)
class FragmentDTO:
    """
    Atomic Evidence.
    R1: Irreducible observation. Any extraction/normalization happens before here.
    """
    fragment_id: str
    source_id: str
    event_time: datetime
    ingest_time: datetime
    payload_ref: str  # Hash or external pointer. NO embedded content.

@dataclass(frozen=True)
class TimelineSegmentDTO:
    """
    Time-bounded state of a thread.
    The atomic unit of rendering.
    """
    segment_id: str
    thread_id: str
    kind: SegmentKind
    
    start_time: datetime
    end_time: datetime
    
    state: ThreadState
    
    # R2: Empty ONLY if kind == ABSENCE.
    # If kind == PRESENCE, must have >= 1 fragment.
    fragment_ids: List[str] 

@dataclass(frozen=True)
class NarrativeThreadDTO:
    """
    Structural grouping of fragments.
    Does NOT imply truth or coherence, only structural relationship.
    """
    thread_id: str
    # I1: No implicit gaps. Segments must be contiguous or explicitly bridged by ABSENCE keys.
    # Note: In this strict spec, ABSENCE segments bridge the gaps.
    segments: List[TimelineSegmentDTO]

@dataclass(frozen=True)
class NarrativeVersionDTO:
    """
    Top-Level Unit.
    A snapshot of the entire narrative landscape at a logical time.
    R1: Immutable once emitted.
    """
    version_id: str
    generated_at: datetime
    threads: List[NarrativeThreadDTO]
