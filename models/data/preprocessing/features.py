"""
Feature Extraction

Extracts temporal and semantic features from raw data.

BOUNDARY ENFORCEMENT:
- Consumes RawDataPoint
- Produces TemporalFeatures, SemanticFeatures
- NO learning, NO inference
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
from datetime import datetime
import hashlib
import re

# Import ONLY from contracts
from ...contracts.data_contracts import (
    RawDataPoint, FeatureVector, TemporalFeatures, 
    SemanticFeatures, PreprocessedFragment, DataQuality
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class FeatureConfig:
    """Configuration for feature extraction."""
    embedding_dimension: int = 128
    max_topics: int = 5
    max_entities: int = 10
    default_language: str = "en"


# =============================================================================
# TEMPORAL FEATURE EXTRACTION
# =============================================================================

class TemporalFeatureExtractor:
    """
    Extract temporal features from data points.
    
    Deterministic extraction - same input, same output.
    """
    
    def __init__(self, reference_time: Optional[datetime] = None):
        self._reference_time = reference_time or datetime.now()
        self._last_timestamps: dict = {}
    
    def extract(
        self,
        data_point: RawDataPoint,
        previous_timestamp: Optional[datetime] = None
    ) -> TemporalFeatures:
        """Extract temporal features from a data point."""
        ts = data_point.timestamp
        
        # Time since last
        time_since_last = None
        if previous_timestamp:
            time_since_last = (ts - previous_timestamp).total_seconds()
        
        # Position in day (0.0 to 1.0)
        seconds_in_day = ts.hour * 3600 + ts.minute * 60 + ts.second
        time_window_position = seconds_in_day / 86400.0
        
        return TemporalFeatures(
            timestamp=ts,
            time_since_last=time_since_last,
            time_window_position=time_window_position,
            day_of_week=ts.weekday(),
            hour_of_day=ts.hour,
            is_weekend=ts.weekday() >= 5
        )


# =============================================================================
# SEMANTIC FEATURE EXTRACTION
# =============================================================================

class TopicExtractor:
    """
    Extract topics from text content.
    
    Uses keyword-based extraction (deterministic).
    """
    
    # Topic keywords mapping
    TOPIC_KEYWORDS: dict = {
        'climate': frozenset({'climate', 'carbon', 'emissions', 'warming', 'environmental'}),
        'technology': frozenset({'tech', 'ai', 'software', 'digital', 'algorithm', 'data'}),
        'politics': frozenset({'government', 'policy', 'election', 'vote', 'political'}),
        'finance': frozenset({'money', 'market', 'stock', 'investment', 'financial'}),
        'health': frozenset({'health', 'medical', 'hospital', 'disease', 'treatment'}),
    }
    
    def extract_topics(self, text: str, max_topics: int = 5) -> Tuple[str, ...]:
        """Extract topic IDs from text."""
        words = frozenset(re.findall(r'\b[a-zA-Z]+\b', text.lower()))
        
        topic_scores = []
        for topic_id, keywords in self.TOPIC_KEYWORDS.items():
            overlap = len(words & keywords)
            if overlap > 0:
                topic_scores.append((overlap, topic_id))
        
        # Sort by score descending, then by topic_id for determinism
        topic_scores.sort(key=lambda x: (-x[0], x[1]))
        
        return tuple(tid for _, tid in topic_scores[:max_topics])


class EntityExtractor:
    """
    Extract entity IDs from text content.
    
    Uses pattern-based extraction (deterministic).
    """
    
    def extract_entities(self, text: str, max_entities: int = 10) -> Tuple[str, ...]:
        """Extract entity IDs from text."""
        # Find capitalized phrases (simplified NER)
        patterns = [
            r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)+\b',  # Multi-word names
            r'\b(?:Mr\.|Mrs\.|Dr\.)\s+[A-Z][a-z]+\b',  # Titles
        ]
        
        entities = set()
        for pattern in patterns:
            matches = re.findall(pattern, text)
            for match in matches:
                # Generate entity ID from text
                entity_id = hashlib.sha256(match.lower().encode()).hexdigest()[:12]
                entities.add(entity_id)
        
        return tuple(sorted(entities)[:max_entities])


class LanguageDetector:
    """
    Detect language of text content.
    
    Uses word frequency (deterministic).
    """
    
    LANGUAGE_WORDS: dict = {
        'en': frozenset({'the', 'and', 'or', 'but', 'for', 'not', 'with', 'this'}),
        'es': frozenset({'el', 'la', 'de', 'que', 'y', 'en', 'un', 'se'}),
        'fr': frozenset({'le', 'la', 'de', 'et', 'ou', 'mais', 'pour', 'avec'}),
    }
    
    def detect(self, text: str) -> str:
        """Detect language from text."""
        words = frozenset(re.findall(r'\b[a-zA-Z]+\b', text.lower()))
        
        scores = {}
        for lang, lang_words in self.LANGUAGE_WORDS.items():
            scores[lang] = len(words & lang_words)
        
        # Return highest scoring language
        if not scores:
            return 'en'
        
        max_score = max(scores.values())
        if max_score == 0:
            return 'en'
        
        for lang in sorted(scores.keys()):
            if scores[lang] == max_score:
                return lang
        
        return 'en'


class SimpleVectorizer:
    """
    Create simple vector embeddings from text.
    
    Uses term frequency with fixed vocabulary.
    Deterministic - same text, same vector.
    """
    
    def __init__(self, dimension: int = 128, seed: int = 42):
        self._dimension = dimension
        self._seed = seed
    
    def vectorize(self, text: str) -> Tuple[float, ...]:
        """Convert text to fixed-dimension vector."""
        # Tokenize
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        if not words:
            return tuple([0.0] * self._dimension)
        
        # Create deterministic hash-based embedding
        vector = [0.0] * self._dimension
        
        for word in words:
            # Hash word to get indices
            word_hash = hashlib.sha256(word.encode()).hexdigest()
            
            # Use hash to set vector positions
            for i in range(0, min(16, len(word_hash)), 2):
                idx = int(word_hash[i:i+2], 16) % self._dimension
                vector[idx] += 1.0
        
        # Normalize
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude > 0:
            vector = [v / magnitude for v in vector]
        
        return tuple(vector)


# =============================================================================
# FEATURE EXTRACTOR (Main class)
# =============================================================================

class FeatureExtractor:
    """
    Main feature extraction engine.
    
    Orchestrates temporal and semantic feature extraction.
    
    BOUNDARY ENFORCEMENT:
    - Consumes RawDataPoint
    - Produces PreprocessedFragment
    - NO learning, NO inference
    """
    
    def __init__(self, config: Optional[FeatureConfig] = None):
        self._config = config or FeatureConfig()
        
        # Initialize extractors
        self._temporal = TemporalFeatureExtractor()
        self._topic_extractor = TopicExtractor()
        self._entity_extractor = EntityExtractor()
        self._language_detector = LanguageDetector()
        self._vectorizer = SimpleVectorizer(self._config.embedding_dimension)
    
    def extract_all(
        self,
        data_point: RawDataPoint,
        previous_timestamp: Optional[datetime] = None
    ) -> PreprocessedFragment:
        """
        Extract all features from a data point.
        
        Returns a complete PreprocessedFragment contract.
        """
        # Temporal features
        temporal_features = self._temporal.extract(data_point, previous_timestamp)
        
        # Semantic features
        topics = self._topic_extractor.extract_topics(
            data_point.payload, 
            self._config.max_topics
        )
        entities = self._entity_extractor.extract_entities(
            data_point.payload,
            self._config.max_entities
        )
        language = self._language_detector.detect(data_point.payload)
        vector = self._vectorizer.vectorize(data_point.payload)
        
        # Content hash
        content_hash = hashlib.sha256(data_point.payload.encode()).hexdigest()
        
        # Create embedding vector contract
        embedding = FeatureVector(
            vector_id=f"emb_{content_hash[:12]}",
            values=vector,
            dimension=self._config.embedding_dimension,
            feature_type="semantic",
            source_id=data_point.data_id,
            created_at=datetime.now()
        )
        
        semantic_features = SemanticFeatures(
            embedding=embedding,
            topic_ids=topics,
            entity_ids=entities,
            language=language,
            content_hash=content_hash
        )
        
        # Assess quality
        quality = self._assess_quality(data_point)
        
        # Generate fragment ID
        fragment_id = f"frag_{content_hash[:16]}"
        
        return PreprocessedFragment(
            fragment_id=fragment_id,
            source_data_id=data_point.data_id,
            temporal_features=temporal_features,
            semantic_features=semantic_features,
            quality=quality,
            preprocessing_version="1.0.0",
            preprocessed_at=datetime.now()
        )
    
    def extract_batch(
        self,
        data_points: List[RawDataPoint]
    ) -> List[PreprocessedFragment]:
        """Extract features from a batch of data points."""
        # Sort by timestamp for temporal feature extraction
        sorted_points = sorted(data_points, key=lambda x: x.timestamp)
        
        fragments = []
        previous_ts = None
        
        for dp in sorted_points:
            fragment = self.extract_all(dp, previous_ts)
            fragments.append(fragment)
            previous_ts = dp.timestamp
        
        return fragments
    
    def _assess_quality(self, data_point: RawDataPoint) -> DataQuality:
        """Assess data quality based on content."""
        payload = data_point.payload
        
        # Check content length
        if len(payload) < 10:
            return DataQuality.LOW
        
        # Check for actual content
        words = re.findall(r'\b[a-zA-Z]+\b', payload)
        if len(words) < 3:
            return DataQuality.LOW
        
        if len(words) >= 10:
            return DataQuality.HIGH
        
        return DataQuality.MEDIUM
