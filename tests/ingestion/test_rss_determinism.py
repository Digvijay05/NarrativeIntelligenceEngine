
import pytest
import os
import shutil
from unittest.mock import MagicMock, patch
from backend.ingestion.rss_fetcher import RssFetcher
from backend.ingestion.extractor import RssExtractor
from backend.contracts.base import Timestamp

TEST_STORAGE_DIR = "./data/test_rss_capsules"

@pytest.fixture
def clean_storage():
    if os.path.exists(TEST_STORAGE_DIR):
        shutil.rmtree(TEST_STORAGE_DIR)
    os.makedirs(TEST_STORAGE_DIR)
    yield TEST_STORAGE_DIR
    if os.path.exists(TEST_STORAGE_DIR):
        shutil.rmtree(TEST_STORAGE_DIR)

def test_fetcher_persistence(clean_storage):
    """Verify raw bytes are persisted before parsing."""
    fetcher = RssFetcher(clean_storage)
    
    mock_xml = b"""<rss version="2.0"><channel><title>Test</title></channel></rss>"""
    
    with patch('requests.get') as mock_get:
        mock_response = MagicMock()
        mock_response.content = mock_xml
        mock_response.status_code = 200
        mock_get.return_value = mock_response
        
        # Action
        capsule = fetcher.fetch_source("test_src", "http://example.com/rss")
        
        # Verification
        assert capsule is not None
        assert os.path.exists(capsule.file_path)
        with open(capsule.file_path, 'rb') as f:
            saved_bytes = f.read()
            assert saved_bytes == mock_xml
            
        assert capsule.source_id == "test_src"

def test_extractor_determinism(clean_storage):
    """Verify extraction is structural and deterministic."""
    # Setup - Create a dummy capsule file
    xml_content = """<?xml version="1.0" ?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>Article 1</title>
      <link>http://example.com/1</link>
      <description>Summary of article 1</description>
      <pubDate>Mon, 01 Jan 2024 10:00:00 GMT</pubDate>
      <guid>guid-1</guid>
    </item>
    <item>
      <title>Article 2</title>
      <link>http://example.com/2</link>
      <!-- Missing Description -->
    </item>
  </channel>
</rss>
"""
    capsule_path = os.path.join(clean_storage, "test.xml")
    with open(capsule_path, "w") as f:
        f.write(xml_content)
        
    extractor = RssExtractor()
    items = extractor.extract_capsule(capsule_path)
    
    # Assertions
    assert len(items) == 2
    
    # Item 1 - Full
    assert items[0].title == "Article 1"
    assert items[0].link == "http://example.com/1"
    assert items[0].summary == "Summary of article 1"
    assert items[0].published_str == "Mon, 01 Jan 2024 10:00:00 GMT"
    assert items[0].guid == "guid-1"
    
    # Item 2 - Partial (No Inference!)
    assert items[1].title == "Article 2"
    assert items[1].link == "http://example.com/2"
    assert items[1].summary == "" # Should be empty string, not None or guessed
    assert items[1].published_str == ""
