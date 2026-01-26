"""
Vectorization Module

Semantic vectorization of text content.

BOUNDARY ENFORCEMENT:
- Pure functions for text to vector conversion
- NO learning, NO inference
- Deterministic: same input, same output
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict
from datetime import datetime
import hashlib
import math
import re

from ...contracts.data_contracts import FeatureVector


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class VectorizerConfig:
    """Configuration for vectorization."""
    dimension: int = 128
    use_tf_idf: bool = True
    normalize: bool = True
    hash_seed: int = 42


# =============================================================================
# TF-IDF COMPUTATION
# =============================================================================

class TFIDFComputer:
    """
    Compute TF-IDF vectors.
    
    Deterministic computation with fixed vocabulary.
    """
    
    def __init__(self):
        self._document_frequencies: Dict[str, int] = {}
        self._total_documents: int = 0
    
    def fit(self, documents: List[str]):
        """Build document frequencies from corpus."""
        self._document_frequencies = {}
        self._total_documents = len(documents)
        
        for doc in documents:
            words = set(re.findall(r'\b[a-zA-Z]+\b', doc.lower()))
            for word in words:
                self._document_frequencies[word] = \
                    self._document_frequencies.get(word, 0) + 1
    
    def compute_tf(self, text: str) -> Dict[str, float]:
        """Compute term frequency for a document."""
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        if not words:
            return {}
        
        tf = {}
        for word in words:
            tf[word] = tf.get(word, 0) + 1
        
        # Normalize by document length
        total = len(words)
        return {w: c / total for w, c in tf.items()}
    
    def compute_idf(self, word: str) -> float:
        """Compute inverse document frequency for a word."""
        if self._total_documents == 0:
            return 1.0
        
        df = self._document_frequencies.get(word, 0)
        if df == 0:
            return 1.0
        
        return math.log(self._total_documents / df) + 1.0
    
    def compute_tfidf(self, text: str) -> Dict[str, float]:
        """Compute TF-IDF for a document."""
        tf = self.compute_tf(text)
        return {word: tf_val * self.compute_idf(word) 
                for word, tf_val in tf.items()}


# =============================================================================
# HASH-BASED VECTORIZATION
# =============================================================================

class HashVectorizer:
    """
    Hash-based vectorization for fixed-dimension output.
    
    Deterministic: Same text always produces same vector.
    """
    
    def __init__(self, dimension: int = 128, seed: int = 42):
        self._dimension = dimension
        self._seed = seed
    
    def vectorize(self, text: str) -> Tuple[float, ...]:
        """Convert text to fixed-dimension vector using hashing trick."""
        words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
        
        vector = [0.0] * self._dimension
        
        for word in words:
            # Deterministic hash
            h = hashlib.sha256(f"{self._seed}:{word}".encode()).digest()
            
            # Use first 8 bytes for index, next 8 for sign
            idx = int.from_bytes(h[:8], 'big') % self._dimension
            sign = 1 if int.from_bytes(h[8:16], 'big') % 2 == 0 else -1
            
            vector[idx] += sign * 1.0
        
        return tuple(vector)
    
    def normalize(self, vector: Tuple[float, ...]) -> Tuple[float, ...]:
        """L2 normalize a vector."""
        magnitude = sum(v * v for v in vector) ** 0.5
        if magnitude == 0:
            return vector
        return tuple(v / magnitude for v in vector)


# =============================================================================
# COMBINED VECTORIZER
# =============================================================================

class Vectorizer:
    """
    Main vectorization engine.
    
    Combines multiple vectorization strategies.
    
    BOUNDARY ENFORCEMENT:
    - Pure function: text → vector
    - NO learning, NO inference
    - Deterministic
    """
    
    def __init__(self, config: Optional[VectorizerConfig] = None):
        self._config = config or VectorizerConfig()
        self._hash_vectorizer = HashVectorizer(
            dimension=self._config.dimension,
            seed=self._config.hash_seed
        )
        self._tfidf = TFIDFComputer()
        self._is_fitted = False
    
    def fit(self, corpus: List[str]):
        """Fit TF-IDF on a corpus (optional preprocessing step)."""
        if self._config.use_tf_idf and corpus:
            self._tfidf.fit(corpus)
            self._is_fitted = True
    
    def vectorize(self, text: str) -> FeatureVector:
        """
        Vectorize a text into a FeatureVector contract.
        
        Deterministic: same text, same vector.
        """
        # Get hash-based vector
        hash_vector = self._hash_vectorizer.vectorize(text)
        
        # Optionally weight by TF-IDF
        if self._config.use_tf_idf and self._is_fitted:
            tfidf = self._tfidf.compute_tfidf(text)
            weighted = list(hash_vector)
            
            # Apply TF-IDF weights
            words = re.findall(r'\b[a-zA-Z]+\b', text.lower())
            for word in words:
                if word in tfidf:
                    h = hashlib.sha256(
                        f"{self._config.hash_seed}:{word}".encode()
                    ).digest()
                    idx = int.from_bytes(h[:8], 'big') % self._config.dimension
                    weighted[idx] *= tfidf[word]
            
            vector = tuple(weighted)
        else:
            vector = hash_vector
        
        # Normalize if configured
        if self._config.normalize:
            vector = self._hash_vectorizer.normalize(vector)
        
        # Generate vector ID
        content_hash = hashlib.sha256(text.encode()).hexdigest()[:12]
        
        return FeatureVector(
            vector_id=f"vec_{content_hash}",
            values=vector,
            dimension=self._config.dimension,
            feature_type="semantic",
            source_id=content_hash,
            created_at=datetime.now()
        )
    
    def vectorize_batch(self, texts: List[str]) -> List[FeatureVector]:
        """Vectorize a batch of texts."""
        return [self.vectorize(text) for text in texts]
    
    def compute_similarity(
        self,
        vec_a: FeatureVector,
        vec_b: FeatureVector
    ) -> float:
        """Compute cosine similarity between two vectors."""
        if vec_a.dimension != vec_b.dimension:
            raise ValueError("Vectors must have same dimension")
        
        dot_product = sum(a * b for a, b in zip(vec_a.values, vec_b.values))
        norm_a = sum(a * a for a in vec_a.values) ** 0.5
        norm_b = sum(b * b for b in vec_b.values) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
