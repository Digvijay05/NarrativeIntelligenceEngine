"""Source credibility assessment."""

from __future__ import annotations
from typing import Dict, List
from datetime import datetime
import hashlib

from ...contracts.temporal_contracts import SourceCredibility


class CredibilityAssessor:
    """Assess credibility of data sources."""
    
    def __init__(self):
        self._source_history: Dict[str, List[float]] = {}
        self._version = "1.0.0"
    
    def assess(
        self,
        source_id: str,
        accuracy_history: List[float] = None
    ) -> SourceCredibility:
        """Assess credibility of a source."""
        history = accuracy_history or self._source_history.get(source_id, [])
        
        if not history:
            credibility = 0.5  # Neutral for unknown sources
            consistency = 0.5
        else:
            credibility = sum(history) / len(history)
            
            # Consistency: how stable is the accuracy
            if len(history) > 1:
                mean = credibility
                variance = sum((h - mean) ** 2 for h in history) / len(history)
                consistency = max(0.0, 1.0 - (variance ** 0.5))
            else:
                consistency = 0.5
        
        cred_id = hashlib.sha256(
            f"{source_id}|{len(history)}".encode()
        ).hexdigest()[:12]
        
        return SourceCredibility(
            credibility_id=f"cred_{cred_id}",
            source_id=source_id,
            credibility_score=credibility,
            consistency_score=consistency,
            accuracy_history=tuple(history[-10:]),  # Keep last 10
            last_updated=datetime.now()
        )
    
    def record_accuracy(self, source_id: str, accuracy: float):
        """Record accuracy observation for a source."""
        if source_id not in self._source_history:
            self._source_history[source_id] = []
        self._source_history[source_id].append(accuracy)
