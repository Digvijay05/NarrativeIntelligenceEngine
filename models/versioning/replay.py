"""Replay suite for deterministic reproduction."""

from __future__ import annotations
from typing import Dict, List, Any
from datetime import datetime
import hashlib

from ..contracts.temporal_contracts import ReplayCheckpoint, ReplayResult


class ReplaySuite:
    """Suite for deterministic replay of model outputs."""
    
    def __init__(self):
        self._checkpoints: Dict[str, ReplayCheckpoint] = {}
        self._recordings: Dict[str, List[Dict]] = {}  # checkpoint_id -> events
    
    def start_recording(self, session_id: str, model_versions: Dict[str, str], seed: int = 42) -> ReplayCheckpoint:
        """Start a replay recording session."""
        checkpoint_id = hashlib.sha256(
            f"ckpt|{session_id}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        checkpoint = ReplayCheckpoint(
            checkpoint_id=f"ckpt_{checkpoint_id}",
            timestamp=datetime.now(),
            sequence_number=len(self._checkpoints),
            state_hash="initial",
            model_versions=tuple(sorted(model_versions.items())),
            random_seed=seed
        )
        
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        self._recordings[checkpoint.checkpoint_id] = []
        
        return checkpoint
    
    def record_event(self, checkpoint_id: str, event: Dict):
        """Record an event in a session."""
        if checkpoint_id in self._recordings:
            self._recordings[checkpoint_id].append({
                'timestamp': datetime.now().isoformat(),
                **event
            })
    
    def finalize_checkpoint(self, checkpoint_id: str) -> ReplayCheckpoint:
        """Finalize a checkpoint with state hash."""
        if checkpoint_id not in self._checkpoints:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        events = self._recordings.get(checkpoint_id, [])
        state_hash = hashlib.sha256(str(events).encode()).hexdigest()
        
        old = self._checkpoints[checkpoint_id]
        updated = ReplayCheckpoint(
            checkpoint_id=old.checkpoint_id,
            timestamp=old.timestamp,
            sequence_number=old.sequence_number,
            state_hash=state_hash,
            model_versions=old.model_versions,
            random_seed=old.random_seed
        )
        
        self._checkpoints[checkpoint_id] = updated
        return updated
    
    def replay_from(self, checkpoint_id: str) -> ReplayResult:
        """Replay from a checkpoint."""
        checkpoint = self._checkpoints.get(checkpoint_id)
        if not checkpoint:
            raise ValueError(f"Checkpoint {checkpoint_id} not found")
        
        events = self._recordings.get(checkpoint_id, [])
        
        # Simulate replay
        replayed_hash = hashlib.sha256(str(events).encode()).hexdigest()
        
        result_id = hashlib.sha256(
            f"replay|{checkpoint_id}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return ReplayResult(
            result_id=f"replay_{result_id}",
            checkpoint_id=checkpoint_id,
            events_replayed=len(events),
            final_state_hash=replayed_hash,
            matches_original=replayed_hash == checkpoint.state_hash,
            discrepancies=() if replayed_hash == checkpoint.state_hash else ("hash_mismatch",),
            timestamp=datetime.now()
        )
