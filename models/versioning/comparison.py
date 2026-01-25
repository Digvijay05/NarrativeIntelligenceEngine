"""Version comparison utilities."""

from __future__ import annotations
from typing import Dict, List, Tuple
from datetime import datetime
import hashlib

from ..contracts.model_contracts import TrainedModelArtifact
from ..contracts.validation_contracts import ComparisonReport


class VersionComparator:
    """Compare model versions."""
    
    def __init__(self):
        self._version = "1.0.0"
    
    def compare(
        self,
        model_a: TrainedModelArtifact,
        model_b: TrainedModelArtifact,
        metrics: Dict[str, Tuple[float, float]]  # metric_name -> (value_a, value_b)
    ) -> ComparisonReport:
        """Compare two model versions."""
        metric_comparisons = tuple(
            (name, vals[0], vals[1])
            for name, vals in metrics.items()
        )
        
        # Determine winner
        a_wins = 0
        b_wins = 0
        
        for name, val_a, val_b in metric_comparisons:
            if val_a > val_b:
                a_wins += 1
            elif val_b > val_a:
                b_wins += 1
        
        if a_wins > b_wins:
            winner = model_a.model_version
        elif b_wins > a_wins:
            winner = model_b.model_version
        else:
            winner = None
        
        # Confidence based on margin
        total = a_wins + b_wins
        confidence = abs(a_wins - b_wins) / total if total > 0 else 0.5
        
        report_id = hashlib.sha256(
            f"{model_a.model_id}|{model_b.model_id}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return ComparisonReport(
            report_id=f"cmp_{report_id}",
            model_a_version=model_a.model_version,
            model_b_version=model_b.model_version,
            metric_comparisons=metric_comparisons,
            winner=winner,
            confidence=confidence,
            generated_at=datetime.now()
        )
