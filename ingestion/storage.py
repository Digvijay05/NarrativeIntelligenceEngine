"""
Ingestion Storage

Persistent storage for raw payloads and extracted content.

PRINCIPLES:
===========
1. NEVER delete raw payloads
2. Store published_at AND fetched_at
3. Track fetch failures as first-class data
4. Support replay from raw payloads
"""

from __future__ import annotations
from typing import Dict, List, Optional, Iterator
from datetime import datetime
from pathlib import Path
import json
import sqlite3
from contextlib import contextmanager

from .contracts import (
    RawRSSPayload, RawArticlePayload, RSSItem, ExtractedArticle,
    FetchResult, FetchStatus
)


class IngestionStore:
    """
    Persistent storage for ingestion data.
    
    Uses SQLite for metadata and file system for raw payloads.
    """
    
    def __init__(self, base_path: Path):
        self._base_path = Path(base_path)
        self._raw_rss_path = self._base_path / 'raw_rss'
        self._raw_articles_path = self._base_path / 'raw_articles'
        self._db_path = self._base_path / 'ingestion.db'
        
        self._ensure_directories()
        self._init_db()
    
    def _ensure_directories(self):
        """Create storage directories."""
        self._base_path.mkdir(parents=True, exist_ok=True)
        self._raw_rss_path.mkdir(exist_ok=True)
        self._raw_articles_path.mkdir(exist_ok=True)
    
    def _init_db(self):
        """Initialize database schema."""
        with self._get_conn() as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS rss_payloads (
                    payload_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    fetched_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    http_status INTEGER,
                    content_type TEXT,
                    content_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL
                );
                
                CREATE TABLE IF NOT EXISTS article_payloads (
                    payload_id TEXT PRIMARY KEY,
                    article_url TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    rss_payload_id TEXT,
                    fetched_at TEXT NOT NULL,
                    http_status INTEGER,
                    content_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    FOREIGN KEY (rss_payload_id) REFERENCES rss_payloads(payload_id)
                );
                
                CREATE TABLE IF NOT EXISTS rss_items (
                    item_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    rss_payload_id TEXT NOT NULL,
                    link TEXT NOT NULL,
                    title TEXT,
                    description TEXT,
                    published_at TEXT,
                    fetched_at TEXT NOT NULL,
                    author TEXT,
                    guid TEXT,
                    content_hash TEXT,
                    FOREIGN KEY (rss_payload_id) REFERENCES rss_payloads(payload_id)
                );
                
                CREATE TABLE IF NOT EXISTS extracted_articles (
                    article_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    rss_item_id TEXT,
                    article_payload_id TEXT,
                    url TEXT NOT NULL,
                    canonical_url TEXT,
                    title TEXT,
                    clean_text TEXT,
                    published_at TEXT,
                    rss_published_at TEXT,
                    fetched_at TEXT NOT NULL,
                    extracted_at TEXT NOT NULL,
                    author TEXT,
                    section TEXT,
                    word_count INTEGER,
                    language TEXT,
                    extraction_method TEXT,
                    extraction_confidence REAL,
                    FOREIGN KEY (rss_item_id) REFERENCES rss_items(item_id),
                    FOREIGN KEY (article_payload_id) REFERENCES article_payloads(payload_id)
                );
                
                CREATE TABLE IF NOT EXISTS fetch_results (
                    result_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL,
                    url TEXT NOT NULL,
                    attempted_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_id TEXT,
                    items_count INTEGER DEFAULT 0,
                    error_message TEXT,
                    http_status INTEGER
                );
                
                CREATE INDEX IF NOT EXISTS idx_rss_payloads_source ON rss_payloads(source_id);
                CREATE INDEX IF NOT EXISTS idx_rss_payloads_fetched ON rss_payloads(fetched_at);
                CREATE INDEX IF NOT EXISTS idx_rss_items_source ON rss_items(source_id);
                CREATE INDEX IF NOT EXISTS idx_rss_items_published ON rss_items(published_at);
                CREATE INDEX IF NOT EXISTS idx_extracted_articles_source ON extracted_articles(source_id);
                CREATE INDEX IF NOT EXISTS idx_fetch_results_source ON fetch_results(source_id);
                CREATE INDEX IF NOT EXISTS idx_fetch_results_status ON fetch_results(status);
            ''')
    
    @contextmanager
    def _get_conn(self):
        """Get database connection."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    # =========================================================================
    # RAW PAYLOAD STORAGE
    # =========================================================================
    
    def store_rss_payload(self, payload: RawRSSPayload) -> str:
        """Store raw RSS payload. Returns file path."""
        # Store raw bytes to file
        date_path = payload.fetched_at.strftime('%Y/%m/%d')
        file_dir = self._raw_rss_path / date_path
        file_dir.mkdir(parents=True, exist_ok=True)
        
        file_name = f"{payload.payload_id}.xml"
        file_path = file_dir / file_name
        file_path.write_bytes(payload.raw_bytes)
        
        # Store metadata to DB
        with self._get_conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO rss_payloads 
                (payload_id, source_id, fetched_at, url, http_status, content_type, content_hash, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                payload.payload_id,
                payload.source_id,
                payload.fetched_at.isoformat(),
                payload.url,
                payload.http_status,
                payload.content_type.value,
                payload.content_hash,
                str(file_path)
            ))
        
        return str(file_path)
    
    def store_article_payload(self, payload: RawArticlePayload) -> str:
        """Store raw article payload. Returns file path."""
        date_path = payload.fetched_at.strftime('%Y/%m/%d')
        file_dir = self._raw_articles_path / date_path
        file_dir.mkdir(parents=True, exist_ok=True)
        
        file_name = f"{payload.payload_id}.html"
        file_path = file_dir / file_name
        file_path.write_bytes(payload.raw_bytes)
        
        with self._get_conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO article_payloads
                (payload_id, article_url, source_id, rss_payload_id, fetched_at, http_status, content_hash, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                payload.payload_id,
                payload.article_url,
                payload.source_id,
                payload.rss_payload_id,
                payload.fetched_at.isoformat(),
                payload.http_status,
                payload.content_hash,
                str(file_path)
            ))
        
        return str(file_path)
    
    # =========================================================================
    # RSS ITEM STORAGE
    # =========================================================================
    
    def store_rss_item(self, item: RSSItem) -> bool:
        """Store RSS item. Returns True if new, False if duplicate."""
        with self._get_conn() as conn:
            # Check for duplicate
            existing = conn.execute(
                'SELECT item_id FROM rss_items WHERE item_id = ?',
                (item.item_id,)
            ).fetchone()
            
            if existing:
                return False
            
            conn.execute('''
                INSERT INTO rss_items
                (item_id, source_id, rss_payload_id, link, title, description,
                 published_at, fetched_at, author, guid, content_hash)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                item.item_id,
                item.source_id,
                item.rss_payload_id,
                item.link,
                item.title,
                item.description,
                item.published_at.isoformat() if item.published_at else None,
                item.fetched_at.isoformat(),
                item.author,
                item.guid,
                item.content_hash()
            ))
            
            return True
    
    def store_rss_items(self, items: List[RSSItem]) -> int:
        """Store multiple RSS items. Returns count of new items."""
        new_count = 0
        for item in items:
            if self.store_rss_item(item):
                new_count += 1
        return new_count
    
    # =========================================================================
    # EXTRACTED ARTICLE STORAGE
    # =========================================================================
    
    def store_extracted_article(self, article: ExtractedArticle) -> bool:
        """Store extracted article. Returns True if new."""
        with self._get_conn() as conn:
            existing = conn.execute(
                'SELECT article_id FROM extracted_articles WHERE article_id = ?',
                (article.article_id,)
            ).fetchone()
            
            if existing:
                return False
            
            conn.execute('''
                INSERT INTO extracted_articles
                (article_id, source_id, rss_item_id, article_payload_id,
                 url, canonical_url, title, clean_text,
                 published_at, rss_published_at, fetched_at, extracted_at,
                 author, section, word_count, language,
                 extraction_method, extraction_confidence)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                article.article_id,
                article.source_id,
                article.rss_item_id,
                article.article_payload_id,
                article.url,
                article.canonical_url,
                article.title,
                article.clean_text,
                article.published_at.isoformat() if article.published_at else None,
                article.rss_published_at.isoformat() if article.rss_published_at else None,
                article.fetched_at.isoformat(),
                article.extracted_at.isoformat(),
                article.author,
                article.section,
                article.word_count,
                article.language,
                article.extraction_method,
                article.extraction_confidence
            ))
            
            return True
    
    # =========================================================================
    # FETCH RESULT STORAGE
    # =========================================================================
    
    def store_fetch_result(self, result: FetchResult):
        """Store fetch result (success or failure)."""
        with self._get_conn() as conn:
            conn.execute('''
                INSERT OR REPLACE INTO fetch_results
                (result_id, source_id, url, attempted_at, completed_at,
                 status, payload_id, items_count, error_message, http_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                result.result_id,
                result.source_id,
                result.url,
                result.attempted_at.isoformat(),
                result.completed_at.isoformat(),
                result.status.value,
                result.payload_id,
                result.items_count,
                result.error_message,
                result.http_status
            ))
    
    # =========================================================================
    # QUERIES
    # =========================================================================
    
    def get_recent_items(self, source_id: str, limit: int = 100) -> List[dict]:
        """Get recent RSS items for a source."""
        with self._get_conn() as conn:
            rows = conn.execute('''
                SELECT * FROM rss_items 
                WHERE source_id = ?
                ORDER BY fetched_at DESC
                LIMIT ?
            ''', (source_id, limit)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_failed_fetches(self, since: Optional[datetime] = None) -> List[dict]:
        """Get failed fetch attempts."""
        with self._get_conn() as conn:
            if since:
                rows = conn.execute('''
                    SELECT * FROM fetch_results
                    WHERE status != ? AND attempted_at > ?
                    ORDER BY attempted_at DESC
                ''', (FetchStatus.SUCCESS.value, since.isoformat())).fetchall()
            else:
                rows = conn.execute('''
                    SELECT * FROM fetch_results
                    WHERE status != ?
                    ORDER BY attempted_at DESC
                ''', (FetchStatus.SUCCESS.value,)).fetchall()
            
            return [dict(row) for row in rows]
    
    def get_stats(self) -> dict:
        """Get storage statistics."""
        with self._get_conn() as conn:
            rss_count = conn.execute('SELECT COUNT(*) FROM rss_payloads').fetchone()[0]
            article_count = conn.execute('SELECT COUNT(*) FROM article_payloads').fetchone()[0]
            item_count = conn.execute('SELECT COUNT(*) FROM rss_items').fetchone()[0]
            extracted_count = conn.execute('SELECT COUNT(*) FROM extracted_articles').fetchone()[0]
            
            success_count = conn.execute(
                'SELECT COUNT(*) FROM fetch_results WHERE status = ?',
                (FetchStatus.SUCCESS.value,)
            ).fetchone()[0]
            
            failure_count = conn.execute(
                'SELECT COUNT(*) FROM fetch_results WHERE status != ?',
                (FetchStatus.SUCCESS.value,)
            ).fetchone()[0]
            
            return {
                'rss_payloads': rss_count,
                'article_payloads': article_count,
                'rss_items': item_count,
                'extracted_articles': extracted_count,
                'successful_fetches': success_count,
                'failed_fetches': failure_count
            }
