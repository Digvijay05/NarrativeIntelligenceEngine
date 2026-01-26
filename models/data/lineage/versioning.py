"""
Data Lineage and Versioning

Tracks transformation history and versions of data entities.

BOUNDARY ENFORCEMENT:
- Pure data tracking, no transformation logic
- Immutable records
- Supports replay and audit
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime
import hashlib


from ...contracts.data_contracts import DataLineageRecord, DataVersion


# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class LineageConfig:
    """Configuration for lineage tracking."""
    max_history_depth: int = 100
    version_format: str = "v{sequence}"


# =============================================================================
# LINEAGE TRACKER
# =============================================================================

class LineageTracker:
    """
    Track data lineage for audit and replay.
    
    Records all transformations applied to data entities.
    
    BOUNDARY ENFORCEMENT:
    - Append-only records
    - No data transformation
    - Pure tracking
    """
    
    def __init__(self, config: Optional[LineageConfig] = None):
        self._config = config or LineageConfig()
        self._records: List[DataLineageRecord] = []
        self._entity_records: Dict[str, List[str]] = {}  # entity_id -> record_ids
        self._record_counter = 0
    
    def record_operation(
        self,
        entity_id: str,
        entity_type: str,
        operation: str,
        input_versions: Tuple[str, ...],
        output_version: str,
        operator_version: str,
        metadata: Optional[Dict[str, str]] = None
    ) -> DataLineageRecord:
        """
        Record a data transformation operation.
        
        Returns the created lineage record.
        """
        self._record_counter += 1
        
        record_id = hashlib.sha256(
            f"{entity_id}|{operation}|{self._record_counter}".encode()
        ).hexdigest()[:16]
        
        record = DataLineageRecord(
            record_id=f"lin_{record_id}",
            entity_id=entity_id,
            entity_type=entity_type,
            operation=operation,
            input_versions=input_versions,
            output_version=output_version,
            timestamp=datetime.now(),
            operator_version=operator_version,
            metadata=tuple(metadata.items()) if metadata else ()
        )
        
        self._records.append(record)
        
        if entity_id not in self._entity_records:
            self._entity_records[entity_id] = []
        self._entity_records[entity_id].append(record.record_id)
        
        return record
    
    def get_entity_history(
        self,
        entity_id: str
    ) -> List[DataLineageRecord]:
        """Get all lineage records for an entity."""
        record_ids = self._entity_records.get(entity_id, [])
        return [r for r in self._records if r.record_id in record_ids]
    
    def get_ancestors(
        self,
        entity_id: str,
        depth: int = 10
    ) -> List[DataLineageRecord]:
        """
        Get ancestor records (inputs that led to this entity).
        
        Traces back through input_versions.
        """
        ancestors = []
        visited = set()
        queue = [entity_id]
        
        while queue and len(ancestors) < depth:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            
            history = self.get_entity_history(current)
            for record in history:
                if record not in ancestors:
                    ancestors.append(record)
                    for input_ver in record.input_versions:
                        # Extract entity_id from version if possible
                        queue.append(input_ver)
        
        return ancestors[:depth]
    
    def get_all_records(self) -> List[DataLineageRecord]:
        """Get all lineage records (read-only copy)."""
        return list(self._records)


# =============================================================================
# VERSION MANAGER
# =============================================================================

class VersionManager:
    """
    Manage versions of data entities.
    
    Provides version creation, comparison, and lookup.
    
    BOUNDARY ENFORCEMENT:
    - Append-only version creation
    - Immutable versions
    - No data transformation
    """
    
    def __init__(self, config: Optional[LineageConfig] = None):
        self._config = config or LineageConfig()
        self._versions: Dict[str, DataVersion] = {}  # version_id -> version
        self._entity_versions: Dict[str, List[str]] = {}  # entity_id -> version_ids
        self._counters: Dict[str, int] = {}  # entity_id -> sequence counter
    
    def create_version(
        self,
        entity_id: str,
        content_hash: str,
        parent_version: Optional[str] = None
    ) -> DataVersion:
        """
        Create a new version for an entity.
        
        Returns the created version.
        """
        # Get next sequence number
        if entity_id not in self._counters:
            self._counters[entity_id] = 0
        self._counters[entity_id] += 1
        sequence = self._counters[entity_id]
        
        # Generate version ID
        version_id = hashlib.sha256(
            f"{entity_id}|{sequence}|{content_hash}".encode()
        ).hexdigest()[:16]
        
        version = DataVersion(
            version_id=f"ver_{version_id}",
            entity_id=entity_id,
            sequence_number=sequence,
            parent_version=parent_version,
            created_at=datetime.now(),
            content_hash=content_hash
        )
        
        self._versions[version.version_id] = version
        
        if entity_id not in self._entity_versions:
            self._entity_versions[entity_id] = []
        self._entity_versions[entity_id].append(version.version_id)
        
        return version
    
    def get_version(self, version_id: str) -> Optional[DataVersion]:
        """Get a specific version by ID."""
        return self._versions.get(version_id)
    
    def get_entity_versions(
        self,
        entity_id: str
    ) -> List[DataVersion]:
        """Get all versions of an entity in order."""
        version_ids = self._entity_versions.get(entity_id, [])
        versions = [self._versions[vid] for vid in version_ids if vid in self._versions]
        return sorted(versions, key=lambda v: v.sequence_number)
    
    def get_latest_version(
        self,
        entity_id: str
    ) -> Optional[DataVersion]:
        """Get the latest version of an entity."""
        versions = self.get_entity_versions(entity_id)
        return versions[-1] if versions else None
    
    def compare_versions(
        self,
        version_a_id: str,
        version_b_id: str
    ) -> Dict[str, Tuple]:
        """
        Compare two versions.
        
        Returns dict of differences.
        """
        version_a = self.get_version(version_a_id)
        version_b = self.get_version(version_b_id)
        
        if not version_a or not version_b:
            return {'error': ('missing_version', None)}
        
        differences = {}
        
        # Compare sequence
        if version_a.sequence_number != version_b.sequence_number:
            differences['sequence'] = (
                version_a.sequence_number,
                version_b.sequence_number
            )
        
        # Compare content hash
        if version_a.content_hash != version_b.content_hash:
            differences['content_hash'] = (
                version_a.content_hash,
                version_b.content_hash
            )
        
        # Compare timestamps
        if version_a.created_at != version_b.created_at:
            differences['created_at'] = (
                version_a.created_at.isoformat(),
                version_b.created_at.isoformat()
            )
        
        return differences
    
    def get_version_chain(
        self,
        version_id: str,
        max_depth: int = 50
    ) -> List[DataVersion]:
        """
        Get the chain of versions back to the root.
        
        Follows parent_version links.
        """
        chain = []
        current_id = version_id
        
        while current_id and len(chain) < max_depth:
            version = self.get_version(current_id)
            if not version:
                break
            chain.append(version)
            current_id = version.parent_version
        
        return chain
