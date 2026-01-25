"""Error categorization."""

from __future__ import annotations
from typing import Dict, List
from datetime import datetime
import hashlib

from ...contracts.validation_contracts import ErrorCategory, ErrorSeverity, InferenceFailure


class ErrorCategorizer:
    """Categorize errors from inference failures."""
    
    def __init__(self):
        self._categories: Dict[str, ErrorCategory] = {}
        self._failure_history: List[InferenceFailure] = []
    
    def record_failure(self, failure: InferenceFailure):
        """Record an inference failure."""
        self._failure_history.append(failure)
        self._update_category(failure)
    
    def _update_category(self, failure: InferenceFailure):
        """Update category from failure."""
        category_name = self._infer_category(failure.failure_type)
        
        if category_name not in self._categories:
            cat_id = hashlib.sha256(category_name.encode()).hexdigest()[:12]
            self._categories[category_name] = ErrorCategory(
                category_id=f"cat_{cat_id}",
                category_name=category_name,
                description=f"Errors of type: {category_name}",
                severity=self._infer_severity(failure.failure_type),
                count=0,
                first_occurrence=failure.occurred_at,
                last_occurrence=failure.occurred_at,
                example_ids=()
            )
        
        old = self._categories[category_name]
        examples = old.example_ids + (failure.failure_id,) if len(old.example_ids) < 5 else old.example_ids
        
        self._categories[category_name] = ErrorCategory(
            category_id=old.category_id,
            category_name=old.category_name,
            description=old.description,
            severity=old.severity,
            count=old.count + 1,
            first_occurrence=old.first_occurrence,
            last_occurrence=failure.occurred_at,
            example_ids=examples
        )
    
    def _infer_category(self, failure_type: str) -> str:
        """Infer category from failure type."""
        if 'timeout' in failure_type.lower():
            return 'timeout_errors'
        elif 'validation' in failure_type.lower():
            return 'validation_errors'
        elif 'model' in failure_type.lower():
            return 'model_errors'
        else:
            return 'unknown_errors'
    
    def _infer_severity(self, failure_type: str) -> ErrorSeverity:
        """Infer severity from failure type."""
        if 'critical' in failure_type.lower():
            return ErrorSeverity.CRITICAL
        elif 'error' in failure_type.lower():
            return ErrorSeverity.HIGH
        else:
            return ErrorSeverity.MEDIUM
    
    def get_categories(self) -> List[ErrorCategory]:
        """Get all error categories."""
        return list(self._categories.values())
