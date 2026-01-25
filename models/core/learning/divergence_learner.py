"""
Divergence Learner (Unsupervised)

Learn divergence patterns from unlabeled data.

BOUNDARY ENFORCEMENT:
- Training logic only
- NO inference
- Unsupervised pattern discovery
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import hashlib
import random
import math

from ...contracts.data_contracts import AnnotatedFragment
from ...contracts.model_contracts import (
    TrainedModelArtifact, TrainingRun,
    ModelStatus, LearningTaskType
)


@dataclass
class DivergenceLearnerConfig:
    """Configuration for divergence learner."""
    n_clusters: int = 5
    max_iterations: int = 20
    convergence_threshold: float = 0.001
    random_seed: int = 42


class DivergenceLearner:
    """
    Learn divergence patterns using unsupervised clustering.
    
    BOUNDARY ENFORCEMENT:
    - Training only, unsupervised
    - Discovers natural clusters/divergence patterns
    - Produces TrainedModelArtifact
    """
    
    def __init__(self, config: Optional[DivergenceLearnerConfig] = None):
        self._config = config or DivergenceLearnerConfig()
        self._centroids: List[List[float]] = []
        self._is_trained = False
        self._version_counter = 0
    
    def train(
        self,
        fragments: List[AnnotatedFragment]
    ) -> Tuple[TrainingRun, TrainedModelArtifact]:
        """Train divergence pattern detector using k-means clustering."""
        random.seed(self._config.random_seed)
        start_time = datetime.now()
        
        # Extract vectors
        vectors = [
            list(f.preprocessed_fragment.semantic_features.embedding.values)
            for f in fragments
        ]
        
        if len(vectors) < self._config.n_clusters:
            raise ValueError("Not enough data for clustering")
        
        dim = len(vectors[0])
        
        # Initialize centroids randomly
        indices = random.sample(range(len(vectors)), self._config.n_clusters)
        self._centroids = [list(vectors[i]) for i in indices]
        
        # K-means iterations
        prev_centroids = None
        for iteration in range(self._config.max_iterations):
            # Assign clusters
            clusters: Dict[int, List[int]] = {i: [] for i in range(self._config.n_clusters)}
            for idx, vec in enumerate(vectors):
                closest = self._find_closest_centroid(vec)
                clusters[closest].append(idx)
            
            # Update centroids
            new_centroids = []
            for i in range(self._config.n_clusters):
                if clusters[i]:
                    centroid = [0.0] * dim
                    for idx in clusters[i]:
                        for j in range(dim):
                            centroid[j] += vectors[idx][j]
                    centroid = [c / len(clusters[i]) for c in centroid]
                    new_centroids.append(centroid)
                else:
                    new_centroids.append(self._centroids[i])
            
            # Check convergence
            if prev_centroids:
                max_change = max(
                    self._distance(new_centroids[i], prev_centroids[i])
                    for i in range(self._config.n_clusters)
                )
                if max_change < self._config.convergence_threshold:
                    break
            
            prev_centroids = [list(c) for c in self._centroids]
            self._centroids = new_centroids
        
        end_time = datetime.now()
        self._is_trained = True
        self._version_counter += 1
        
        run_id = hashlib.sha256(
            f"diverge_{self._version_counter}".encode()
        ).hexdigest()[:12]
        
        training_run = TrainingRun(
            run_id=f"run_{run_id}",
            task_id="divergence_detection",
            config_id=f"config_{run_id}",
            started_at=start_time,
            completed_at=end_time,
            final_loss=None,
            final_metrics=(("clusters", float(self._config.n_clusters)),),
            status="completed"
        )
        
        weights_hash = hashlib.sha256(str(self._centroids).encode()).hexdigest()
        
        artifact = TrainedModelArtifact(
            model_id=f"model_diverge_{run_id}",
            model_version=f"diverge_v{self._version_counter}",
            task_type=LearningTaskType.DIVERGENCE_DETECTION,
            weights_hash=weights_hash,
            weights_path=f"models/divergence_{run_id}.pkl",
            training_run_id=training_run.run_id,
            input_schema="AnnotatedFragment",
            output_schema="int",
            status=ModelStatus.TRAINED,
            created_at=end_time
        )
        
        return training_run, artifact
    
    def _find_closest_centroid(self, vec: List[float]) -> int:
        """Find index of closest centroid."""
        min_dist = float('inf')
        closest = 0
        for i, centroid in enumerate(self._centroids):
            dist = self._distance(vec, centroid)
            if dist < min_dist:
                min_dist = dist
                closest = i
        return closest
    
    def _distance(self, a: List[float], b: List[float]) -> float:
        """Euclidean distance."""
        return sum((ai - bi) ** 2 for ai, bi in zip(a, b)) ** 0.5
