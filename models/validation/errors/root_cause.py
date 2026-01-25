"""Root cause analysis."""

from __future__ import annotations
from typing import List, Dict
from datetime import datetime
import hashlib

from ...contracts.validation_contracts import RootCauseAnalysis, ErrorCategory


class RootCauseAnalyzer:
    """Analyze root causes of error patterns."""
    
    def __init__(self):
        self._analyses: Dict[str, RootCauseAnalysis] = {}
    
    def analyze(self, category: ErrorCategory) -> RootCauseAnalysis:
        """Analyze root cause for an error category."""
        root_cause, factors = self._infer_root_cause(category)
        recommendation = self._generate_recommendation(root_cause)
        
        analysis_id = hashlib.sha256(
            f"rca|{category.category_id}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        analysis = RootCauseAnalysis(
            analysis_id=f"rca_{analysis_id}",
            failure_pattern=category.category_name,
            root_cause=root_cause,
            contributing_factors=factors,
            affected_count=category.count,
            recommendation=recommendation,
            confidence=min(0.9, category.count / 100.0 + 0.3),
            analyzed_at=datetime.now()
        )
        
        self._analyses[category.category_id] = analysis
        return analysis
    
    def _infer_root_cause(self, category: ErrorCategory) -> tuple:
        """Infer root cause from category."""
        name = category.category_name.lower()
        
        if 'timeout' in name:
            return (
                "Resource contention or slow model inference",
                ("high_load", "model_complexity", "resource_limits")
            )
        elif 'validation' in name:
            return (
                "Input data quality issues",
                ("schema_mismatch", "missing_fields", "invalid_values")
            )
        elif 'model' in name:
            return (
                "Model internal error or incompatibility",
                ("version_mismatch", "corrupted_weights", "numerical_instability")
            )
        else:
            return (
                "Unknown root cause - requires investigation",
                ("insufficient_data",)
            )
    
    def _generate_recommendation(self, root_cause: str) -> str:
        """Generate recommendation based on root cause."""
        if 'resource' in root_cause.lower():
            return "Consider scaling compute resources or optimizing model"
        elif 'quality' in root_cause.lower():
            return "Review input validation and data preprocessing"
        elif 'model' in root_cause.lower():
            return "Verify model version compatibility and weights integrity"
        else:
            return "Investigate error patterns and collect more diagnostics"
    
    def get_all_analyses(self) -> List[RootCauseAnalysis]:
        """Get all root cause analyses."""
        return list(self._analyses.values())
