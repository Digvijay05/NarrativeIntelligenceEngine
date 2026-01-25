"""
Ingestion Service

Orchestrates RSS feed polling and article extraction.
"""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from pathlib import Path
import asyncio
import time

from .contracts import FeedSource, FetchBatch, FetchResult
from .registry import FeedRegistry
from .fetcher import RSSFetcher
from .extractor import ArticleExtractor
from .storage import IngestionStore


class IngestionService:
    """
    Coordinates feed polling, article extraction, and storage.
    
    DESIGN:
    =======
    1. Poll feeds according to tier-based schedules
    2. Extract full articles for each new item
    3. Store everything (raw + extracted)
    4. Track all failures
    """
    
    def __init__(
        self,
        storage_path: Path,
        config_path: Optional[Path] = None
    ):
        self._registry = FeedRegistry.load(config_path)
        self._fetcher = RSSFetcher()
        self._extractor = ArticleExtractor()
        self._store = IngestionStore(storage_path)
    
    def poll_all_sync(self, extract_articles: bool = True) -> FetchBatch:
        """
        Poll all enabled feeds synchronously.
        
        Returns batch with all results.
        """
        started_at = datetime.utcnow()
        results = []
        
        for source in self._registry.enabled_sources():
            result, payload, items = self._fetcher.fetch_sync(source)
            
            # Store fetch result
            self._store.store_fetch_result(result)
            
            # Store raw payload if available
            if payload:
                self._store.store_rss_payload(payload)
            
            # Store items and extract articles
            if items:
                new_count = self._store.store_rss_items(items)
                
                if extract_articles:
                    for item in items:
                        self._extract_and_store(item, source)
            
            results.append(result)
        
        return FetchBatch(
            batch_id=f"batch_{started_at.strftime('%Y%m%d%H%M%S')}",
            started_at=started_at,
            completed_at=datetime.utcnow(),
            results=tuple(results)
        )
    
    def poll_source_sync(self, source_id: str, extract_articles: bool = True) -> Optional[FetchResult]:
        """Poll a single source."""
        source = self._registry.get(source_id)
        if not source:
            return None
        
        result, payload, items = self._fetcher.fetch_sync(source)
        
        self._store.store_fetch_result(result)
        
        if payload:
            self._store.store_rss_payload(payload)
        
        if items:
            self._store.store_rss_items(items)
            
            if extract_articles:
                for item in items:
                    self._extract_and_store(item, source)
        
        return result
    
    def poll_category_sync(self, category: str, extract_articles: bool = True) -> List[FetchResult]:
        """Poll all feeds in a category."""
        from .contracts import FeedCategory
        
        try:
            cat = FeedCategory(category)
        except ValueError:
            return []
        
        results = []
        for source in self._registry.by_category(cat):
            if source.enabled:
                result = self.poll_source_sync(source.source_id, extract_articles)
                if result:
                    results.append(result)
        
        return results
    
    def _extract_and_store(self, item, source: FeedSource):
        """Extract and store article for an item."""
        result, payload, article = self._extractor.extract_sync(item, source)
        
        self._store.store_fetch_result(result)
        
        if payload:
            self._store.store_article_payload(payload)
        
        if article:
            self._store.store_extracted_article(article)
    
    def get_stats(self) -> dict:
        """Get ingestion statistics."""
        return {
            'registry': self._registry.stats(),
            'storage': self._store.get_stats()
        }
    
    def get_failed_fetches(self, since: Optional[datetime] = None) -> List[dict]:
        """Get failed fetch attempts."""
        return self._store.get_failed_fetches(since)
    
    @property
    def registry(self) -> FeedRegistry:
        return self._registry


def create_service(
    storage_path: str = './data/ingestion',
    config_path: Optional[str] = None
) -> IngestionService:
    """Create ingestion service with defaults."""
    return IngestionService(
        storage_path=Path(storage_path),
        config_path=Path(config_path) if config_path else None
    )
