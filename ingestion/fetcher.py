"""
RSS Fetcher

Fetches RSS feeds and extracts items.

PRINCIPLES:
===========
1. Store raw XML - never delete
2. Failed fetches are first-class events
3. Parse with maximum tolerance
4. Track published_at vs fetched_at
"""

from __future__ import annotations
from typing import List, Optional, Tuple
from datetime import datetime
import hashlib
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
import re

import httpx

from .contracts import (
    FeedSource, RawRSSPayload, RSSItem, FetchResult, FetchStatus, ContentType
)


class RSSFetcher:
    """
    Fetches and parses RSS feeds.
    
    GUARANTEES:
    ===========
    1. Raw XML stored before parsing
    2. Failed fetches return FetchResult with error details
    3. Parse errors don't lose raw data
    """
    
    def __init__(
        self,
        timeout: float = 30.0,
        user_agent: str = "NarrativeIntelligence/1.0"
    ):
        self._timeout = timeout
        self._user_agent = user_agent
    
    async def fetch(self, source: FeedSource) -> Tuple[FetchResult, Optional[RawRSSPayload], List[RSSItem]]:
        """
        Fetch a feed and parse items.
        
        Returns:
            - FetchResult (always)
            - RawRSSPayload (if HTTP succeeded)
            - List[RSSItem] (if parsing succeeded)
        """
        attempted_at = datetime.utcnow()
        
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.get(
                    source.url,
                    headers={'User-Agent': self._user_agent},
                    follow_redirects=True
                )
            
            completed_at = datetime.utcnow()
            
            # Create raw payload regardless of status
            raw_payload = RawRSSPayload.create(
                source_id=source.source_id,
                url=source.url,
                http_status=response.status_code,
                raw_bytes=response.content,
                headers=dict(response.headers),
                fetched_at=completed_at
            )
            
            # Check HTTP status
            if response.status_code != 200:
                result = FetchResult(
                    result_id=self._generate_result_id(source, attempted_at),
                    source_id=source.source_id,
                    url=source.url,
                    attempted_at=attempted_at,
                    completed_at=completed_at,
                    status=FetchStatus.HTTP_ERROR,
                    payload_id=raw_payload.payload_id,
                    http_status=response.status_code,
                    error_message=f"HTTP {response.status_code}"
                )
                return result, raw_payload, []
            
            # Parse RSS
            try:
                items = self._parse_rss(
                    raw_bytes=response.content,
                    source_id=source.source_id,
                    payload_id=raw_payload.payload_id,
                    fetched_at=completed_at
                )
                
                result = FetchResult(
                    result_id=self._generate_result_id(source, attempted_at),
                    source_id=source.source_id,
                    url=source.url,
                    attempted_at=attempted_at,
                    completed_at=completed_at,
                    status=FetchStatus.SUCCESS,
                    payload_id=raw_payload.payload_id,
                    items_count=len(items)
                )
                return result, raw_payload, items
                
            except Exception as e:
                result = FetchResult(
                    result_id=self._generate_result_id(source, attempted_at),
                    source_id=source.source_id,
                    url=source.url,
                    attempted_at=attempted_at,
                    completed_at=datetime.utcnow(),
                    status=FetchStatus.PARSE_ERROR,
                    payload_id=raw_payload.payload_id,
                    error_message=str(e)
                )
                return result, raw_payload, []
        
        except httpx.TimeoutException:
            return self._timeout_result(source, attempted_at), None, []
        
        except httpx.NetworkError as e:
            return self._network_error_result(source, attempted_at, e), None, []
        
        except Exception as e:
            return self._generic_error_result(source, attempted_at, e), None, []
    
    def fetch_sync(self, source: FeedSource) -> Tuple[FetchResult, Optional[RawRSSPayload], List[RSSItem]]:
        """Synchronous version of fetch."""
        attempted_at = datetime.utcnow()
        
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    source.url,
                    headers={'User-Agent': self._user_agent},
                    follow_redirects=True
                )
            
            completed_at = datetime.utcnow()
            
            raw_payload = RawRSSPayload.create(
                source_id=source.source_id,
                url=source.url,
                http_status=response.status_code,
                raw_bytes=response.content,
                headers=dict(response.headers),
                fetched_at=completed_at
            )
            
            if response.status_code != 200:
                result = FetchResult(
                    result_id=self._generate_result_id(source, attempted_at),
                    source_id=source.source_id,
                    url=source.url,
                    attempted_at=attempted_at,
                    completed_at=completed_at,
                    status=FetchStatus.HTTP_ERROR,
                    payload_id=raw_payload.payload_id,
                    http_status=response.status_code,
                    error_message=f"HTTP {response.status_code}"
                )
                return result, raw_payload, []
            
            try:
                items = self._parse_rss(
                    raw_bytes=response.content,
                    source_id=source.source_id,
                    payload_id=raw_payload.payload_id,
                    fetched_at=completed_at
                )
                
                result = FetchResult(
                    result_id=self._generate_result_id(source, attempted_at),
                    source_id=source.source_id,
                    url=source.url,
                    attempted_at=attempted_at,
                    completed_at=completed_at,
                    status=FetchStatus.SUCCESS,
                    payload_id=raw_payload.payload_id,
                    items_count=len(items)
                )
                return result, raw_payload, items
                
            except Exception as e:
                result = FetchResult(
                    result_id=self._generate_result_id(source, attempted_at),
                    source_id=source.source_id,
                    url=source.url,
                    attempted_at=attempted_at,
                    completed_at=datetime.utcnow(),
                    status=FetchStatus.PARSE_ERROR,
                    payload_id=raw_payload.payload_id,
                    error_message=str(e)
                )
                return result, raw_payload, []
        
        except httpx.TimeoutException:
            return self._timeout_result(source, attempted_at), None, []
        
        except Exception as e:
            return self._generic_error_result(source, attempted_at, e), None, []
    
    def _parse_rss(
        self,
        raw_bytes: bytes,
        source_id: str,
        payload_id: str,
        fetched_at: datetime
    ) -> List[RSSItem]:
        """Parse RSS/Atom XML into items."""
        items = []
        
        # Try to decode
        try:
            content = raw_bytes.decode('utf-8')
        except UnicodeDecodeError:
            content = raw_bytes.decode('latin-1')
        
        # Parse XML
        root = ET.fromstring(content)
        
        # Detect format (RSS 2.0 vs Atom)
        if root.tag == 'rss' or root.tag.endswith('rss'):
            items = self._parse_rss2(root, source_id, payload_id, fetched_at)
        elif 'Atom' in root.tag or 'atom' in root.tag or root.tag == 'feed':
            items = self._parse_atom(root, source_id, payload_id, fetched_at)
        else:
            # Try RSS 2.0 parsing anyway
            items = self._parse_rss2(root, source_id, payload_id, fetched_at)
        
        return items
    
    def _parse_rss2(
        self,
        root: ET.Element,
        source_id: str,
        payload_id: str,
        fetched_at: datetime
    ) -> List[RSSItem]:
        """Parse RSS 2.0 format."""
        items = []
        
        # Find channel
        channel = root.find('channel')
        if channel is None:
            channel = root
        
        # Find items
        for item in channel.findall('item'):
            title = self._get_text(item, 'title', '')
            link = self._get_text(item, 'link', '')
            description = self._get_text(item, 'description', '')
            
            # Skip if no link
            if not link:
                continue
            
            # Parse published date
            pub_date = self._get_text(item, 'pubDate', '')
            published_at = self._parse_date(pub_date)
            
            # Get other fields
            author = self._get_text(item, 'author', None) or self._get_text(item, 'dc:creator', None)
            guid = self._get_text(item, 'guid', None)
            
            # Get categories
            categories = tuple(
                cat.text or '' for cat in item.findall('category') if cat.text
            )
            
            # Generate item ID
            item_id = self._generate_item_id(source_id, link, guid)
            
            items.append(RSSItem(
                item_id=item_id,
                source_id=source_id,
                rss_payload_id=payload_id,
                title=title,
                link=link,
                description=description,
                published_at=published_at,
                fetched_at=fetched_at,
                author=author,
                categories=categories,
                guid=guid
            ))
        
        return items
    
    def _parse_atom(
        self,
        root: ET.Element,
        source_id: str,
        payload_id: str,
        fetched_at: datetime
    ) -> List[RSSItem]:
        """Parse Atom format."""
        items = []
        
        # Namespace handling
        ns = {'atom': 'http://www.w3.org/2005/Atom'}
        
        for entry in root.findall('atom:entry', ns) or root.findall('entry'):
            title = self._get_text(entry, 'atom:title', '', ns) or self._get_text(entry, 'title', '')
            
            # Get link (prefer alternate)
            link = ''
            for link_elem in entry.findall('atom:link', ns) or entry.findall('link'):
                rel = link_elem.get('rel', 'alternate')
                if rel == 'alternate':
                    link = link_elem.get('href', '')
                    break
            if not link:
                link_elem = entry.find('atom:link', ns) or entry.find('link')
                if link_elem is not None:
                    link = link_elem.get('href', '')
            
            if not link:
                continue
            
            description = (
                self._get_text(entry, 'atom:summary', '', ns) or 
                self._get_text(entry, 'summary', '') or
                self._get_text(entry, 'atom:content', '', ns) or
                self._get_text(entry, 'content', '')
            )
            
            # Parse date
            updated = self._get_text(entry, 'atom:updated', '', ns) or self._get_text(entry, 'updated', '')
            published = self._get_text(entry, 'atom:published', '', ns) or self._get_text(entry, 'published', '')
            published_at = self._parse_date(published or updated)
            
            # Author
            author_elem = entry.find('atom:author', ns) or entry.find('author')
            author = None
            if author_elem is not None:
                author = self._get_text(author_elem, 'atom:name', None, ns) or self._get_text(author_elem, 'name', None)
            
            # ID
            guid = self._get_text(entry, 'atom:id', None, ns) or self._get_text(entry, 'id', None)
            
            # Categories
            categories = tuple(
                cat.get('term', '') for cat in (entry.findall('atom:category', ns) or entry.findall('category'))
                if cat.get('term')
            )
            
            item_id = self._generate_item_id(source_id, link, guid)
            
            items.append(RSSItem(
                item_id=item_id,
                source_id=source_id,
                rss_payload_id=payload_id,
                title=title,
                link=link,
                description=description,
                published_at=published_at,
                fetched_at=fetched_at,
                author=author,
                categories=categories,
                guid=guid
            ))
        
        return items
    
    def _get_text(self, elem: ET.Element, tag: str, default: Optional[str], ns: dict = None) -> Optional[str]:
        """Get text from child element."""
        if ns:
            child = elem.find(tag, ns)
        else:
            child = elem.find(tag)
        
        if child is not None and child.text:
            return child.text.strip()
        return default
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_str:
            return None
        
        # Try RFC 2822 (common in RSS)
        try:
            return parsedate_to_datetime(date_str)
        except:
            pass
        
        # Try ISO 8601
        try:
            # Remove timezone suffix for parsing
            clean = re.sub(r'[Zz]$', '+00:00', date_str)
            return datetime.fromisoformat(clean)
        except:
            pass
        
        return None
    
    def _generate_item_id(self, source_id: str, link: str, guid: Optional[str]) -> str:
        """Generate unique item ID."""
        content = guid or link
        hash_val = hashlib.sha256(f"{source_id}|{content}".encode()).hexdigest()[:12]
        return f"item_{source_id}_{hash_val}"
    
    def _generate_result_id(self, source: FeedSource, attempted_at: datetime) -> str:
        """Generate fetch result ID."""
        ts = attempted_at.strftime('%Y%m%d%H%M%S')
        return f"fetch_{source.source_id}_{ts}"
    
    def _timeout_result(self, source: FeedSource, attempted_at: datetime) -> FetchResult:
        return FetchResult(
            result_id=self._generate_result_id(source, attempted_at),
            source_id=source.source_id,
            url=source.url,
            attempted_at=attempted_at,
            completed_at=datetime.utcnow(),
            status=FetchStatus.TIMEOUT,
            error_message="Request timed out"
        )
    
    def _network_error_result(self, source: FeedSource, attempted_at: datetime, error: Exception) -> FetchResult:
        return FetchResult(
            result_id=self._generate_result_id(source, attempted_at),
            source_id=source.source_id,
            url=source.url,
            attempted_at=attempted_at,
            completed_at=datetime.utcnow(),
            status=FetchStatus.NETWORK_ERROR,
            error_message=str(error)
        )
    
    def _generic_error_result(self, source: FeedSource, attempted_at: datetime, error: Exception) -> FetchResult:
        return FetchResult(
            result_id=self._generate_result_id(source, attempted_at),
            source_id=source.source_id,
            url=source.url,
            attempted_at=attempted_at,
            completed_at=datetime.utcnow(),
            status=FetchStatus.NETWORK_ERROR,
            error_message=str(error)
        )
