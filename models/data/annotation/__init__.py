"""
Annotation Subpackage

Contains tagging and marking logic for:
- Contradiction detection
- Presence/absence flags
- Divergence markers
"""

from .tagging import AnnotationEngine, ContradictionTagger
from .markers import DivergenceMarker

__all__ = ['AnnotationEngine', 'ContradictionTagger', 'DivergenceMarker']
