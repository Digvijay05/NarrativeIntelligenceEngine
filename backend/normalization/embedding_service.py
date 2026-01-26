"""
Embedding Service
=================

Coordinate transform service for the normalization layer.

ML FENCE POST:
==============
This service computes embeddings as GEOMETRY, not understanding.
It returns raw vectors and similarity scores WITHOUT thresholds.

ALLOWED:
- Vector computation
- Distance/similarity computation
- Nearest neighbor lookup

FORBIDDEN:
- Threshold-based decisions ("similarity > 0.8 = duplicate")
- Dimension interpretation
- Vector averaging/summarization
"""

from __future__ import annotations
from typing import List, Optional, Tuple, Dict
from dataclasses import dataclass
import numpy as np

from ..contracts.events import EmbeddingVector, SimilarityScore
from ..contracts.base import FragmentId


@dataclass
class EmbeddingServiceConfig:
    """Configuration for embedding service."""
    model_id: str = "all-MiniLM-L6-v2"  # Default sentence-transformers model
    model_version: str = "1.0.0"
    max_sequence_length: int = 256
    batch_size: int = 32
    use_gpu: bool = False
    
    # Index configuration
    store_embeddings: bool = True
    similarity_metric: str = "cosine"  # "cosine", "euclidean", "dot"


class EmbeddingService:
    """
    Embedding service for coordinate transforms.
    
    ML FENCE POST:
    ==============
    This service is a PROBE that measures geometry.
    It does NOT interpret what the measurements mean.
    
    All outputs are raw values that cross to the next layer
    as immutable contracts.
    """
    
    def __init__(self, config: Optional[EmbeddingServiceConfig] = None):
        self._config = config or EmbeddingServiceConfig()
        self._model = None
        self._model_loaded = False
        
        # In-memory index of embeddings for similarity lookup
        # Maps fragment_id -> embedding vector (as numpy array)
        self._embedding_index: Dict[str, np.ndarray] = {}
        self._fragment_ids: List[str] = []
    
    def _ensure_model_loaded(self) -> bool:
        """Lazy load the embedding model."""
        if self._model_loaded:
            return True
        
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(
                self._config.model_id,
                device='cuda' if self._config.use_gpu else 'cpu'
            )
            self._model_loaded = True
            return True
        except ImportError:
            # sentence-transformers not installed - graceful degradation
            self._model = None
            self._model_loaded = False
            return False
        except Exception:
            # Model loading failed
            self._model = None
            self._model_loaded = False
            return False
    
    def compute_embedding(self, text: str) -> Optional[EmbeddingVector]:
        """
        Compute embedding vector for text.
        
        Returns None if model not available (graceful degradation).
        
        ML FENCE POST:
        - Returns raw vector coordinates
        - Does NOT interpret what the coordinates mean
        """
        if not self._ensure_model_loaded():
            return None
        
        if not text or len(text.strip()) == 0:
            return None
        
        try:
            # Truncate to max sequence length
            truncated = text[:self._config.max_sequence_length * 4]  # Rough char estimate
            
            # Compute embedding
            embedding = self._model.encode(
                truncated,
                convert_to_numpy=True,
                normalize_embeddings=True  # Unit vectors for cosine similarity
            )
            
            return EmbeddingVector.from_list(
                values=embedding.tolist(),
                model_id=self._config.model_id,
                model_version=self._config.model_version
            )
        except Exception:
            return None
    
    def compute_batch_embeddings(
        self,
        texts: List[str]
    ) -> List[Optional[EmbeddingVector]]:
        """
        Compute embeddings for a batch of texts.
        
        Returns list of embeddings, None for any that failed.
        """
        if not self._ensure_model_loaded():
            return [None] * len(texts)
        
        results = []
        for text in texts:
            results.append(self.compute_embedding(text))
        
        return results
    
    def compute_similarity(
        self,
        embedding1: EmbeddingVector,
        embedding2: EmbeddingVector
    ) -> SimilarityScore:
        """
        Compute similarity between two embeddings.
        
        ML FENCE POST:
        - Returns RAW similarity score
        - Does NOT apply threshold
        - Does NOT decide if they are "similar enough"
        """
        vec1 = np.array(embedding1.to_list())
        vec2 = np.array(embedding2.to_list())
        
        if self._config.similarity_metric == "cosine":
            # Vectors are normalized, so dot product = cosine similarity
            similarity = float(np.dot(vec1, vec2))
        elif self._config.similarity_metric == "euclidean":
            # Return negative distance (higher = more similar)
            similarity = -float(np.linalg.norm(vec1 - vec2))
        elif self._config.similarity_metric == "dot":
            similarity = float(np.dot(vec1, vec2))
        else:
            similarity = float(np.dot(vec1, vec2))
        
        return SimilarityScore(
            value=similarity,
            metric=self._config.similarity_metric,
            threshold_applied=False  # EXPLICITLY: no decision made
        )
    
    def register_embedding(
        self,
        fragment_id: FragmentId,
        embedding: EmbeddingVector
    ) -> None:
        """
        Register embedding in index for future similarity lookups.
        """
        if not self._config.store_embeddings:
            return
        
        self._embedding_index[fragment_id.value] = np.array(embedding.to_list())
        if fragment_id.value not in self._fragment_ids:
            self._fragment_ids.append(fragment_id.value)
    
    def find_nearest(
        self,
        embedding: EmbeddingVector,
        exclude_ids: Optional[List[str]] = None
    ) -> Tuple[Optional[FragmentId], Optional[SimilarityScore]]:
        """
        Find nearest neighbor in the embedding index.
        
        ML FENCE POST:
        - Returns the NEAREST fragment by distance
        - Returns RAW similarity score
        - Does NOT decide if it's "close enough"
        
        Returns (None, None) if index is empty.
        """
        if not self._embedding_index:
            return None, None
        
        exclude_set = set(exclude_ids or [])
        query_vec = np.array(embedding.to_list())
        
        best_id = None
        best_similarity = float('-inf')
        
        for frag_id, stored_vec in self._embedding_index.items():
            if frag_id in exclude_set:
                continue
            
            if self._config.similarity_metric == "cosine":
                sim = float(np.dot(query_vec, stored_vec))
            elif self._config.similarity_metric == "euclidean":
                sim = -float(np.linalg.norm(query_vec - stored_vec))
            else:
                sim = float(np.dot(query_vec, stored_vec))
            
            if sim > best_similarity:
                best_similarity = sim
                best_id = frag_id
        
        if best_id is None:
            return None, None
        
        return (
            FragmentId(value=best_id, content_hash=""),  # Content hash not needed for reference
            SimilarityScore(
                value=best_similarity,
                metric=self._config.similarity_metric,
                threshold_applied=False
            )
        )
    
    def get_index_size(self) -> int:
        """Return number of embeddings in index."""
        return len(self._embedding_index)
    
    def clear_index(self) -> None:
        """Clear the embedding index."""
        self._embedding_index.clear()
        self._fragment_ids.clear()
    
    def is_available(self) -> bool:
        """Check if embedding service is available."""
        return self._ensure_model_loaded()


# Singleton instance for the normalization layer
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service(config: Optional[EmbeddingServiceConfig] = None) -> EmbeddingService:
    """Get or create the embedding service singleton."""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService(config)
    return _embedding_service
