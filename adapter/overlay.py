"""
Model Overlay Store

Stores model outputs as versioned overlays on backend state.

BOUNDARY ENFORCEMENT:
=====================
Model outputs NEVER mutate backend state.
They are stored as OVERLAYS that can be queried alongside state.

WHY OVERLAYS:
=============
1. Backend state remains sovereign - model cannot corrupt it
2. Model outputs are versioned independently
3. Historical model outputs are preserved
4. Easy to compare model versions
5. Rollback is trivial (just ignore overlay)
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import hashlib

from .contracts import (
    ModelAnalysisResponse,
    ModelAnnotation,
    ModelScore,
    InvocationMetadata,
    ModelVersionInfo,
)


# =============================================================================
# OVERLAY TYPES
# =============================================================================

@dataclass(frozen=True)
class ModelOverlay:
    """
    Versioned overlay of model outputs on backend state.
    
    WHY THIS STRUCTURE:
    - Links to backend state by entity_id (never copies state)
    - Fully versioned for replay
    - Immutable - new analysis creates new overlay
    """
    overlay_id: str
    overlay_version: str
    entity_id: str  # The backend entity this overlays (thread_id, fragment_id)
    entity_type: str
    entity_version: str  # Version of backend entity when overlay was created
    
    # Source of overlay
    invocation_id: str
    model_version: str
    model_weights_hash: str
    
    # Overlay content
    annotations: Tuple[ModelAnnotation, ...]
    scores: Tuple[ModelScore, ...]
    
    # Timestamps
    created_at: datetime
    expires_at: Optional[datetime] = None  # Optional TTL for cache purposes
    
    # Supersedes
    supersedes_overlay_id: Optional[str] = None  # Previous overlay this replaces
    
    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Check if overlay has expired."""
        if self.expires_at is None:
            return False
        check_time = now or datetime.utcnow()
        return check_time > self.expires_at


@dataclass(frozen=True)
class OverlayQuery:
    """Query for retrieving overlays."""
    entity_id: Optional[str] = None
    entity_type: Optional[str] = None
    model_version: Optional[str] = None
    include_expired: bool = False
    max_results: int = 100


@dataclass(frozen=True)
class OverlayQueryResult:
    """Result of overlay query."""
    query_id: str
    overlays: Tuple[ModelOverlay, ...]
    total_count: int
    has_more: bool


# =============================================================================
# OVERLAY STORE
# =============================================================================

