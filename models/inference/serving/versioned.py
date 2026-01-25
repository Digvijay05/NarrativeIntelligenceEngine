"""Versioned model serving."""

from __future__ import annotations
from typing import Dict, Optional, List, Any
from datetime import datetime
import hashlib

from ...contracts.inference_contracts import ModelVersion, ModelEndpoint


class VersionedModelServer:
    """Version-aware model serving."""
    
    def __init__(self):
        self._versions: Dict[str, Dict[str, ModelVersion]] = {}  # model_id -> version_id -> version
        self._active: Dict[str, str] = {}  # model_id -> active_version_id
        self._models: Dict[str, Any] = {}  # version_id -> model
    
    def register_version(
        self,
        model_id: str,
        version_number: str,
        model: Any,
        weights_hash: str,
        config_hash: str
    ) -> ModelVersion:
        """Register a new model version."""
        version_id = hashlib.sha256(
            f"{model_id}|{version_number}|{weights_hash}".encode()
        ).hexdigest()[:16]
        
        version = ModelVersion(
            version_id=f"ver_{version_id}",
            model_id=model_id,
            version_number=version_number,
            deployed_at=datetime.now(),
            is_active=False,
            weights_hash=weights_hash,
            config_hash=config_hash
        )
        
        if model_id not in self._versions:
            self._versions[model_id] = {}
        
        self._versions[model_id][version.version_id] = version
        self._models[version.version_id] = model
        
        return version
    
    def activate_version(self, model_id: str, version_id: str):
        """Activate a specific version."""
        if model_id in self._versions and version_id in self._versions[model_id]:
            self._active[model_id] = version_id
    
    def get_active_version(self, model_id: str) -> Optional[ModelVersion]:
        """Get currently active version."""
        version_id = self._active.get(model_id)
        if version_id and model_id in self._versions:
            return self._versions[model_id].get(version_id)
        return None
    
    def get_model(self, model_id: str, version_id: str = None) -> Optional[Any]:
        """Get model by ID and optional version."""
        if version_id:
            return self._models.get(version_id)
        
        active_version_id = self._active.get(model_id)
        if active_version_id:
            return self._models.get(active_version_id)
        
        return None
    
    def list_versions(self, model_id: str) -> List[ModelVersion]:
        """List all versions for a model."""
        if model_id not in self._versions:
            return []
        return list(self._versions[model_id].values())
    
    def rollback(self, model_id: str, version_id: str) -> bool:
        """Rollback to a previous version."""
        if model_id in self._versions and version_id in self._versions[model_id]:
            self._active[model_id] = version_id
            return True
        return False
