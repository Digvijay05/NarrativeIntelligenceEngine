"""
Article Extractor

Fetches full article content and extracts clean text.

PRINCIPLES:
===========
1. Store raw HTML - never delete
2. Handle paywalls gracefully
3. Extract canonical URL when available
4. Track extraction confidence
"""

from __future__ import annotations
from typing import Optional, Tuple
from datetime import datetime
import hashlib
import re
from html.parser import HTMLParser

import httpx

from .contracts import (
    FeedSource, RSSItem, RawArticlePayload, ExtractedArticle,
    FetchResult, FetchStatus
)


class MLStripper(HTMLParser):
    """Simple HTML tag stripper."""
    
    def __init__(self):
        super().__init__()
        self.reset()
        self.fed = []
        self.skip_tags = {'script', 'style', 'head', 'meta', 'link', 'noscript'}
        self._skip_data = False
    
    def handle_starttag(self, tag, attrs):
        if tag in self.skip_tags:
            self._skip_data = True
    
    def handle_endtag(self, tag):
        if tag in self.skip_tags:
            self._skip_data = False
    
    def handle_data(self, data):
        if not self._skip_data:
            self.fed.append(data)
    
    def get_data(self):
        return ' '.join(self.fed)


class ArticleExtractor:
    """
    Extracts article content from URLs.
    
    GUARANTEES:
    ===========
    1. Raw HTML stored before extraction
    2. Failed fetches return explicit status
    3. Paywalls detected and marked
    """
    
    # Common paywall indicators
    PAYWALL_INDICATORS = [
        'subscribe to continue',
        'subscription required',
        'premium content',
        'members only',
        'sign in to read',
        'login to read',
        'paywall',
        'article limit reached',
    ]
    
    def __init__(
        self,
        timeout: float = 30.0,
        user_agent: str = "NarrativeIntelligence/1.0"
    ):
        self._timeout = timeout
        self._user_agent = user_agent
    
    def extract_sync(
        self,
        item: RSSItem,
        source: FeedSource
    ) -> Tuple[FetchResult, Optional[RawArticlePayload], Optional[ExtractedArticle]]:
        """
        Fetch and extract article content.
        
        Returns:
            - FetchResult (always)
            - RawArticlePayload (if HTTP succeeded)
            - ExtractedArticle (if extraction succeeded)
        """
        attempted_at = datetime.utcnow()
        
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    item.link,
                    headers={'User-Agent': self._user_agent},
                    follow_redirects=True
                )
            
            completed_at = datetime.utcnow()
            
            # Create raw payload
            raw_payload = RawArticlePayload.create(
                article_url=item.link,
                source_id=source.source_id,
                rss_payload_id=item.rss_payload_id,
                http_status=response.status_code,
                raw_bytes=response.content,
                headers=dict(response.headers),
                fetched_at=completed_at
            )
            
            # Check HTTP status
            if response.status_code != 200:
                result = FetchResult(
                    result_id=self._generate_result_id(item, attempted_at),
                    source_id=source.source_id,
                    url=item.link,
                    attempted_at=attempted_at,
                    completed_at=completed_at,
                    status=FetchStatus.HTTP_ERROR,
                    payload_id=raw_payload.payload_id,
                    http_status=response.status_code,
                    error_message=f"HTTP {response.status_code}"
                )
                return result, raw_payload, None
            
            # Extract content
            try:
                html_content = response.content.decode('utf-8', errors='replace')
                
                # Check for paywall
                if self._detect_paywall(html_content):
                    result = FetchResult(
                        result_id=self._generate_result_id(item, attempted_at),
                        source_id=source.source_id,
                        url=item.link,
                        attempted_at=attempted_at,
                        completed_at=completed_at,
                        status=FetchStatus.PAYWALL_BLOCKED,
                        payload_id=raw_payload.payload_id,
                        error_message="Paywall detected"
                    )
                    return result, raw_payload, None
                
                # Extract article
                article = self._extract_article(
                    html_content=html_content,
                    item=item,
                    payload=raw_payload,
                    source=source
                )
                
                result = FetchResult(
                    result_id=self._generate_result_id(item, attempted_at),
                    source_id=source.source_id,
                    url=item.link,
                    attempted_at=attempted_at,
                    completed_at=completed_at,
                    status=FetchStatus.SUCCESS,
                    payload_id=raw_payload.payload_id,
                    items_count=1
                )
                return result, raw_payload, article
                
            except Exception as e:
                result = FetchResult(
                    result_id=self._generate_result_id(item, attempted_at),
                    source_id=source.source_id,
                    url=item.link,
                    attempted_at=attempted_at,
                    completed_at=datetime.utcnow(),
                    status=FetchStatus.PARSE_ERROR,
                    payload_id=raw_payload.payload_id,
                    error_message=str(e)
                )
                return result, raw_payload, None
        
        except httpx.TimeoutException:
            return self._timeout_result(item, source, attempted_at), None, None
        
        except Exception as e:
            return self._error_result(item, source, attempted_at, e), None, None
    
    def _extract_article(
        self,
        html_content: str,
        item: RSSItem,
        payload: RawArticlePayload,
        source: FeedSource
    ) -> ExtractedArticle:
        """Extract article from HTML."""
        # Extract title from HTML (or use RSS title)
        title = self._extract_title(html_content) or item.title
        
        # Extract canonical URL
        canonical_url = self._extract_canonical(html_content)
        
        # Extract clean text
        clean_text = self._extract_text(html_content)
        
        # Extract metadata
        author = self._extract_meta(html_content, 'author') or item.author
        section = self._extract_meta(html_content, 'section')
        
        # Extract published date from HTML
        html_published = self._extract_published_date(html_content)
        
        # Extract tags
        tags = self._extract_tags(html_content)
        
        # Generate article ID
        article_id = f"art_{hashlib.sha256(item.link.encode()).hexdigest()[:16]}"
        
        return ExtractedArticle(
            article_id=article_id,
            source_id=source.source_id,
            rss_item_id=item.item_id,
            article_payload_id=payload.payload_id,
            url=item.link,
            canonical_url=canonical_url,
            title=title,
            clean_text=clean_text,
            published_at=html_published,
            rss_published_at=item.published_at,
            fetched_at=payload.fetched_at,
            extracted_at=datetime.utcnow(),
            author=author,
            section=section,
            tags=tuple(tags) if tags else (),
            word_count=len(clean_text.split()),
            language=source.language,
            extraction_method="basic",
            extraction_confidence=0.8
        )
    
    def _extract_title(self, html: str) -> Optional[str]:
        """Extract title from HTML."""
        # Try og:title
        match = re.search(r'<meta[^>]*property=["\']og:title["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if match:
            return match.group(1)
        
        # Try title tag
        match = re.search(r'<title>([^<]+)</title>', html, re.I)
        if match:
            return match.group(1).strip()
        
        return None
    
    def _extract_canonical(self, html: str) -> Optional[str]:
        """Extract canonical URL."""
        match = re.search(r'<link[^>]*rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, re.I)
        if match:
            return match.group(1)
        
        match = re.search(r'<meta[^>]*property=["\']og:url["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if match:
            return match.group(1)
        
        return None
    
    def _extract_text(self, html: str) -> str:
        """Extract clean text from HTML."""
        # Remove common non-content elements
        html = re.sub(r'<(header|footer|nav|aside|sidebar)[^>]*>.*?</\1>', '', html, flags=re.I|re.S)
        html = re.sub(r'<(script|style|noscript)[^>]*>.*?</\1>', '', html, flags=re.I|re.S)
        
        # Try to find main content
        main_content = None
        
        # Look for article tag
        match = re.search(r'<article[^>]*>(.*?)</article>', html, re.I|re.S)
        if match:
            main_content = match.group(1)
        
        # Look for main tag
        if not main_content:
            match = re.search(r'<main[^>]*>(.*?)</main>', html, re.I|re.S)
            if match:
                main_content = match.group(1)
        
        # Look for content div
        if not main_content:
            for pattern in [
                r'<div[^>]*class=["\'][^"\']*content[^"\']*["\'][^>]*>(.*?)</div>',
                r'<div[^>]*id=["\'][^"\']*content[^"\']*["\'][^>]*>(.*?)</div>',
                r'<div[^>]*class=["\'][^"\']*article[^"\']*["\'][^>]*>(.*?)</div>',
            ]:
                match = re.search(pattern, html, re.I|re.S)
                if match:
                    main_content = match.group(1)
                    break
        
        # Fall back to body
        if not main_content:
            match = re.search(r'<body[^>]*>(.*?)</body>', html, re.I|re.S)
            if match:
                main_content = match.group(1)
            else:
                main_content = html
        
        # Strip HTML tags
        stripper = MLStripper()
        stripper.feed(main_content)
        text = stripper.get_data()
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
    
    def _extract_meta(self, html: str, name: str) -> Optional[str]:
        """Extract meta tag content."""
        patterns = [
            rf'<meta[^>]*name=["\'](?:author|article:{name})["\'][^>]*content=["\']([^"\']+)["\']',
            rf'<meta[^>]*property=["\'](?:article:{name})["\'][^>]*content=["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.I)
            if match:
                return match.group(1)
        
        return None
    
    def _extract_published_date(self, html: str) -> Optional[datetime]:
        """Extract published date from HTML."""
        patterns = [
            r'<meta[^>]*property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)["\']',
            r'<time[^>]*datetime=["\']([^"\']+)["\']',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.I)
            if match:
                date_str = match.group(1)
                try:
                    clean = re.sub(r'[Zz]$', '+00:00', date_str)
                    return datetime.fromisoformat(clean)
                except:
                    pass
        
        return None
    
    def _extract_tags(self, html: str) -> list:
        """Extract article tags/keywords."""
        tags = []
        
        # Meta keywords
        match = re.search(r'<meta[^>]*name=["\']keywords["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        if match:
            tags.extend([t.strip() for t in match.group(1).split(',')])
        
        # Article tags
        matches = re.findall(r'<meta[^>]*property=["\']article:tag["\'][^>]*content=["\']([^"\']+)["\']', html, re.I)
        tags.extend(matches)
        
        return list(set(tags))[:20]  # Limit to 20 tags
    
    def _detect_paywall(self, html: str) -> bool:
        """Detect if page is behind paywall."""
        html_lower = html.lower()
        
        for indicator in self.PAYWALL_INDICATORS:
            if indicator in html_lower:
                return True
        
        return False
    
    def _generate_result_id(self, item: RSSItem, attempted_at: datetime) -> str:
        ts = attempted_at.strftime('%Y%m%d%H%M%S')
        return f"extract_{item.item_id}_{ts}"
    
    def _timeout_result(self, item: RSSItem, source: FeedSource, attempted_at: datetime) -> FetchResult:
        return FetchResult(
            result_id=self._generate_result_id(item, attempted_at),
            source_id=source.source_id,
            url=item.link,
            attempted_at=attempted_at,
            completed_at=datetime.utcnow(),
            status=FetchStatus.TIMEOUT,
            error_message="Request timed out"
        )
    
    def _error_result(self, item: RSSItem, source: FeedSource, attempted_at: datetime, error: Exception) -> FetchResult:
        return FetchResult(
            result_id=self._generate_result_id(item, attempted_at),
            source_id=source.source_id,
            url=item.link,
            attempted_at=attempted_at,
            completed_at=datetime.utcnow(),
            status=FetchStatus.NETWORK_ERROR,
            error_message=str(error)
        )
