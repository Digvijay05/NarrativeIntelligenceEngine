"""Temporal coherence scoring."""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
import hashlib

from ...contracts.temporal_contracts import TemporalCoherence
from ...contracts.data_contracts import AnnotatedFragment


class CoherenceScorer:
    """Score temporal coherence of sequences."""
    
    def __init__(self, gap_penalty_rate: float = 0.01, anomaly_penalty: float = 0.1):
        self._gap_penalty_rate = gap_penalty_rate
        self._anomaly_penalty = anomaly_penalty
        self._version = "1.0.0"
    
    def score(self, fragments: List[AnnotatedFragment]) -> TemporalCoherence:
        """Score temporal coherence of fragment sequence."""
        if len(fragments) < 2:
            return self._perfect_coherence(fragments)
        
        sorted_frags = sorted(
            fragments,
            key=lambda f: f.preprocessed_fragment.temporal_features.timestamp
        )
        
        # Detect gaps and anomalies
        gaps = 0
        anomalies = 0
        total_penalty = 0.0
        
        for i in range(1, len(sorted_frags)):
            curr = sorted_frags[i].preprocessed_fragment.temporal_features
            prev = sorted_frags[i-1].preprocessed_fragment.temporal_features
            
            gap_seconds = (curr.timestamp - prev.timestamp).total_seconds()
            
            # Check for large gaps (> 1 day)
            if gap_seconds > 86400:
                gaps += 1
                total_penalty += self._gap_penalty_rate * (gap_seconds / 86400)
            
            # Check for out-of-order anomalies (shouldn't happen if sorted, but check)
            if gap_seconds < 0:
                anomalies += 1
                total_penalty += self._anomaly_penalty
        
        coherence_score = max(0.0, 1.0 - total_penalty)
        
        seq_id = hashlib.sha256(
            f"{sorted_frags[0].fragment_id}|{len(fragments)}".encode()
        ).hexdigest()[:12]
        
        return TemporalCoherence(
            coherence_id=f"coh_{seq_id}",
            sequence_id=seq_id,
            coherence_score=coherence_score,
            gaps_detected=gaps,
            anomalies_detected=anomalies,
            confidence=min(1.0, len(fragments) / 10.0),
            timestamp=datetime.now()
        )
    
    def _perfect_coherence(self, fragments: List[AnnotatedFragment]) -> TemporalCoherence:
        """Return perfect coherence for trivial sequences."""
        fid = fragments[0].fragment_id if fragments else "empty"
        return TemporalCoherence(
            coherence_id=f"coh_{fid[:12]}",
            sequence_id=fid[:12],
            coherence_score=1.0,
            gaps_detected=0,
            anomalies_detected=0,
            confidence=0.5,
            timestamp=datetime.now()
        )
