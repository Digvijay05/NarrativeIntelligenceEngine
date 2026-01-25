"""
Graph Embeddings

Learn embeddings for knowledge graph nodes using simple approaches.

BOUNDARY ENFORCEMENT:
- Training logic only
- NO temporal prediction
- NO inference execution
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import hashlib
import math
import random

from ...contracts.model_contracts import (
    KnowledgeGraphSnapshot, GraphNode, GraphEdge,
    EmbeddingVector, EmbeddingSpace, TrainedModelArtifact,
    ModelStatus, LearningTaskType
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class EmbeddingConfig:
    """Configuration for graph embeddings."""
    dimension: int = 64
    learning_rate: float = 0.01
    epochs: int = 10
    negative_samples: int = 5
    random_seed: int = 42


# =============================================================================
# GRAPH EMBEDDER
# =============================================================================

class GraphEmbedder:
    """
    Learn embeddings for knowledge graph nodes.
    
    Uses simplified node2vec-style approach.
    
    BOUNDARY ENFORCEMENT:
    - Training only, no inference
    - Produces EmbeddingSpace and TrainedModelArtifact
    - Deterministic with seeded randomness
    """
    
    def __init__(self, config: Optional[EmbeddingConfig] = None):
        self._config = config or EmbeddingConfig()
        self._embeddings: Dict[str, List[float]] = {}
        self._is_trained = False
        self._version_counter = 0
    
    def train(
        self,
        graph: KnowledgeGraphSnapshot
    ) -> Tuple[EmbeddingSpace, TrainedModelArtifact]:
        """
        Train embeddings on a knowledge graph.
        
        Returns (EmbeddingSpace, TrainedModelArtifact) contracts.
        """
        random.seed(self._config.random_seed)
        
        # Initialize embeddings
        for node in graph.nodes:
            self._embeddings[node.node_id] = [
                random.gauss(0, 0.1) for _ in range(self._config.dimension)
            ]
        
        # Build adjacency
        adjacency: Dict[str, List[str]] = {}
        for node in graph.nodes:
            adjacency[node.node_id] = []
        for edge in graph.edges:
            adjacency[edge.source_node_id].append(edge.target_node_id)
            adjacency[edge.target_node_id].append(edge.source_node_id)
        
        # Simple training: attract connected nodes, repel random
        all_node_ids = list(self._embeddings.keys())
        
        for epoch in range(self._config.epochs):
            for node_id in all_node_ids:
                neighbors = adjacency.get(node_id, [])
                
                # Positive samples: pull towards neighbors
                for neighbor_id in neighbors:
                    self._update_embeddings(node_id, neighbor_id, positive=True)
                
                # Negative samples: push away from random nodes
                for _ in range(self._config.negative_samples):
                    neg_id = random.choice(all_node_ids)
                    if neg_id != node_id and neg_id not in neighbors:
                        self._update_embeddings(node_id, neg_id, positive=False)
        
        self._is_trained = True
        self._version_counter += 1
        
        # Create embedding vectors
        embedding_vectors = []
        entity_types = set()
        
        for node in graph.nodes:
            vec = self._embeddings.get(node.node_id, [0.0] * self._config.dimension)
            entity_types.add(node.node_type.value)
            
            emb = EmbeddingVector(
                embedding_id=f"emb_{node.node_id}",
                entity_id=node.node_id,
                entity_type=node.node_type.value,
                vector=tuple(vec),
                dimension=self._config.dimension,
                model_version=f"graphemb_v{self._version_counter}",
                created_at=datetime.now()
            )
            embedding_vectors.append(emb)
        
        # Create embedding space
        space_id = hashlib.sha256(
            f"{graph.snapshot_id}|{self._version_counter}".encode()
        ).hexdigest()[:12]
        
        space = EmbeddingSpace(
            space_id=f"space_{space_id}",
            embeddings=tuple(embedding_vectors),
            dimension=self._config.dimension,
            model_version=f"graphemb_v{self._version_counter}",
            entity_types=frozenset(entity_types),
            created_at=datetime.now()
        )
        
        # Create model artifact
        weights_content = str(list(self._embeddings.values()))
        weights_hash = hashlib.sha256(weights_content.encode()).hexdigest()
        
        artifact = TrainedModelArtifact(
            model_id=f"model_graphemb_{space_id}",
            model_version=f"graphemb_v{self._version_counter}",
            task_type=LearningTaskType.SEQUENCE_PREDICTION,
            weights_hash=weights_hash,
            weights_path=f"embeddings/graph_{space_id}.pkl",
            training_run_id=f"run_{space_id}",
            input_schema="KnowledgeGraphSnapshot",
            output_schema="EmbeddingSpace",
            status=ModelStatus.TRAINED,
            created_at=datetime.now()
        )
        
        return space, artifact
    
    def _update_embeddings(
        self,
        node_id: str,
        other_id: str,
        positive: bool
    ):
        """Update embeddings via gradient-like step."""
        vec1 = self._embeddings[node_id]
        vec2 = self._embeddings[other_id]
        
        lr = self._config.learning_rate
        direction = 1.0 if positive else -1.0
        
        for i in range(len(vec1)):
            diff = vec2[i] - vec1[i]
            vec1[i] += direction * lr * diff * 0.5
            vec2[i] -= direction * lr * diff * 0.5
    
    def get_embedding(self, node_id: str) -> Optional[List[float]]:
        """Get embedding for a node (after training)."""
        if not self._is_trained:
            return None
        return self._embeddings.get(node_id)
    
    def compute_similarity(
        self,
        node_id_a: str,
        node_id_b: str
    ) -> float:
        """Compute cosine similarity between two node embeddings."""
        vec_a = self._embeddings.get(node_id_a)
        vec_b = self._embeddings.get(node_id_b)
        
        if not vec_a or not vec_b:
            return 0.0
        
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)
