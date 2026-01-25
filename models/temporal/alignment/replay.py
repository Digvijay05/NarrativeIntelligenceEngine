"""State replay for deterministic reproduction."""

from __future__ import annotations
from typing import List, Dict
from datetime import datetime
import hashlib

from ...contracts.temporal_contracts import (
    ReplayCheckpoint, ReplayResult, TemporalState, LifecycleState
)
from ...contracts.data_contracts import AnnotatedFragment


class StateReplayer:
    """Replay state from checkpoints for deterministic reproduction."""
    
    def __init__(self):
        self._checkpoints: Dict[str, ReplayCheckpoint] = {}
        self._version = "1.0.0"
    
    def create_checkpoint(
        self,
        states: List[TemporalState],
        model_versions: Dict[str, str],
        random_seed: int = 42
    ) -> ReplayCheckpoint:
        """Create a checkpoint from current states."""
        state_content = "|".join(s.state_id for s in sorted(states, key=lambda x: x.state_id))
        state_hash = hashlib.sha256(state_content.encode()).hexdigest()
        
        checkpoint_id = hashlib.sha256(
            f"{datetime.now().isoformat()}|{state_hash[:16]}".encode()
        ).hexdigest()[:12]
        
        checkpoint = ReplayCheckpoint(
            checkpoint_id=f"ckpt_{checkpoint_id}",
            timestamp=datetime.now(),
            sequence_number=len(self._checkpoints),
            state_hash=state_hash,
            model_versions=tuple(sorted(model_versions.items())),
            random_seed=random_seed
        )
        
        self._checkpoints[checkpoint.checkpoint_id] = checkpoint
        return checkpoint
    
    def replay_from_checkpoint(
        self,
        checkpoint: ReplayCheckpoint,
        current_states: List[TemporalState]
    ) -> ReplayResult:
        """Replay from checkpoint and verify consistency."""
        # Compute current state hash
        state_content = "|".join(
            s.state_id for s in sorted(current_states, key=lambda x: x.state_id)
        )
        current_hash = hashlib.sha256(state_content.encode()).hexdigest()
        
        matches = current_hash == checkpoint.state_hash
        
        discrepancies = ()
        if not matches:
            discrepancies = (
                f"Hash mismatch: expected {checkpoint.state_hash[:16]}, got {current_hash[:16]}",
            )
        
        result_id = hashlib.sha256(
            f"{checkpoint.checkpoint_id}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return ReplayResult(
            result_id=f"replay_{result_id}",
            checkpoint_id=checkpoint.checkpoint_id,
            events_replayed=len(current_states),
            final_state_hash=current_hash,
            matches_original=matches,
            discrepancies=discrepancies,
            timestamp=datetime.now()
        )
    
    def get_checkpoint(self, checkpoint_id: str) -> ReplayCheckpoint:
        """Retrieve a checkpoint by ID."""
        return self._checkpoints.get(checkpoint_id)
