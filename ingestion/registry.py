"""
Feed Registry

Loads and manages feed configurations from feeds.json.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Iterator
import json
from pathlib import Path

from .contracts import FeedSource, FeedCategory, FeedTier, PollConfig


@dataclass
class FeedRegistry:
    """
    Registry of all configured RSS feeds.
    
    Loads from config/feeds.json and provides query methods.
    """
    
    _sources: Dict[str, FeedSource]
    _by_category: Dict[FeedCategory, List[FeedSource]]
    _by_tier: Dict[FeedTier, List[FeedSource]]
    _poll_configs: Dict[str, PollConfig]
    
    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> 'FeedRegistry':
        """Load registry from feeds.json."""
        if config_path is None:
            # Default path relative to project root
            config_path = Path(__file__).parent.parent / 'config' / 'feeds.json'
        
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        sources = {}
        by_category = {cat: [] for cat in FeedCategory}
        by_tier = {tier: [] for tier in FeedTier}
        
        # Load poll configs
        poll_configs = {}
        for poll_type, poll_cfg in config.get('poll_config', {}).items():
            poll_configs[poll_type] = poll_cfg
        
        # Load feeds by category
        for category_name, category_data in config.get('feeds', {}).items():
            try:
                category = FeedCategory(category_name)
            except ValueError:
                continue
            
            tier_num = category_data.get('tier', 2)
            tier = FeedTier(tier_num)
            poll_type = category_data.get('poll_type', 'news')
            
            for source_data in category_data.get('sources', []):
                source = FeedSource(
                    source_id=source_data['id'],
                    name=source_data['name'],
                    url=source_data['url'],
                    category=category,
                    tier=tier,
                    language=source_data.get('language', 'en'),
                    region=source_data.get('region', 'national'),
                    enabled=source_data.get('enabled', True),
                    source_type=source_data.get('source_type', 'news'),
                    notes=source_data.get('notes')
                )
                
                sources[source.source_id] = source
                by_category[category].append(source)
                by_tier[tier].append(source)
        
        return cls(
            _sources=sources,
            _by_category=by_category,
            _by_tier=by_tier,
            _poll_configs=poll_configs
        )
    
    def get(self, source_id: str) -> Optional[FeedSource]:
        """Get source by ID."""
        return self._sources.get(source_id)
    
    def all_sources(self) -> Iterator[FeedSource]:
        """Iterate all sources."""
        yield from self._sources.values()
    
    def enabled_sources(self) -> Iterator[FeedSource]:
        """Iterate only enabled sources."""
        for source in self._sources.values():
            if source.enabled:
                yield source
    
    def by_category(self, category: FeedCategory) -> List[FeedSource]:
        """Get sources by category."""
        return self._by_category.get(category, [])
    
    def by_tier(self, tier: FeedTier) -> List[FeedSource]:
        """Get sources by tier."""
        return self._by_tier.get(tier, [])
    
    def get_poll_interval(self, source: FeedSource) -> int:
        """Get poll interval in minutes for a source."""
        category_name = source.category.value
        poll_type = None
        
        # Map category to poll type
        poll_type_map = {
            FeedCategory.NATIONAL_NEWS: 'news',
            FeedCategory.GOVERNMENT_POLICY: 'policy',
            FeedCategory.BUSINESS_ECONOMY: 'business',
            FeedCategory.REGIONAL: 'regional',
            FeedCategory.INVESTIGATIVE: 'investigative',
            FeedCategory.GLOBAL_CONTEXT: 'global',
            FeedCategory.SPECIALIZED: 'specialized',
        }
        poll_type = poll_type_map.get(source.category, 'news')
        
        config = self._poll_configs.get(poll_type, {})
        return config.get('interval_minutes', 10)
    
    @property
    def total_count(self) -> int:
        """Total number of feeds."""
        return len(self._sources)
    
    @property
    def enabled_count(self) -> int:
        """Number of enabled feeds."""
        return sum(1 for s in self._sources.values() if s.enabled)
    
    def stats(self) -> dict:
        """Get registry statistics."""
        return {
            'total': self.total_count,
            'enabled': self.enabled_count,
            'by_tier': {
                tier.name: len(sources) 
                for tier, sources in self._by_tier.items()
            },
            'by_category': {
                cat.value: len(sources) 
                for cat, sources in self._by_category.items()
            }
        }
