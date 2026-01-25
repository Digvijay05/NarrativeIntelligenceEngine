"""
Contradiction Detector (Supervised Learning)

Learn to detect contradictions from labeled examples.

BOUNDARY ENFORCEMENT:
- Training logic only
- NO inference (that's Phase 5)
- Uses labeled annotation data
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
from datetime import datetime
import hashlib
import random
import math

from ...contracts.data_contracts import AnnotatedFragment, AnnotationType
from ...contracts.model_contracts import (
    TrainedModelArtifact, TrainingRun, TrainingConfig,
    ModelStatus, LearningTaskType
)


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class ContradictionLearnerConfig:
    """Configuration for contradiction learner."""
    hidden_dimension: int = 32
    learning_rate: float = 0.01
    epochs: int = 20
    batch_size: int = 16
    random_seed: int = 42


# =============================================================================
# SIMPLE CLASSIFIER
# =============================================================================

class SimpleClassifier:
    """
    Simple linear classifier for contradiction detection.
    
    In production, would use neural networks.
    """
    
    def __init__(self, input_dim: int, hidden_dim: int, seed: int = 42):
        random.seed(seed)
        
        self.input_dim = input_dim
        self.hidden_dim = hidden_dim
        
        # Initialize weights
        self.W1 = [[random.gauss(0, 0.1) for _ in range(input_dim)] 
                   for _ in range(hidden_dim)]
        self.b1 = [0.0] * hidden_dim
        
        self.W2 = [random.gauss(0, 0.1) for _ in range(hidden_dim)]
        self.b2 = 0.0
    
    def forward(self, x: List[float]) -> float:
        """Forward pass."""
        # Hidden layer
        hidden = []
        for j in range(self.hidden_dim):
            h = sum(x[i] * self.W1[j][i] for i in range(len(x))) + self.b1[j]
            hidden.append(max(0, h))  # ReLU
        
        # Output layer
        output = sum(hidden[j] * self.W2[j] for j in range(self.hidden_dim)) + self.b2
        
        # Sigmoid
        return 1.0 / (1.0 + math.exp(-max(-10, min(10, output))))
    
    def train_step(
        self,
        x: List[float],
        y: float,
        lr: float
    ) -> float:
        """Single training step with gradient descent."""
        # Forward
        prediction = self.forward(x)
        
        # Loss
        epsilon = 1e-7
        loss = -(y * math.log(prediction + epsilon) + 
                 (1 - y) * math.log(1 - prediction + epsilon))
        
        # Simple gradient update (approximate)
        error = prediction - y
        
        # Update W2, b2
        hidden = []
        for j in range(self.hidden_dim):
            h = sum(x[i] * self.W1[j][i] for i in range(len(x))) + self.b1[j]
            hidden.append(max(0, h))
        
        for j in range(self.hidden_dim):
            self.W2[j] -= lr * error * hidden[j]
        self.b2 -= lr * error
        
        return loss


# =============================================================================
# CONTRADICTION LEARNER
# =============================================================================

class ContradictionLearner:
    """
    Learn to detect contradictions from labeled data.
    
    BOUNDARY ENFORCEMENT:
    - Training only
    - Uses annotations as labels
    - Produces TrainedModelArtifact
    """
    
    def __init__(self, config: Optional[ContradictionLearnerConfig] = None):
        self._config = config or ContradictionLearnerConfig()
        self._classifier: Optional[SimpleClassifier] = None
        self._is_trained = False
        self._version_counter = 0
    
    def prepare_training_data(
        self,
        fragments: List[AnnotatedFragment]
    ) -> List[Tuple[List[float], float]]:
        """
        Prepare training data from annotated fragments.
        
        Creates pairs of (feature_vector, label).
        """
        data = []
        
        # Create pairs from fragments
        for i, frag_a in enumerate(fragments):
            for frag_b in fragments[i+1:]:
                # Get feature vectors
                vec_a = frag_a.preprocessed_fragment.semantic_features.embedding.values
                vec_b = frag_b.preprocessed_fragment.semantic_features.embedding.values
                
                # Combine vectors (concatenate or difference)
                combined = []
                for a, b in zip(vec_a, vec_b):
                    combined.append(a - b)  # Difference
                    combined.append(a * b)  # Interaction
                
                # Label: 1 if contradiction, 0 otherwise
                is_contradiction = frag_b.fragment_id in frag_a.contradiction_targets
                label = 1.0 if is_contradiction else 0.0
                
                data.append((combined, label))
        
        return data
    
    def train(
        self,
        fragments: List[AnnotatedFragment]
    ) -> Tuple[TrainingRun, TrainedModelArtifact]:
        """
        Train contradiction detector on annotated fragments.
        
        Returns (TrainingRun, TrainedModelArtifact).
        """
        random.seed(self._config.random_seed)
        
        # Prepare data
        training_data = self.prepare_training_data(fragments)
        
        if not training_data:
            raise ValueError("No training data generated")
        
        # Infer input dimension
        input_dim = len(training_data[0][0])
        
        # Initialize classifier
        self._classifier = SimpleClassifier(
            input_dim=input_dim,
            hidden_dim=self._config.hidden_dimension,
            seed=self._config.random_seed
        )
        
        # Training loop
        start_time = datetime.now()
        total_loss = 0.0
        
        for epoch in range(self._config.epochs):
            random.shuffle(training_data)
            epoch_loss = 0.0
            
            for x, y in training_data:
                loss = self._classifier.train_step(
                    x, y, self._config.learning_rate
                )
                epoch_loss += loss
            
            total_loss = epoch_loss / len(training_data)
        
        end_time = datetime.now()
        self._is_trained = True
        self._version_counter += 1
        
        # Create training run record
        run_id = hashlib.sha256(
            f"contra_{self._version_counter}_{start_time.isoformat()}".encode()
        ).hexdigest()[:12]
        
        training_run = TrainingRun(
            run_id=f"run_{run_id}",
            task_id="contradiction_detection",
            config_id=f"config_{run_id}",
            started_at=start_time,
            completed_at=end_time,
            final_loss=total_loss,
            final_metrics=(
                ("loss", total_loss),
                ("samples", float(len(training_data))),
            ),
            status="completed"
        )
        
        # Create model artifact
        weights_hash = hashlib.sha256(
            str(self._classifier.W1).encode()
        ).hexdigest()
        
        artifact = TrainedModelArtifact(
            model_id=f"model_contra_{run_id}",
            model_version=f"contra_v{self._version_counter}",
            task_type=LearningTaskType.CONTRADICTION_DETECTION,
            weights_hash=weights_hash,
            weights_path=f"models/contradiction_{run_id}.pkl",
            training_run_id=training_run.run_id,
            input_schema="Tuple[FeatureVector, FeatureVector]",
            output_schema="float",
            status=ModelStatus.TRAINED,
            created_at=end_time
        )
        
        return training_run, artifact
