"""Query caching for inference."""

from __future__ import annotations
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib

from ...contracts.inference_contracts import CacheEntry, CacheStats


class QueryCache:
    """Cache for inference queries."""
    
    def __init__(self, max_entries: int = 1000, ttl_seconds: int = 3600):
        self._max_entries = max_entries
        self._ttl = ttl_seconds
        self._cache: Dict[str, CacheEntry] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0
    
    def get(self, key: str) -> Optional[tuple]:
        """Get cached response."""
        entry = self._cache.get(key)
        
        if entry is None:
            self._misses += 1
            return None
        
        if datetime.now() > entry.expires_at:
            del self._cache[key]
            self._misses += 1
            return None
        
        self._hits += 1
        # Update hit count (create new entry)
        self._cache[key] = CacheEntry(
            cache_key=entry.cache_key,
            request_hash=entry.request_hash,
            response_data=entry.response_data,
            model_version=entry.model_version,
            created_at=entry.created_at,
            expires_at=entry.expires_at,
            hit_count=entry.hit_count + 1
        )
        
        return entry.response_data
    
    def put(
        self,
        key: str,
        request_hash: str,
        response_data: tuple,
        model_version: str
    ):
        """Store response in cache."""
        if len(self._cache) >= self._max_entries:
            self._evict_oldest()
        
        now = datetime.now()
        entry = CacheEntry(
            cache_key=key,
            request_hash=request_hash,
            response_data=response_data,
            model_version=model_version,
            created_at=now,
            expires_at=now + timedelta(seconds=self._ttl),
            hit_count=0
        )
        
        self._cache[key] = entry
    
    def _evict_oldest(self):
        """Evict oldest entry."""
        if not self._cache:
            return
        
        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]
        self._evictions += 1
    
    def invalidate(self, key: str):
        """Invalidate a cache entry."""
        if key in self._cache:
            del self._cache[key]
    
    def clear(self):
        """Clear all cache entries."""
        self._cache.clear()
    
    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        
        memory_estimate = sum(
            len(str(e.response_data)) for e in self._cache.values()
        )
        
        return CacheStats(
            total_entries=len(self._cache),
            hit_count=self._hits,
            miss_count=self._misses,
            eviction_count=self._evictions,
            memory_usage_bytes=memory_estimate,
            hit_rate=hit_rate,
            computed_at=datetime.now()
        )
