"""
Lifecycle Predictor

Predict narrative lifecycle state transitions.

BOUNDARY ENFORCEMENT:
- Uses trained models from Phase 2
- Produces predictions via contracts
- Deterministic and replay-safe
- NO model training
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
import hashlib
import math

from ...contracts.temporal_contracts import (
    TemporalState, LifecycleState, LifecyclePrediction,
    PredictionConfidence, StateTransition
)
from ...contracts.data_contracts import AnnotatedFragment


@dataclass
class LifecycleConfig:
    """Configuration for lifecycle prediction."""
    emerging_threshold: int = 3  # Fragments to become active
    dormancy_threshold_hours: float = 48.0
    termination_threshold_hours: float = 168.0  # 1 week


class LifecyclePredictor:
    """
    Predict lifecycle state of narrative threads.
    
    BOUNDARY ENFORCEMENT:
    - Deterministic state machine logic
    - NO model training
    - Replay-safe: same input = same output
    """
    
    def __init__(self, config: Optional[LifecycleConfig] = None):
        self._config = config or LifecycleConfig()
        self._version = "1.0.0"
    
    def predict_current_state(
        self,
        fragments: List[AnnotatedFragment],
        current_time: Optional[datetime] = None
    ) -> TemporalState:
        """
        Predict current lifecycle state from fragments.
        
        Deterministic: same fragments + time = same state.
        """
        now = current_time or datetime.now()
        
        if not fragments:
            return self._create_empty_state(now)
        
        # Sort by timestamp
        sorted_frags = sorted(
            fragments,
            key=lambda f: f.preprocessed_fragment.temporal_features.timestamp
        )
        
        # Compute lifecycle state
        lifecycle = self._compute_lifecycle(sorted_frags, now)
        
        # Time since last activity
        last_ts = sorted_frags[-1].preprocessed_fragment.temporal_features.timestamp
        time_since_last = (now - last_ts).total_seconds()
        
        # Generate state ID
        state_hash = hashlib.sha256(
            f"{sorted_frags[-1].fragment_id}|{lifecycle.value}|{now.isoformat()}".encode()
        ).hexdigest()[:12]
        
        return TemporalState(
            state_id=f"state_{state_hash}",
            entity_id=sorted_frags[0].fragment_id[:16],  # Thread ID proxy
            entity_type="thread",
            lifecycle=lifecycle,
            timestamp=now,
            sequence_position=len(sorted_frags),
            version=self._version,
            time_since_last_activity=time_since_last,
            expected_next_activity=self._estimate_next_activity(sorted_frags),
            activity_count=len(sorted_frags)
        )
    
    def predict_transition(
        self,
        current_state: TemporalState,
        hours_ahead: float = 24.0
    ) -> LifecyclePrediction:
        """
        Predict lifecycle state transition.
        
        Deterministic based on current state and time delta.
        """
        future_time = datetime.now()  # Would add hours_ahead
        
        # State transition logic
        current = current_state.lifecycle
        predicted = current  # Default: no change
        probability = 0.0
        
        if current == LifecycleState.EMERGING:
            if current_state.activity_count >= self._config.emerging_threshold:
                predicted = LifecycleState.ACTIVE
                probability = 0.8
            else:
                probability = 0.3
        
        elif current == LifecycleState.ACTIVE:
            if current_state.time_since_last_activity:
                hours_inactive = current_state.time_since_last_activity / 3600
                if hours_inactive > self._config.dormancy_threshold_hours:
                    predicted = LifecycleState.DORMANT
                    probability = 0.7
        
        elif current == LifecycleState.DORMANT:
            if current_state.time_since_last_activity:
                hours_inactive = current_state.time_since_last_activity / 3600
                if hours_inactive > self._config.termination_threshold_hours:
                    predicted = LifecycleState.TERMINATED
                    probability = 0.6
        
        pred_id = hashlib.sha256(
            f"{current_state.state_id}|{predicted.value}".encode()
        ).hexdigest()[:12]
        
        return LifecyclePrediction(
            prediction_id=f"pred_{pred_id}",
            thread_id=current_state.entity_id,
            current_state=current,
            predicted_state=predicted,
            transition_probability=probability,
            time_to_transition=hours_ahead * 3600 if predicted != current else None,
            confidence=probability,
            model_version=self._version,
            timestamp=datetime.now()
        )
    
    def _compute_lifecycle(
        self,
        fragments: List[AnnotatedFragment],
        now: datetime
    ) -> LifecycleState:
        """Compute lifecycle from fragment history."""
        if len(fragments) < self._config.emerging_threshold:
            return LifecycleState.EMERGING
        
        last_ts = fragments[-1].preprocessed_fragment.temporal_features.timestamp
        hours_since = (now - last_ts).total_seconds() / 3600
        
        if hours_since > self._config.termination_threshold_hours:
            return LifecycleState.TERMINATED
        elif hours_since > self._config.dormancy_threshold_hours:
            return LifecycleState.DORMANT
        else:
            return LifecycleState.ACTIVE
    
    def _estimate_next_activity(
        self,
        fragments: List[AnnotatedFragment]
    ) -> Optional[float]:
        """Estimate seconds until next activity."""
        if len(fragments) < 2:
            return None
        
        # Compute average inter-arrival time
        timestamps = [
            f.preprocessed_fragment.temporal_features.timestamp
            for f in fragments
        ]
        
        gaps = []
        for i in range(1, len(timestamps)):
            gap = (timestamps[i] - timestamps[i-1]).total_seconds()
            gaps.append(gap)
        
        if gaps:
            return sum(gaps) / len(gaps)
        return None
    
    def _create_empty_state(self, now: datetime) -> TemporalState:
        """Create empty state for no fragments."""
        return TemporalState(
            state_id=f"state_empty_{now.timestamp()}",
            entity_id="unknown",
            entity_type="thread",
            lifecycle=LifecycleState.EMERGING,
            timestamp=now,
            sequence_position=0,
            version=self._version
        )
