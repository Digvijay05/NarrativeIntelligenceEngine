"""
Divergence Risk Predictor

Predict risk of narrative divergence.

BOUNDARY ENFORCEMENT:
- Deterministic risk assessment
- NO model training
- Replay-safe
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Set
from datetime import datetime
import hashlib

from ...contracts.temporal_contracts import DivergencePrediction
from ...contracts.data_contracts import AnnotatedFragment, AnnotationType


@dataclass
class DivergenceRiskConfig:
    """Configuration for divergence risk prediction."""
    contradiction_weight: float = 0.4
    topic_diversity_weight: float = 0.3
    temporal_gap_weight: float = 0.3
    high_risk_threshold: float = 0.7


class DivergenceRiskPredictor:
    """
    Predict divergence risk for narrative threads.
    
    BOUNDARY ENFORCEMENT:
    - Deterministic risk scoring
    - NO model training
    - Replay-safe
    """
    
    def __init__(self, config: Optional[DivergenceRiskConfig] = None):
        self._config = config or DivergenceRiskConfig()
        self._version = "1.0.0"
    
    def predict(
        self,
        fragments: List[AnnotatedFragment]
    ) -> DivergencePrediction:
        """
        Predict divergence risk from fragment analysis.
        
        Deterministic: same fragments = same prediction.
        """
        if not fragments:
            return self._empty_prediction()
        
        # Compute risk factors
        contradiction_risk = self._assess_contradiction_risk(fragments)
        diversity_risk = self._assess_topic_diversity(fragments)
        temporal_risk = self._assess_temporal_gaps(fragments)
        
        # Combined probability
        probability = (
            self._config.contradiction_weight * contradiction_risk +
            self._config.topic_diversity_weight * diversity_risk +
            self._config.temporal_gap_weight * temporal_risk
        )
        
        # Collect risk factors
        risk_factors = []
        if contradiction_risk > 0.5:
            risk_factors.append("high_contradiction_rate")
        if diversity_risk > 0.5:
            risk_factors.append("topic_fragmentation")
        if temporal_risk > 0.5:
            risk_factors.append("temporal_irregularity")
        
        # Estimate branches
        potential_branches = self._estimate_branch_count(fragments)
        
        pred_id = hashlib.sha256(
            f"{fragments[-1].fragment_id}|{probability:.4f}".encode()
        ).hexdigest()[:12]
        
        return DivergencePrediction(
            prediction_id=f"divr_{pred_id}",
            thread_id=fragments[0].fragment_id[:16],
            divergence_probability=probability,
            potential_branches=potential_branches,
            risk_factors=tuple(risk_factors),
            model_version=self._version,
            timestamp=datetime.now()
        )
    
    def _assess_contradiction_risk(
        self,
        fragments: List[AnnotatedFragment]
    ) -> float:
        """Assess risk from contradictions."""
        if not fragments:
            return 0.0
        
        contradiction_count = 0
        for frag in fragments:
            contradiction_count += len(frag.contradiction_targets)
        
        # Normalize by fragment count
        rate = contradiction_count / (len(fragments) * 2)  # Each contradiction counted twice
        return min(1.0, rate)
    
    def _assess_topic_diversity(
        self,
        fragments: List[AnnotatedFragment]
    ) -> float:
        """Assess risk from topic fragmentation."""
        if len(fragments) < 2:
            return 0.0
        
        # Count unique topics
        all_topics: Set[str] = set()
        for frag in fragments:
            all_topics.update(frag.preprocessed_fragment.semantic_features.topic_ids)
        
        # High diversity relative to fragment count = higher risk
        if len(fragments) == 0:
            return 0.0
        
        diversity_ratio = len(all_topics) / len(fragments)
        return min(1.0, diversity_ratio)
    
    def _assess_temporal_gaps(
        self,
        fragments: List[AnnotatedFragment]
    ) -> float:
        """Assess risk from temporal irregularities."""
        if len(fragments) < 2:
            return 0.0
        
        sorted_frags = sorted(
            fragments,
            key=lambda f: f.preprocessed_fragment.temporal_features.timestamp
        )
        
        # Compute gap variance
        gaps = []
        for i in range(1, len(sorted_frags)):
            gap = (
                sorted_frags[i].preprocessed_fragment.temporal_features.timestamp -
                sorted_frags[i-1].preprocessed_fragment.temporal_features.timestamp
            ).total_seconds()
            gaps.append(gap)
        
        if not gaps or len(gaps) == 1:
            return 0.0
        
        avg = sum(gaps) / len(gaps)
        if avg == 0:
            return 0.0
        
        variance = sum((g - avg) ** 2 for g in gaps) / len(gaps)
        std = variance ** 0.5
        
        # Coefficient of variation
        cv = std / avg if avg > 0 else 0
        return min(1.0, cv / 2)  # Normalize
    
    def _estimate_branch_count(
        self,
        fragments: List[AnnotatedFragment]
    ) -> int:
        """Estimate potential number of divergent branches."""
        # Count topic clusters
        topics: Set[str] = set()
        for frag in fragments:
            topics.update(frag.preprocessed_fragment.semantic_features.topic_ids)
        
        # Each distinct topic could be a branch
        return max(1, len(topics))
    
    def _empty_prediction(self) -> DivergencePrediction:
        """Create empty prediction."""
        return DivergencePrediction(
            prediction_id=f"divr_empty_{datetime.now().timestamp()}",
            thread_id="unknown",
            divergence_probability=0.0,
            potential_branches=0,
            risk_factors=(),
            model_version=self._version,
            timestamp=datetime.now()
        )
