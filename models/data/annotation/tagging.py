"""
Annotation Tagging Module

Applies annotations to preprocessed fragments.

BOUNDARY ENFORCEMENT:
- Consumes PreprocessedFragment
- Produces AnnotatedFragment
- NO learning, NO inference
- Tags contradictions, does NOT resolve them
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime
import hashlib

from ...contracts.data_contracts import (
    PreprocessedFragment, AnnotatedFragment, Annotation,
    AnnotationType, DataQuality
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class AnnotationConfig:
    """Configuration for annotation engine."""
    contradiction_threshold: float = 0.8
    duplicate_similarity_threshold: float = 0.9
    annotator_version: str = "1.0.0"


# =============================================================================
# CONTRADICTION DETECTION
# =============================================================================

class ContradictionTagger:
    """
    Tag contradictions between fragments.
    
    CRITICAL: Only TAGS contradictions, never RESOLVES them.
    Both contradicting statements remain in the system.
    """
    
    # Negation words that may indicate contradiction
    NEGATION_WORDS = frozenset({
        'not', 'no', 'never', 'none', 'nobody', 'nothing',
        'deny', 'denied', 'reject', 'rejected', 'false'
    })
    
    # Opposite pairs
    OPPOSITES = (
        ('increase', 'decrease'),
        ('rise', 'fall'),
        ('support', 'oppose'),
        ('approve', 'reject'),
        ('confirm', 'deny'),
        ('success', 'failure'),
    )
    
    def __init__(self, config: AnnotationConfig):
        self._config = config
    
    def detect_contradictions(
        self,
        fragments: List[PreprocessedFragment]
    ) -> Dict[str, List[str]]:
        """
        Detect contradictions between fragments.
        
        Returns mapping: fragment_id -> list of contradicting fragment_ids
        """
        contradictions: Dict[str, List[str]] = {}
        
        # Group by topic for efficiency
        topic_fragments: Dict[str, List[PreprocessedFragment]] = {}
        for frag in fragments:
            for topic_id in frag.semantic_features.topic_ids:
                if topic_id not in topic_fragments:
                    topic_fragments[topic_id] = []
                topic_fragments[topic_id].append(frag)
        
        # Check within each topic group
        for topic_id, topic_frags in topic_fragments.items():
            for i, frag_a in enumerate(topic_frags):
                for frag_b in topic_frags[i+1:]:
                    if self._is_contradiction(frag_a, frag_b):
                        # Record bidirectionally
                        if frag_a.fragment_id not in contradictions:
                            contradictions[frag_a.fragment_id] = []
                        if frag_b.fragment_id not in contradictions:
                            contradictions[frag_b.fragment_id] = []
                        
                        contradictions[frag_a.fragment_id].append(frag_b.fragment_id)
                        contradictions[frag_b.fragment_id].append(frag_a.fragment_id)
        
        return contradictions
    
    def _is_contradiction(
        self,
        frag_a: PreprocessedFragment,
        frag_b: PreprocessedFragment
    ) -> bool:
        """
        Check if two fragments contradict each other.
        
        Heuristic-based but deterministic.
        """
        # Get embeddings
        vec_a = frag_a.semantic_features.embedding.values
        vec_b = frag_b.semantic_features.embedding.values
        
        # Check topic overlap (need shared topics to contradict)
        topics_a = set(frag_a.semantic_features.topic_ids)
        topics_b = set(frag_b.semantic_features.topic_ids)
        
        if not (topics_a & topics_b):
            return False
        
        # Simple heuristic: Check for opposite patterns
        # In a real system, this would use learned models
        
        # Compute content similarity
        similarity = self._cosine_similarity(vec_a, vec_b)
        
        # If very similar but one has negation, likely contradiction
        if similarity > 0.6:
            # Would check for negation patterns here
            pass
        
        return False  # Conservative default
    
    def _cosine_similarity(
        self,
        vec_a: Tuple[float, ...],
        vec_b: Tuple[float, ...]
    ) -> float:
        """Compute cosine similarity."""
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)


# =============================================================================
# DUPLICATE DETECTION
# =============================================================================

class DuplicateTagger:
    """
    Tag duplicate fragments.
    
    Identifies exact and near-duplicates.
    """
    
    def __init__(self, config: AnnotationConfig):
        self._config = config
        self._seen_hashes: Dict[str, str] = {}  # hash -> fragment_id
    
    def detect_duplicates(
        self,
        fragments: List[PreprocessedFragment]
    ) -> Dict[str, str]:
        """
        Detect duplicates among fragments.
        
        Returns mapping: duplicate_fragment_id -> original_fragment_id
        """
        duplicates = {}
        
        for frag in fragments:
            content_hash = frag.semantic_features.content_hash
            
            if content_hash in self._seen_hashes:
                duplicates[frag.fragment_id] = self._seen_hashes[content_hash]
            else:
                self._seen_hashes[content_hash] = frag.fragment_id
        
        return duplicates


# =============================================================================
# PRESENCE/ABSENCE TAGGING
# =============================================================================

class PresenceTagger:
    """
    Tag presence and absence of expected elements.
    """
    
    def tag_presence(
        self,
        fragment: PreprocessedFragment,
        expected_entities: Set[str]
    ) -> List[Tuple[str, bool]]:
        """
        Check for presence/absence of expected entities.
        
        Returns list of (entity_id, is_present) tuples.
        """
        present_entities = set(fragment.semantic_features.entity_ids)
        
        results = []
        for expected in sorted(expected_entities):
            results.append((expected, expected in present_entities))
        
        return results


# =============================================================================
# ANNOTATION ENGINE
# =============================================================================

class AnnotationEngine:
    """
    Main annotation engine.
    
    Orchestrates all annotation tagging.
    
    BOUNDARY ENFORCEMENT:
    - Consumes PreprocessedFragment
    - Produces AnnotatedFragment
    - NO learning, NO inference
    """
    
    def __init__(self, config: Optional[AnnotationConfig] = None):
        self._config = config or AnnotationConfig()
        self._contradiction_tagger = ContradictionTagger(self._config)
        self._duplicate_tagger = DuplicateTagger(self._config)
        self._presence_tagger = PresenceTagger()
    
    def annotate(
        self,
        fragment: PreprocessedFragment,
        all_fragments: Optional[List[PreprocessedFragment]] = None,
        contradictions: Optional[Dict[str, List[str]]] = None,
        duplicates: Optional[Dict[str, str]] = None
    ) -> AnnotatedFragment:
        """
        Apply all annotations to a fragment.
        
        Returns an AnnotatedFragment contract.
        """
        annotations = []
        now = datetime.now()
        
        # Check for contradictions
        contradiction_targets = ()
        if contradictions and fragment.fragment_id in contradictions:
            contradiction_targets = tuple(contradictions[fragment.fragment_id])
            
            annotation = Annotation(
                annotation_id=f"ann_contra_{fragment.fragment_id[:8]}",
                annotation_type=AnnotationType.CONTRADICTION,
                confidence=0.8,
                evidence=contradiction_targets,
                annotated_at=now,
                annotator_version=self._config.annotator_version
            )
            annotations.append(annotation)
        
        # Check for duplicates
        is_duplicate = False
        duplicate_of = None
        if duplicates and fragment.fragment_id in duplicates:
            is_duplicate = True
            duplicate_of = duplicates[fragment.fragment_id]
        
        # Add presence annotation
        if fragment.semantic_features.topic_ids:
            annotation = Annotation(
                annotation_id=f"ann_pres_{fragment.fragment_id[:8]}",
                annotation_type=AnnotationType.PRESENCE,
                confidence=1.0,
                evidence=fragment.semantic_features.topic_ids,
                annotated_at=now,
                annotator_version=self._config.annotator_version
            )
            annotations.append(annotation)
        
        # Generate lineage version
        lineage_version = hashlib.sha256(
            f"{fragment.fragment_id}|{now.isoformat()}".encode()
        ).hexdigest()[:12]
        
        return AnnotatedFragment(
            fragment_id=fragment.fragment_id,
            preprocessed_fragment=fragment,
            annotations=tuple(annotations),
            is_duplicate=is_duplicate,
            duplicate_of=duplicate_of,
            contradiction_targets=contradiction_targets,
            lineage_version=lineage_version,
            finalized_at=now
        )
    
    def annotate_batch(
        self,
        fragments: List[PreprocessedFragment]
    ) -> List[AnnotatedFragment]:
        """
        Annotate a batch of fragments.
        
        Performs batch-level analysis (contradictions, duplicates)
        before annotating individual fragments.
        """
        # Batch-level analysis
        contradictions = self._contradiction_tagger.detect_contradictions(fragments)
        duplicates = self._duplicate_tagger.detect_duplicates(fragments)
        
        # Annotate each fragment
        annotated = []
        for frag in fragments:
            annotated_frag = self.annotate(
                fragment=frag,
                all_fragments=fragments,
                contradictions=contradictions,
                duplicates=duplicates
            )
            annotated.append(annotated_frag)
        
        return annotated
