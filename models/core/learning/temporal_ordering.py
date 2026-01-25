"""
Temporal Order Learner (Self-supervised)

Learn temporal ordering from sequence structure.

BOUNDARY ENFORCEMENT:
- Training logic only
- Self-supervised: labels derived from sequence order
- NO temporal prediction (that's Phase 3)
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import hashlib
import random

from ...contracts.data_contracts import AnnotatedFragment
from ...contracts.model_contracts import (
    TrainedModelArtifact, TrainingRun,
    ModelStatus, LearningTaskType
)


@dataclass
class TemporalOrderConfig:
    """Configuration for temporal order learning."""
    hidden_dimension: int = 32
    learning_rate: float = 0.01
    epochs: int = 10
    random_seed: int = 42


class TemporalOrderLearner:
    """
    Learn temporal ordering using self-supervised approach.
    
    Task: Given two fragments, predict which comes first.
    
    BOUNDARY ENFORCEMENT:
    - Training only
    - Self-supervised from timestamps
    - Produces TrainedModelArtifact
    """
    
    def __init__(self, config: Optional[TemporalOrderConfig] = None):
        self._config = config or TemporalOrderConfig()
        self._weights: List[float] = []
        self._is_trained = False
        self._version_counter = 0
    
    def prepare_pairs(
        self,
        fragments: List[AnnotatedFragment]
    ) -> List[Tuple[List[float], float]]:
        """Prepare training pairs from fragments."""
        pairs = []
        
        sorted_frags = sorted(
            fragments,
            key=lambda f: f.preprocessed_fragment.temporal_features.timestamp
        )
        
        for i in range(len(sorted_frags) - 1):
            frag_a = sorted_frags[i]
            frag_b = sorted_frags[i + 1]
            
            vec_a = frag_a.preprocessed_fragment.semantic_features.embedding.values
            vec_b = frag_b.preprocessed_fragment.semantic_features.embedding.values
            
            # Features: difference and interaction
            features = []
            for a, b in zip(vec_a, vec_b):
                features.append(a - b)
            
            # Label: 1 if a comes before b (always true for sorted pairs)
            pairs.append((features, 1.0))
            
            # Add negative: b before a
            features_neg = [-f for f in features]
            pairs.append((features_neg, 0.0))
        
        return pairs
    
    def train(
        self,
        fragments: List[AnnotatedFragment]
    ) -> Tuple[TrainingRun, TrainedModelArtifact]:
        """Train temporal order predictor."""
        random.seed(self._config.random_seed)
        start_time = datetime.now()
        
        pairs = self.prepare_pairs(fragments)
        if not pairs:
            raise ValueError("No training pairs generated")
        
        dim = len(pairs[0][0])
        self._weights = [random.gauss(0, 0.1) for _ in range(dim)]
        
        total_loss = 0.0
        for epoch in range(self._config.epochs):
            random.shuffle(pairs)
            epoch_loss = 0.0
            
            for features, label in pairs:
                # Forward
                logit = sum(w * f for w, f in zip(self._weights, features))
                pred = 1.0 / (1.0 + (2.718 ** (-max(-10, min(10, logit)))))
                
                # Loss
                epsilon = 1e-7
                loss = -(label * (pred + epsilon).__log__() if hasattr(pred, '__log__') else 0)
                epoch_loss += abs(pred - label)
                
                # Update
                error = pred - label
                for i in range(dim):
                    self._weights[i] -= self._config.learning_rate * error * features[i]
            
            total_loss = epoch_loss / len(pairs)
        
        end_time = datetime.now()
        self._is_trained = True
        self._version_counter += 1
        
        run_id = hashlib.sha256(
            f"tempord_{self._version_counter}".encode()
        ).hexdigest()[:12]
        
        training_run = TrainingRun(
            run_id=f"run_{run_id}",
            task_id="temporal_ordering",
            config_id=f"config_{run_id}",
            started_at=start_time,
            completed_at=end_time,
            final_loss=total_loss,
            final_metrics=(("pairs", float(len(pairs))),),
            status="completed"
        )
        
        weights_hash = hashlib.sha256(str(self._weights).encode()).hexdigest()
        
        artifact = TrainedModelArtifact(
            model_id=f"model_tempord_{run_id}",
            model_version=f"tempord_v{self._version_counter}",
            task_type=LearningTaskType.TEMPORAL_ORDERING,
            weights_hash=weights_hash,
            weights_path=f"models/temporal_order_{run_id}.pkl",
            training_run_id=training_run.run_id,
            input_schema="Tuple[AnnotatedFragment, AnnotatedFragment]",
            output_schema="float",
            status=ModelStatus.TRAINED,
            created_at=end_time
        )
        
        return training_run, artifact
