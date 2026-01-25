"""Temporal indexing for query acceleration."""

from __future__ import annotations
from typing import Dict, List, Tuple
from datetime import datetime
import hashlib
import bisect

from ...contracts.inference_contracts import IndexConfig, IndexStats
from ...contracts.data_contracts import AnnotatedFragment


class TemporalIndexer:
    """Index fragments for fast temporal queries."""
    
    def __init__(self):
        self._indices: Dict[str, Dict] = {}  # index_id -> index data
        self._configs: Dict[str, IndexConfig] = {}
    
    def create_index(
        self,
        index_name: str,
        indexed_fields: Tuple[str, ...],
        partition_strategy: str = "daily"
    ) -> IndexConfig:
        """Create a temporal index configuration."""
        index_id = hashlib.sha256(
            f"{index_name}|{','.join(indexed_fields)}".encode()
        ).hexdigest()[:12]
        
        config = IndexConfig(
            index_id=f"idx_{index_id}",
            index_type="temporal",
            indexed_fields=indexed_fields,
            partition_strategy=partition_strategy,
            created_at=datetime.now()
        )
        
        self._configs[config.index_id] = config
        self._indices[config.index_id] = {
            'timestamps': [],
            'fragment_ids': [],
            'partitions': {}
        }
        
        return config
    
    def add_to_index(
        self,
        index_id: str,
        fragments: List[AnnotatedFragment]
    ):
        """Add fragments to an index."""
        if index_id not in self._indices:
            return
        
        index = self._indices[index_id]
        
        for frag in fragments:
            ts = frag.preprocessed_fragment.temporal_features.timestamp
            ts_key = ts.timestamp()
            
            # Insert sorted
            pos = bisect.bisect_left(index['timestamps'], ts_key)
            index['timestamps'].insert(pos, ts_key)
            index['fragment_ids'].insert(pos, frag.fragment_id)
            
            # Update partition
            partition_key = self._get_partition_key(ts, self._configs[index_id].partition_strategy)
            if partition_key not in index['partitions']:
                index['partitions'][partition_key] = []
            index['partitions'][partition_key].append(frag.fragment_id)
    
    def query_range(
        self,
        index_id: str,
        start_time: datetime,
        end_time: datetime
    ) -> List[str]:
        """Query fragments in time range."""
        if index_id not in self._indices:
            return []
        
        index = self._indices[index_id]
        start_key = start_time.timestamp()
        end_key = end_time.timestamp()
        
        start_pos = bisect.bisect_left(index['timestamps'], start_key)
        end_pos = bisect.bisect_right(index['timestamps'], end_key)
        
        return index['fragment_ids'][start_pos:end_pos]
    
    def _get_partition_key(self, ts: datetime, strategy: str) -> str:
        """Get partition key for timestamp."""
        if strategy == "daily":
            return ts.strftime("%Y-%m-%d")
        elif strategy == "hourly":
            return ts.strftime("%Y-%m-%d-%H")
        else:
            return ts.strftime("%Y-%m")
    
    def get_stats(self, index_id: str) -> IndexStats:
        """Get index statistics."""
        if index_id not in self._indices:
            return None
        
        index = self._indices[index_id]
        
        return IndexStats(
            index_id=index_id,
            entry_count=len(index['fragment_ids']),
            size_bytes=len(str(index)),  # Rough estimate
            query_speedup=5.0,  # Estimated speedup
            last_rebuild=datetime.now()
        )
