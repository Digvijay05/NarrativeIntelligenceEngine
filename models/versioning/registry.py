"""Model registry for version management."""

from __future__ import annotations
from typing import Dict, List, Optional
from datetime import datetime
import hashlib

from ..contracts.model_contracts import TrainedModelArtifact, ModelStatus, ModelRegistry


class ModelRegistryManager:
    """Manage model registry for versioning."""
    
    def __init__(self):
        self._models: Dict[str, List[TrainedModelArtifact]] = {}  # task_type -> versions
        self._active: Dict[str, str] = {}  # task_type -> model_id
    
    def register(self, artifact: TrainedModelArtifact):
        """Register a model artifact."""
        task = artifact.task_type.value
        
        if task not in self._models:
            self._models[task] = []
        
        self._models[task].append(artifact)
    
    def activate(self, task_type: str, model_id: str):
        """Set active model for a task type."""
        self._active[task_type] = model_id
    
    def get_active(self, task_type: str) -> Optional[TrainedModelArtifact]:
        """Get active model for task type."""
        model_id = self._active.get(task_type)
        if not model_id:
            return None
        
        for artifact in self._models.get(task_type, []):
            if artifact.model_id == model_id:
                return artifact
        return None
    
    def get_versions(self, task_type: str) -> List[TrainedModelArtifact]:
        """Get all versions for a task type."""
        return self._models.get(task_type, [])
    
    def get_registry(self) -> ModelRegistry:
        """Get full registry snapshot."""
        all_models = []
        for models in self._models.values():
            all_models.extend(models)
        
        reg_id = hashlib.sha256(
            f"registry|{len(all_models)}|{datetime.now().isoformat()}".encode()
        ).hexdigest()[:12]
        
        return ModelRegistry(
            registry_id=f"reg_{reg_id}",
            models=tuple(all_models),
            active_versions=tuple(self._active.items()),
            updated_at=datetime.now()
        )
