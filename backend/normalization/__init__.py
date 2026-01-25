"""
Normalization & Canonicalization Layer

RESPONSIBILITY: Transform raw events into normalized, canonical fragments
ALLOWED INPUTS: RawIngestionEvent from ingestion layer
OUTPUTS: NormalizedFragment (immutable)

WHAT THIS LAYER MUST NOT DO:
============================
- Store data persistently
- Manage threads or narrative state
- Make truth judgments about content
- Rank importance or priority
- Resolve contradictions (only tag them)
- Access ingestion layer internals
- Access core engine or storage internals

BOUNDARY ENFORCEMENT:
=====================
This layer ONLY consumes RawIngestionEvent and produces NormalizedFragment.
Contradictions are TAGGED, never RESOLVED - we represent conflicting data.

REFACTORING FROM PREVIOUS CODE:
===============================
Previous coupling risks eliminated:
1. OLD: Duplicate detection was in ingestion.py (wrong layer)
   NEW: Dedicated DuplicateDetector in normalization layer
2. OLD: Language detection was in ingestion.py (wrong layer)  
   NEW: Dedicated LanguageDetector in normalization layer
3. OLD: Topic assignment happened during ingestion
   NEW: TopicClassifier in normalization layer
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional, Tuple
import re
import hashlib
import json

# ONLY import from contracts - never from other layers' implementations
from ..contracts.base import (
    FragmentId, Timestamp, SourceMetadata, ContentSignature,
    CanonicalTopic, CanonicalEntity, Error, ErrorCode
)
from ..contracts.events import (
    RawIngestionEvent, NormalizedFragment, NormalizationResult,
    DuplicateInfo, DuplicateStatus, ContradictionInfo, ContradictionStatus,
    AuditLogEntry, AuditEventType
)


# =============================================================================
# LANGUAGE DETECTION (Deterministic)
# =============================================================================

class LanguageDetector:
    """
    Deterministic language detection.
    
    Uses word frequency analysis for consistent, reproducible results.
    No probabilistic models - same input always produces same output.
    """
    
    # Language word sets (frozen for immutability)
    _ENGLISH_WORDS: frozenset = frozenset({
        'the', 'and', 'or', 'but', 'for', 'not', 'with', 'this', 'that', 
        'which', 'have', 'from', 'they', 'been', 'were', 'said', 'each'
    })
    _SPANISH_WORDS: frozenset = frozenset({
        'el', 'la', 'de', 'que', 'y', 'en', 'un', 'se', 'por', 'del',
        'los', 'las', 'con', 'para', 'una', 'como', 'pero'
    })
    _FRENCH_WORDS: frozenset = frozenset({
        'le', 'la', 'de', 'et', 'ou', 'mais', 'pour', 'avec', 'ce', 'qui',
        'les', 'des', 'dans', 'est', 'que', 'une', 'sur'
    })
    
    def detect(self, text: str) -> Optional[str]:
        """
        Detect language from text.
        
        Returns ISO 639-1 language code or None if undetermined.
        Deterministic: same text always returns same result.
        """
        if not text or not text.strip():
            return None
        
        # Tokenize (simple word extraction)
        words = frozenset(re.findall(r'\b[a-zA-Z]+\b', text.lower()))
        
        if not words:
            return None
        
        # Count matches for each language
        scores = {
            'en': len(words & self._ENGLISH_WORDS),
            'es': len(words & self._SPANISH_WORDS),
            'fr': len(words & self._FRENCH_WORDS),
        }
        
        # Return language with highest score, or 'en' as default if tied at 0
        max_score = max(scores.values())
        if max_score == 0:
            return 'en'  # Default to English
        
        # Deterministic tie-breaking: alphabetical order
        for lang in sorted(scores.keys()):
            if scores[lang] == max_score:
                return lang
        
        return 'en'


# =============================================================================
# DUPLICATE DETECTION (Deterministic)
# =============================================================================

class DuplicateDetector:
    """
    Deterministic duplicate detection using content hashing and similarity.
    
    Maintains index of seen content for O(1) exact duplicate detection
    and O(n) near-duplicate detection.
    """
    
    def __init__(self, similarity_threshold: float = 0.8):
        self._exact_hashes: Dict[str, FragmentId] = {}
        self._content_index: Dict[str, Tuple[FragmentId, frozenset]] = {}
        self._similarity_threshold = similarity_threshold
    
    def check(self, content: str, content_hash: str) -> DuplicateInfo:
        """
        Check if content is a duplicate.
        
        Returns DuplicateInfo with status and reference to original if duplicate.
        Deterministic: same content always returns same duplicate status.
        """
        # Check exact duplicate first
        if content_hash in self._exact_hashes:
            return DuplicateInfo(
                status=DuplicateStatus.EXACT_DUPLICATE,
                original_fragment_id=self._exact_hashes[content_hash],
                similarity_score=1.0
            )
        
        # Check near duplicates using Jaccard similarity
        content_tokens = self._tokenize(content)
        
        for stored_hash, (fragment_id, stored_tokens) in self._content_index.items():
            similarity = self._jaccard_similarity(content_tokens, stored_tokens)
            if similarity >= self._similarity_threshold:
                return DuplicateInfo(
                    status=DuplicateStatus.NEAR_DUPLICATE,
                    original_fragment_id=fragment_id,
                    similarity_score=similarity
                )
        
        return DuplicateInfo(status=DuplicateStatus.UNIQUE)
    
    def register(self, fragment_id: FragmentId, content: str, content_hash: str):
        """Register content for future duplicate detection."""
        self._exact_hashes[content_hash] = fragment_id
        self._content_index[content_hash] = (fragment_id, self._tokenize(content))
    
    def _tokenize(self, text: str) -> frozenset:
        """Tokenize text into frozen set of lowercase words."""
        return frozenset(re.findall(r'\b\w+\b', text.lower()))
    
    def _jaccard_similarity(self, set1: frozenset, set2: frozenset) -> float:
        """Compute Jaccard similarity between two token sets."""
        if not set1 and not set2:
            return 1.0
        if not set1 or not set2:
            return 0.0
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union


# =============================================================================
# CONTRADICTION DETECTION (Tags, never resolves)
# =============================================================================

class ContradictionDetector:
    """
    Detect contradictions between fragments.
    
    CRITICAL: This class TAGS contradictions, it does NOT resolve them.
    Both contradicting statements are preserved in the system.
    
    Contradiction detection is heuristic-based but deterministic.
    """
    
    # Negation indicators
    _NEGATION_WORDS: frozenset = frozenset({
        'not', 'no', 'never', 'none', 'nobody', 'nothing', 'neither',
        'nowhere', 'deny', 'denied', 'denies', 'reject', 'rejected'
    })
    
    # Contradiction patterns (simplified for determinism)
    _OPPOSITE_PAIRS: Tuple[Tuple[str, str], ...] = (
        ('increase', 'decrease'),
        ('rise', 'fall'),
        ('grow', 'shrink'),
        ('approve', 'reject'),
        ('support', 'oppose'),
        ('confirm', 'deny'),
        ('agree', 'disagree'),
        ('true', 'false'),
        ('success', 'failure'),
    )
    
    def __init__(self):
        self._content_index: Dict[str, Tuple[FragmentId, frozenset, frozenset]] = {}
    
    def check(
        self, 
        content: str, 
        topics: Tuple[CanonicalTopic, ...]
    ) -> ContradictionInfo:
        """
        Check if content contradicts any previously seen content.
        
        Returns ContradictionInfo with status and references if contradiction found.
        DOES NOT RESOLVE - both sides of contradiction remain valid.
        """
        content_tokens = self._tokenize(content)
        content_negations = content_tokens & self._NEGATION_WORDS
        topic_ids = frozenset(t.topic_id for t in topics)
        
        contradicting_ids = []
        
        for stored_hash, (fragment_id, stored_tokens, stored_topics) in self._content_index.items():
            # Only check within same topics
            if not (topic_ids & stored_topics):
                continue
            
            # Check for contradiction patterns
            if self._detect_contradiction(content_tokens, content_negations, stored_tokens):
                contradicting_ids.append(fragment_id)
        
        if contradicting_ids:
            return ContradictionInfo(
                status=ContradictionStatus.CONTRADICTION_DETECTED,
                contradicting_fragment_ids=tuple(contradicting_ids),
                contradiction_description="Content appears to contradict existing fragments"
            )
        
        return ContradictionInfo(status=ContradictionStatus.NO_CONTRADICTION)
    
    def register(
        self, 
        fragment_id: FragmentId, 
        content: str, 
        topics: Tuple[CanonicalTopic, ...]
    ):
        """Register content for future contradiction detection."""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        topic_ids = frozenset(t.topic_id for t in topics)
        self._content_index[content_hash] = (
            fragment_id, 
            self._tokenize(content),
            topic_ids
        )
    
    def _tokenize(self, text: str) -> frozenset:
        """Tokenize text into frozen set of lowercase words."""
        return frozenset(re.findall(r'\b\w+\b', text.lower()))
    
    def _detect_contradiction(
        self, 
        tokens1: frozenset, 
        negations1: frozenset,
        tokens2: frozenset
    ) -> bool:
        """
        Detect if two token sets represent contradicting statements.
        
        Simplified heuristic:
        1. If one has negation and significant overlap, likely contradiction
        2. If opposite word pairs are present, likely contradiction
        """
        # Check negation-based contradiction
        negations2 = tokens2 & self._NEGATION_WORDS
        if (negations1 and not negations2) or (negations2 and not negations1):
            # One has negation, one doesn't - check overlap
            non_neg_overlap = (tokens1 - self._NEGATION_WORDS) & (tokens2 - self._NEGATION_WORDS)
            if len(non_neg_overlap) >= 3:  # Significant shared content
                return True
        
        # Check opposite pairs
        for word1, word2 in self._OPPOSITE_PAIRS:
            if (word1 in tokens1 and word2 in tokens2) or \
               (word2 in tokens1 and word1 in tokens2):
                return True
        
        return False


# =============================================================================
# TOPIC CLASSIFICATION (Deterministic)
# =============================================================================

class TopicClassifier:
    """
    Classify content into canonical topics.
    
    Uses keyword-based classification for deterministic results.
    No ML models - same input always produces same topics.
    """
    
    def __init__(self):
        self._topic_keywords: Dict[str, frozenset] = {}
        self._topic_registry: Dict[str, CanonicalTopic] = {}
        self._register_default_topics()
    
    def _register_default_topics(self):
        """Register default topic classifications."""
        default_topics = {
            'climate_policy': frozenset({
                'climate', 'carbon', 'emissions', 'environment', 'green',
                'renewable', 'sustainability', 'pollution', 'warming'
            }),
            'technology': frozenset({
                'tech', 'technology', 'software', 'hardware', 'digital',
                'ai', 'artificial', 'intelligence', 'machine', 'algorithm'
            }),
            'finance': frozenset({
                'finance', 'financial', 'money', 'bank', 'investment',
                'stock', 'market', 'economic', 'economy', 'trade'
            }),
            'politics': frozenset({
                'government', 'political', 'politics', 'election', 'vote',
                'party', 'congress', 'senate', 'legislation', 'policy'
            }),
            'health': frozenset({
                'health', 'medical', 'medicine', 'hospital', 'doctor',
                'patient', 'treatment', 'disease', 'vaccine', 'healthcare'
            }),
        }
        
        for topic_id, keywords in default_topics.items():
            self._topic_keywords[topic_id] = keywords
            self._topic_registry[topic_id] = CanonicalTopic(
                topic_id=topic_id,
                canonical_name=topic_id.replace('_', ' ').title(),
                aliases=frozenset()
            )
    
    def register_topic(self, topic: CanonicalTopic, keywords: frozenset):
        """Register a custom topic with keywords."""
        self._topic_registry[topic.topic_id] = topic
        self._topic_keywords[topic.topic_id] = keywords
    
    def classify(self, content: str) -> Tuple[CanonicalTopic, ...]:
        """
        Classify content into matching topics.
        
        Returns tuple of matching CanonicalTopic objects.
        Deterministic: same content always returns same topics.
        """
        content_tokens = frozenset(re.findall(r'\b\w+\b', content.lower()))
        
        matches = []
        for topic_id, keywords in self._topic_keywords.items():
            overlap = content_tokens & keywords
            if len(overlap) >= 1:  # At least one keyword match
                matches.append((len(overlap), topic_id))
        
        # Sort by match count (descending), then by topic_id (ascending) for determinism
        matches.sort(key=lambda x: (-x[0], x[1]))
        
        return tuple(self._topic_registry[topic_id] for _, topic_id in matches)


# =============================================================================
# ENTITY EXTRACTION (Deterministic)
# =============================================================================

class EntityExtractor:
    """
    Extract canonical entities from content.
    
    Uses pattern-based extraction for deterministic results.
    """
    
    def __init__(self):
        self._entity_patterns: Dict[str, str] = {
            'organization': r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',
            'person': r'\b(?:Mr\.|Mrs\.|Ms\.|Dr\.)\s+[A-Z][a-z]+\b',
        }
        self._known_entities: Dict[str, CanonicalEntity] = {}
    
    def extract(self, content: str) -> Tuple[CanonicalEntity, ...]:
        """
        Extract entities from content.
        
        Returns tuple of CanonicalEntity objects found.
        Deterministic: same content always returns same entities.
        """
        entities = []
        
        for entity_type, pattern in self._entity_patterns.items():
            matches = re.findall(pattern, content)
            for match in matches:
                entity_id = hashlib.sha256(
                    f"{entity_type}:{match.lower()}".encode()
                ).hexdigest()[:12]
                
                entity = CanonicalEntity(
                    entity_id=entity_id,
                    canonical_name=match,
                    entity_type=entity_type,
                    aliases=frozenset()
                )
                entities.append(entity)
        
        # Sort for determinism
        entities.sort(key=lambda e: (e.entity_type, e.entity_id))
        return tuple(entities)


# =============================================================================
# NORMALIZATION ENGINE (Orchestrates all normalization)
# =============================================================================

@dataclass
class NormalizationConfig:
    """Configuration for normalization engine."""
    duplicate_similarity_threshold: float = 0.8
    min_payload_length: int = 1
    max_payload_length: int = 100000


class NormalizationEngine:
    """
    Core normalization engine that orchestrates all canonicalization.
    
    BOUNDARY ENFORCEMENT:
    - Consumes ONLY RawIngestionEvent from ingestion layer
    - Produces ONLY NormalizedFragment objects
    - Does NOT access storage, core engine, or query layers
    - Does NOT resolve contradictions, only tags them
    """
    
    def __init__(self, config: Optional[NormalizationConfig] = None):
        self._config = config or NormalizationConfig()
        self._language_detector = LanguageDetector()
        self._duplicate_detector = DuplicateDetector(
            similarity_threshold=self._config.duplicate_similarity_threshold
        )
        self._contradiction_detector = ContradictionDetector()
        self._topic_classifier = TopicClassifier()
        self._entity_extractor = EntityExtractor()
        self._audit_log: List[AuditLogEntry] = []
    
    def normalize(self, event: RawIngestionEvent) -> NormalizationResult:
        """
        Normalize a raw ingestion event into a canonical fragment.
        
        This is the primary entry point for normalization.
        Returns NormalizationResult with either fragment or explicit error.
        """
        import time
        start_time = time.time()
        
        # Extract payload from raw event
        try:
            payload_data = json.loads(event.raw_payload)
            if isinstance(payload_data, dict):
                payload = payload_data.get('payload', json.dumps(payload_data))
            else:
                payload = str(payload_data)
        except json.JSONDecodeError:
            payload = event.raw_payload
        
        # Validate payload
        if not payload or len(payload) < self._config.min_payload_length:
            return NormalizationResult(
                success=False,
                error=Error(
                    code=ErrorCode.EMPTY_PAYLOAD,
                    message="Payload is empty or too short",
                    timestamp=Timestamp.now().value
                ),
                processing_time_ms=(time.time() - start_time) * 1000
            )
        
        if len(payload) > self._config.max_payload_length:
            return NormalizationResult(
                success=False,
                error=Error(
                    code=ErrorCode.MALFORMED_PAYLOAD,
                    message=f"Payload exceeds maximum length of {self._config.max_payload_length}",
                    timestamp=Timestamp.now().value
                ),
                processing_time_ms=(time.time() - start_time) * 1000
            )
        
        # Compute content signature
        content_signature = ContentSignature.compute(payload)
        
        # Generate fragment ID
        fragment_id = FragmentId.generate(
            source_id=event.source_metadata.source_id.value,
            timestamp=event.source_metadata.capture_timestamp.value,
            payload=payload
        )
        
        # Detect language
        detected_language = self._language_detector.detect(payload)
        
        # Classify topics
        topics = self._topic_classifier.classify(payload)
        
        # Extract entities
        entities = self._entity_extractor.extract(payload)
        
        # Check for duplicates
        duplicate_info = self._duplicate_detector.check(
            content=payload,
            content_hash=content_signature.payload_hash
        )
        
        # Check for contradictions (only if unique)
        if duplicate_info.status == DuplicateStatus.UNIQUE:
            contradiction_info = self._contradiction_detector.check(
                content=payload,
                topics=topics
            )
        else:
            contradiction_info = ContradictionInfo(
                status=ContradictionStatus.NO_CONTRADICTION
            )
        
        # Create normalized fragment
        fragment = NormalizedFragment(
            fragment_id=fragment_id,
            source_event_id=event.event_id,
            content_signature=content_signature,
            normalized_payload=payload,
            detected_language=detected_language,
            canonical_topics=topics,
            canonical_entities=entities,
            duplicate_info=duplicate_info,
            contradiction_info=contradiction_info,
            normalization_timestamp=Timestamp.now(),
            source_metadata=event.source_metadata
        )
        
        # Register with detectors (only if unique)
        if duplicate_info.status == DuplicateStatus.UNIQUE:
            self._duplicate_detector.register(
                fragment_id=fragment_id,
                content=payload,
                content_hash=content_signature.payload_hash
            )
            self._contradiction_detector.register(
                fragment_id=fragment_id,
                content=payload,
                topics=topics
            )
        
        processing_time_ms = (time.time() - start_time) * 1000
        
        self._log_audit(
            action="fragment_normalized",
            entity_id=fragment_id.value,
            metadata=(
                ("duplicate_status", duplicate_info.status.value),
                ("contradiction_status", contradiction_info.status.value),
                ("topic_count", str(len(topics))),
                ("processing_time_ms", f"{processing_time_ms:.2f}"),
            )
        )
        
        return NormalizationResult(
            success=True,
            fragment=fragment,
            processing_time_ms=processing_time_ms
        )
    
    def normalize_batch(
        self, 
        events: List[RawIngestionEvent]
    ) -> List[NormalizationResult]:
        """Normalize a batch of events."""
        return [self.normalize(event) for event in events]
    
    def _log_audit(
        self,
        action: str,
        entity_id: Optional[str] = None,
        metadata: tuple = ()
    ):
        """Add entry to internal audit log."""
        entry_id = hashlib.sha256(
            f"norm_{action}|{Timestamp.now().value.timestamp()}".encode()
        ).hexdigest()[:16]
        
        entry = AuditLogEntry(
            entry_id=f"audit_{entry_id}",
            event_type=AuditEventType.NORMALIZATION,
            timestamp=Timestamp.now(),
            layer="normalization",
            action=action,
            entity_id=entity_id,
            entity_type="fragment",
            metadata=metadata
        )
        self._audit_log.append(entry)
    
    def get_audit_log(self) -> List[AuditLogEntry]:
        """Return copy of audit log entries."""
        return list(self._audit_log)