class OverlayStore:
    """
    Store for model overlays.
    
    GUARANTEES:
    ===========
    1. Overlays are append-only (never mutated)
    2. All overlays are versioned
    3. Historical overlays are preserved
    4. Query always returns consistent results
    
    WHY IN-MEMORY:
    In production, this would be backed by durable storage.
    In-memory implementation shows the interface contract.
    """
    
    def __init__(self):
        self._overlays: Dict[str, ModelOverlay] = {}  # overlay_id -> overlay
        self._by_entity: Dict[str, List[str]] = {}  # entity_id -> list of overlay_ids
        self._by_version: Dict[str, List[str]] = {}  # model_version -> list of overlay_ids
        self._version_counter = 0
    
    def store(
        self,
        response: ModelAnalysisResponse,
        entity_id: str,
        entity_type: str,
        entity_version: str
    ) -> ModelOverlay:
        """
        Store model response as an overlay.
        
        Returns the created overlay.
        NEVER mutates the response.
        """
        if not response.success:
            raise ValueError("Cannot store failed response as overlay")
        
        self._version_counter += 1
        
        # Generate overlay ID
        overlay_id = self._generate_overlay_id(
            entity_id=entity_id,
            invocation_id=response.invocation.invocation_id
        )
        overlay_version = f"v{self._version_counter}"
        
        # Find superseded overlay
        supersedes = None
        existing = self._by_entity.get(entity_id, [])
        if existing:
            # Get latest non-expired overlay
            for oid in reversed(existing):
                overlay = self._overlays.get(oid)
                if overlay and not overlay.is_expired():
                    supersedes = overlay.overlay_id
                    break
        
        overlay = ModelOverlay(
            overlay_id=overlay_id,
            overlay_version=overlay_version,
            entity_id=entity_id,
            entity_type=entity_type,
            entity_version=entity_version,
            invocation_id=response.invocation.invocation_id,
            model_version=response.invocation.model_version.model_version,
            model_weights_hash=response.invocation.model_version.weights_hash,
            annotations=response.annotations,
            scores=response.scores,
            created_at=datetime.utcnow(),
            supersedes_overlay_id=supersedes
        )
        
        # Store
        self._overlays[overlay_id] = overlay
        
        if entity_id not in self._by_entity:
            self._by_entity[entity_id] = []
        self._by_entity[entity_id].append(overlay_id)
        
        model_ver = response.invocation.model_version.model_version
        if model_ver not in self._by_version:
            self._by_version[model_ver] = []
        self._by_version[model_ver].append(overlay_id)
        
        return overlay
    
    def get(self, overlay_id: str) -> Optional[ModelOverlay]:
        """Get overlay by ID."""
        return self._overlays.get(overlay_id)
    
    def get_latest_for_entity(
        self,
        entity_id: str,
        model_version: Optional[str] = None
    ) -> Optional[ModelOverlay]:
        """
        Get latest non-expired overlay for an entity.
        
        Optionally filter by model version.
        """
        overlay_ids = self._by_entity.get(entity_id, [])
        
        for oid in reversed(overlay_ids):
            overlay = self._overlays.get(oid)
            if overlay and not overlay.is_expired():
                if model_version is None or overlay.model_version == model_version:
                    return overlay
        
        return None
    
    def query(self, query: OverlayQuery) -> OverlayQueryResult:
        """
        Query overlays with filters.
        
        Returns immutable result.
        """
        query_id = self._generate_query_id()
        candidates = []
        
        # Filter by entity
        if query.entity_id:
            overlay_ids = self._by_entity.get(query.entity_id, [])
            candidates = [self._overlays[oid] for oid in overlay_ids if oid in self._overlays]
        else:
            candidates = list(self._overlays.values())
        
        # Filter by entity type
        if query.entity_type:
            candidates = [o for o in candidates if o.entity_type == query.entity_type]
        
        # Filter by model version
        if query.model_version:
            candidates = [o for o in candidates if o.model_version == query.model_version]
        
        # Filter expired
        if not query.include_expired:
            now = datetime.utcnow()
            candidates = [o for o in candidates if not o.is_expired(now)]
        
        # Sort by creation time (newest first)
        candidates.sort(key=lambda o: o.created_at, reverse=True)
        
        total = len(candidates)
        limited = candidates[:query.max_results]
        
        return OverlayQueryResult(
            query_id=query_id,
            overlays=tuple(limited),
            total_count=total,
            has_more=total > query.max_results
        )
    
    def get_history(
        self,
        entity_id: str,
        max_results: int = 50
    ) -> Tuple[ModelOverlay, ...]:
        """
        Get overlay history for an entity (newest first).
        
        Includes expired overlays for historical analysis.
        """
        overlay_ids = self._by_entity.get(entity_id, [])
        overlays = [
            self._overlays[oid] 
            for oid in reversed(overlay_ids)
            if oid in self._overlays
        ]
        return tuple(overlays[:max_results])
    
    def _generate_overlay_id(self, entity_id: str, invocation_id: str) -> str:
        """Generate unique overlay ID."""
        content = f"{entity_id}|{invocation_id}|{datetime.utcnow().isoformat()}"
        return f"overlay_{hashlib.sha256(content.encode()).hexdigest()[:16]}"
    
    def _generate_query_id(self) -> str:
        """Generate unique query ID."""
        return f"query_{int(datetime.utcnow().timestamp())}"
