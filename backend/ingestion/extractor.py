"""
Deterministic RSS Extractor
===========================

Responsibility: Parse RawCapsule XML into structured data.
Constraint: NO INFERENCE. Extract what is there.
"""

import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import List, Optional, Dict
from datetime import datetime

@dataclass(frozen=True)
class ExtractedItem:
    """Raw extracted structure. Strings only."""
    title: str
    link: str
    summary: str
    published_str: Optional[str]
    guid: str

class RssExtractor:
    
    def extract_capsule(self, file_path: str) -> List[ExtractedItem]:
        """
        Parse XML file key structural elements.
        Supports RSS 2.0 and simplistic Atom.
        """
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Simple Namespace stripping for consistency
            # (Crude but effective for "no magic")
            items = []
            
            # 1. RSS 2.0 <item>
            if root.tag == 'rss' or root.find('channel'):
                 # Look for channel/item
                 channel = root.find('channel')
                 if channel:
                     for item in channel.findall('item'):
                         items.append(self._parse_rss_item(item))
            
            # 2. Atom <entry> (Namespaced usually)
            # Handling namespaces in ET is verbose, using a simple wildcard search for now
            # or strictly checking string endings if needed.
            elif 'feed' in root.tag:
                 # Atom
                 for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                     items.append(self._parse_atom_entry(entry))
                     
            return items
            
        except Exception as e:
            print(f"[!] Extraction failed for {file_path}: {e}")
            return []

    def _parse_rss_item(self, element: ET.Element) -> ExtractedItem:
        return ExtractedItem(
            title=self._get_text(element, 'title'),
            link=self._get_text(element, 'link'),
            summary=self._get_text(element, 'description'),
            published_str=self._get_text(element, 'pubDate'),
            guid=self._get_text(element, 'guid') or self._get_text(element, 'link')
        )

    def _parse_atom_entry(self, element: ET.Element) -> ExtractedItem:
        # User defined simple Atom handling
        # Atom links are attributes <link href="..." />
        ns = "{http://www.w3.org/2005/Atom}"
        
        link = ""
        link_elem = element.find(f'{ns}link')
        if link_elem is not None:
            link = link_elem.attrib.get('href', "")
            
        return ExtractedItem(
            title=self._get_text(element, f'{ns}title'),
            link=link,
            summary=self._get_text(element, f'{ns}summary') or self._get_text(element, f'{ns}content'),
            published_str=self._get_text(element, f'{ns}published') or self._get_text(element, f'{ns}updated'),
            guid=self._get_text(element, f'{ns}id') or link
        )

    def _get_text(self, parent: ET.Element, tag: str) -> str:
        """Safe text extraction."""
        node = parent.find(tag)
        if node is not None and node.text:
            return node.text.strip()
        return ""
