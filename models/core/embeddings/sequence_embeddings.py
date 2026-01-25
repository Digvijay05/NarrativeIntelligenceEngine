"""
Sequence Embeddings

Learn embeddings for temporal sequences of fragments.

BOUNDARY ENFORCEMENT:
- Training logic only
- NO temporal prediction (that's Phase 3)
- NO inference execution
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import hashlib
import random

from ...contracts.data_contracts import AnnotatedFragment
from ...contracts.model_contracts import (
    EmbeddingVector, TrainedModelArtifact,
    ModelStatus, LearningTaskType
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class SequenceEmbeddingConfig:
    """Configuration for sequence embeddings."""
    dimension: int = 64
    context_window: int = 3
    learning_rate: float = 0.01
    epochs: int = 5
    random_seed: int = 42


# =============================================================================
# SEQUENCE EMBEDDER
# =============================================================================

class SequenceEmbedder:
    """
    Learn embeddings that capture sequential/temporal patterns.
    
    BOUNDARY ENFORCEMENT:
    - Training only, no inference
    - Learns from fragment sequences
    - Deterministic with seeded randomness
    """
    
    def __init__(self, config: Optional[SequenceEmbeddingConfig] = None):
        self._config = config or SequenceEmbeddingConfig()
        self._embeddings: Dict[str, List[float]] = {}
        self._is_trained = False
        self._version_counter = 0
    
    def train(
        self,
        sequences: List[List[AnnotatedFragment]]
    ) -> Tuple[Dict[str, EmbeddingVector], TrainedModelArtifact]:
        """
        Train sequence embeddings from fragment sequences.
        
        Learns to predict context from central fragment.
        """
        random.seed(self._config.random_seed)
        
        # Collect all fragment IDs
        all_fragment_ids = set()
        for seq in sequences:
            for frag in seq:
                all_fragment_ids.add(frag.fragment_id)
        
        # Initialize embeddings
        for fid in all_fragment_ids:
            self._embeddings[fid] = [
                random.gauss(0, 0.1) for _ in range(self._config.dimension)
            ]
        
        # Training: context window approach
        for epoch in range(self._config.epochs):
            for seq in sequences:
                sorted_seq = sorted(
                    seq, 
                    key=lambda f: f.preprocessed_fragment.temporal_features.timestamp
                )
                
                for i, center_frag in enumerate(sorted_seq):
                    # Get context window
                    start = max(0, i - self._config.context_window)
                    end = min(len(sorted_seq), i + self._config.context_window + 1)
                    
                    context_frags = (
                        sorted_seq[start:i] + 
                        sorted_seq[i+1:end]
                    )
                    
                    # Update embeddings
                    center_id = center_frag.fragment_id
                    for ctx_frag in context_frags:
                        ctx_id = ctx_frag.fragment_id
                        self._update_embeddings(center_id, ctx_id)
        
        self._is_trained = True
        self._version_counter += 1
        
        # Create embedding vectors
        embedding_dict = {}
        for fid, vec in self._embeddings.items():
            emb = EmbeddingVector(
                embedding_id=f"seqemb_{fid}",
                entity_id=fid,
                entity_type="fragment",
                vector=tuple(vec),
                dimension=self._config.dimension,
                model_version=f"seqemb_v{self._version_counter}",
                created_at=datetime.now()
            )
            embedding_dict[fid] = emb
        
        # Create model artifact
        weights_content = str(list(self._embeddings.values()))[:1000]
        weights_hash = hashlib.sha256(weights_content.encode()).hexdigest()
        
        model_id = hashlib.sha256(
            f"seqemb_{self._version_counter}_{len(all_fragment_ids)}".encode()
        ).hexdigest()[:12]
        
        artifact = TrainedModelArtifact(
            model_id=f"model_seqemb_{model_id}",
            model_version=f"seqemb_v{self._version_counter}",
            task_type=LearningTaskType.SEQUENCE_PREDICTION,
            weights_hash=weights_hash,
            weights_path=f"embeddings/sequence_{model_id}.pkl",
            training_run_id=f"run_{model_id}",
            input_schema="List[List[AnnotatedFragment]]",
            output_schema="Dict[str, EmbeddingVector]",
            status=ModelStatus.TRAINED,
            created_at=datetime.now()
        )
        
        return embedding_dict, artifact
    
    def _update_embeddings(
        self,
        center_id: str,
        context_id: str
    ):
        """Update embeddings to bring context closer to center."""
        vec_center = self._embeddings[center_id]
        vec_context = self._embeddings[context_id]
        
        lr = self._config.learning_rate
        
        for i in range(len(vec_center)):
            diff = vec_context[i] - vec_center[i]
            vec_center[i] += lr * diff * 0.3
            vec_context[i] -= lr * diff * 0.3
    
    def get_sequence_embedding(
        self,
        fragment_ids: List[str]
    ) -> Optional[List[float]]:
        """
        Get combined embedding for a sequence of fragments.
        
        Returns average of individual embeddings.
        """
        if not self._is_trained:
            return None
        
        valid_embeddings = [
            self._embeddings[fid]
            for fid in fragment_ids
            if fid in self._embeddings
        ]
        
        if not valid_embeddings:
            return None
        
        # Average embeddings
        result = [0.0] * self._config.dimension
        for emb in valid_embeddings:
            for i, v in enumerate(emb):
                result[i] += v / len(valid_embeddings)
        
        return result
