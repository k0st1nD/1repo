# 🔌 Archivist Magika - Multi-Source Architecture (POST-MVP)

## ⚠️ STATUS: POST-MVP Feature

**This is NOT part of MVP v2.0**

MVP v2.0 focuses on **PDF only** with enhancements (OCR, tables, structure detection).

Multi-source support will be added **after MVP is complete and tested**.

**Timeline:**
- Week 1-2: MVP v2.0 (PDF) ← Current
- Week 3-4: Testing & polish
- Week 5-6: Multi-source (Confluence, DOCX, TXT, HTML) ← This document

---

## 📊 Концепция: Unified Dataset Format

**Идея:** Разные источники (PDF, Confluence, Notion, etc) → Единый формат датасета

```
PDF Books          Confluence         Notion           Google Docs
    ↓                  ↓                 ↓                  ↓
[source adapter]   [source adapter]  [source adapter]  [source adapter]
    ↓                  ↓                 ↓                  ↓
    └──────────────────┴─────────────────┴──────────────────┘
                            ↓
                    UNIFIED DATASET
                    (*.dataset.jsonl)
                            ↓
              [общий pipeline: summarize → extended → finalize → chunk → embed]
                            ↓
                       RAG SEARCH
```

---

## 📁 Обновлённая структура проекта

```
archivist-magika/
├── core/
│   ├── am_common.py
│   ├── am_config.yaml
│   └── am_logging.py
│
├── sources/                          # ✨ NEW! Source adapters
│   ├── __init__.py
│   ├── base.py                       # BaseSourceAdapter (abstract)
│   │
│   ├── pdf/                          # PDF источник (существующий)
│   │   ├── __init__.py
│   │   ├── am_structural.py          # PDF → dataset
│   │   └── am_structure_detect.py
│   │
│   ├── confluence/                   # ✨ Confluence источник
│   │   ├── __init__.py
│   │   ├── confluence_extractor.py   # REST API / Export → dataset
│   │   ├── html_cleaner.py           # HTML → Markdown/text
│   │   └── metadata_mapper.py        # Confluence meta → unified meta
│   │
│   └── notion/                       # ✨ Future: Notion
│       ├── __init__.py
│       └── notion_extractor.py
│
├── pipeline/                         # Общий pipeline для всех источников
│   ├── am_summarize.py               # L1/L2 summaries
│   ├── am_extended.py                # merge + continuity + dedup
│   ├── am_finalize.py                # validation
│   ├── am_chunk.py                   # chunking
│   └── am_embed.py                   # embedding
│
├── rag/
│   ├── search.py
│   └── index_manager.py
│
├── data/
│   ├── sources/
│   │   ├── pdf/                      # Исходные PDF
│   │   ├── confluence/               # ✨ Confluence exports
│   │   └── notion/                   # ✨ Notion exports
│   │
│   ├── datasets/
│   │   ├── raw/                      # После source adapters (UNIFIED)
│   │   ├── summarized/
│   │   ├── extended/
│   │   ├── final/
│   │   └── chunks/
│   │
│   └── indexes/
│       ├── faiss/
│       └── metadata/
```

---

## 🎯 Unified Dataset Format Specification

### Header Fields:
```json
{
  "segment_id": "__header__",
  "source": {
    "type": "pdf|confluence|notion|...",          // ✨ Source type
    "source_id": "12345",                         // Source-specific ID
    "title": "Accelerate",
    "author": "Nicole Forsgren",                  // PDF: author / Confluence: creator
    "url": "https://company.atlassian.net/...",  // Confluence: page URL / PDF: null
    "space": "ENG",                               // Confluence: space / PDF: null
    "publisher": "IT Revolution",                 // PDF only
    "year": 2018,
    "pages": 257,                                 // PDF: page count / Confluence: null
    "language": "en",
    "document_type": "book|wiki_page|blog_post",  // ✨ Unified type
    "path": ["Parent Page", "Child Page"],        // Confluence: breadcrumbs / PDF: null
    "labels": ["devops", "architecture"],         // Confluence: labels / PDF: extracted
    "version": 17,                                // Confluence: version / PDF: 1
    "created": "2023-02-01T12:00:00Z",
    "updated": "2024-06-05T08:10:00Z"
  },
  "book": "accelerate",                           // PDF: book name / Confluence: space key
  "total_cards": 257,
  "segment_ids": ["00001", "00002", ...],
  "dataset_created_at": "2025-01-28T12:00:00Z",
  "version": "v4.3.8",
  "product": "archivist magika v4.3.8"
}
```

### Card Fields (Unified):
```json
{
  "segment_id": "00042",
  "section_path": "chapter/5/section/5.1",        // PDF: chapters / Confluence: page hierarchy
  "segment": "Full text content...",
  "summary": {
    "level1": "Short summary",
    "level3": "[pp.42-42]"                        // PDF: pages / Confluence: [chunk.42]
  },
  "structure": {
    "chapter": "Chapter 5: Architecture",         // PDF: detected / Confluence: parent page
    "section": "5.1 Loosely Coupled",
    "level": 2
  },
  "flags": {
    "has_image": true,
    "has_table": true,
    "has_code": false                             // ✨ Confluence: code blocks
  },
  "source_metadata": {                            // ✨ Source-specific metadata
    // For PDF:
    "page_num": 42,
    "ocr_used": false,
    
    // For Confluence:
    "page_id": "12345",
    "space_key": "ENG",
    "parent_id": "11111",
    "content_status": "current",
    "restrictions": []
  }
}
```

---

## 🔌 Base Source Adapter Interface

```python
# sources/base.py

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Dict, Any

class BaseSourceAdapter(ABC):
    """
    Abstract base class for all source adapters.
    Each source (PDF, Confluence, Notion, etc) implements this interface.
    """
    
    @abstractmethod
    def extract(self, source_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract content from source and convert to unified dataset format.
        
        Args:
            source_path: Path to source (file, directory, export, etc)
            config: Source-specific configuration
            
        Returns:
            Dict with header, cards, audit, footer in unified format
        """
        pass
    
    @abstractmethod
    def validate_source(self, source_path: Path) -> bool:
        """Check if source is valid and can be processed."""
        pass
    
    @abstractmethod
    def get_source_type(self) -> str:
        """Return source type identifier (pdf, confluence, notion, etc)."""
        pass
    
    def normalize_metadata(self, raw_metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert source-specific metadata to unified format.
        Can be overridden for custom normalization.
        """
        return raw_metadata
```

---

## 📘 Confluence Source Adapter

```yaml
# config/sources/confluence.yaml

confluence:
  enabled: true
  
  # Input format
  input:
    format: "rest_export"              # "rest_export" | "html_export" | "xml_export"
    root_path: "data/sources/confluence/"
  
  # Extraction settings
  extraction:
    content_types:
      - "page"                         # Include regular pages
      - "blogpost"                     # Include blog posts
      - "comment"                      # Include comments (optional)
    
    # HTML cleaning
    html_cleaning:
      remove_macros: false             # Keep macros as placeholders
      convert_to_markdown: true        # Convert to Markdown
      preserve_code_blocks: true
      preserve_tables: true
      remove_attachments_section: true
  
  # Metadata mapping
  metadata:
    map_space_to_book: true            # space_key → book field
    map_labels_to_topics: true         # labels → topics
    include_page_hierarchy: true       # ancestors → path
    include_version_history: false     # For MVP: only current version
  
  # Segmentation
  segmentation:
    strategy: "by_page"                # "by_page" | "by_heading" | "by_section"
    
    # If by_heading:
    heading_levels: [1, 2]             # Split on h1, h2
    min_segment_length: 100            # Minimum chars per segment
  
  # Structure detection
  structure:
    detect_from_headings: true
    use_page_hierarchy: true           # Parent pages → chapters
    create_toc: true

# Mapping rules: Confluence → Unified Format
mapping:
  source_type: "confluence"
  
  header:
    title: "meta.title"
    author: "meta.version.by.displayName"
    url: "meta._links.webui"
    space: "meta.spaceKey"
    document_type: "page|blogpost"     # From content_type
    path: "ancestors[].title"
    labels: "meta.metadata.labels.results[].name"
    version: "meta.version.number"
    created: "meta.version.when"
    updated: "meta.version.when"
  
  card:
    segment_id: "auto_generated"       # Format: confluence_<pageId>_<index>
    section_path: "auto_generated"     # From hierarchy
    segment: "body.storage.value"      # After cleaning
    source_metadata:
      page_id: "meta.id"
      space_key: "meta.spaceKey"
      parent_id: "meta.ancestors[-1].id"
```

---

## 💻 Confluence Extractor Implementation

```python
# sources/confluence/confluence_extractor.py

from pathlib import Path
from typing import Dict, Any, List
import json
from bs4 import BeautifulSoup
import re

from sources.base import BaseSourceAdapter
from core.am_common import utc_now_iso, sha256_hex


class ConfluenceSourceAdapter(BaseSourceAdapter):
    """
    Confluence REST Export → Unified Dataset Format
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.html_cleaner = HTMLCleaner(config.get('html_cleaning', {}))
    
    def get_source_type(self) -> str:
        return "confluence"
    
    def validate_source(self, source_path: Path) -> bool:
        """Check if this is valid Confluence export."""
        # Look for typical structure: page/ and blogpost/ directories
        return (
            source_path.is_dir() and
            (source_path / "page").exists()
        )
    
    def extract(self, source_path: Path, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract Confluence pages and convert to unified dataset.
        """
        # Load all pages metadata first (for hierarchy)
        index = self._load_index(source_path)
        
        # Extract pages
        cards = []
        for content_type, page_dir, meta, body_html in self._iter_pages(source_path):
            # Clean HTML
            cleaned_text = self.html_cleaner.to_markdown(body_html)
            
            # Create segments (for now: 1 page = 1 segment)
            segments = self._create_segments(cleaned_text, meta, index)
            cards.extend(segments)
        
        # Build header
        header = self._build_header(cards, source_path, index)
        
        # Audit
        audit = {
            "segment_id": "__audit__",
            "created_at": utc_now_iso(),
            "ruleset": "v4.3.8",
            "source_type": "confluence",
            "total_pages": len(index),
            "total_segments": len(cards)
        }
        
        # Footer
        footer = {
            "segment_id": "__footer__",
            "created_at": utc_now_iso(),
            "manifest_sha256": None,  # Will be calculated on save
            "version": "v4.3.8",
            "product": "archivist magika v4.3.8"
        }
        
        return {
            "header": header,
            "cards": cards,
            "audit": audit,
            "footer": footer
        }
    
    def _load_index(self, root: Path) -> Dict[str, Dict]:
        """Load all page metadata for hierarchy building."""
        index = {}
        for content_type in ["page", "blogpost"]:
            type_dir = root / content_type
            if not type_dir.exists():
                continue
            
            for page_dir in type_dir.glob("*__*"):
                meta_path = page_dir / "meta.json"
                if meta_path.exists():
                    meta = json.loads(meta_path.read_text("utf-8"))
                    index[meta["id"]] = meta
        
        return index
    
    def _iter_pages(self, root: Path):
        """Iterate over all pages in export."""
        for content_type in ["page", "blogpost"]:
            type_dir = root / content_type
            if not type_dir.exists():
                continue
            
            for page_dir in type_dir.glob("*__*"):
                meta_path = page_dir / "meta.json"
                body_path = page_dir / "page.storage.html"
                
                if not (meta_path.exists() and body_path.exists()):
                    continue
                
                meta = json.loads(meta_path.read_text("utf-8"))
                body = body_path.read_text("utf-8")
                
                yield content_type, page_dir, meta, body
    
    def _create_segments(self, text: str, meta: Dict, index: Dict) -> List[Dict]:
        """
        Create segments from page content.
        For MVP: 1 page = 1 segment
        """
        # Build path (breadcrumbs)
        path = self._build_path(meta, index)
        
        # Extract labels
        labels = self._extract_labels(meta)
        
        # Build URL
        url = self._build_url(meta)
        
        segment = {
            "segment_id": f"confluence_{meta['id']}_001",
            "section_path": "/".join(path),
            "segment": text,
            "summary": {
                "level3": f"[confluence.{meta['id']}]"
            },
            "structure": {
                "path": path,
                "level": len(path)
            },
            "flags": {
                "has_code": self._detect_code_blocks(text),
                "has_table": self._detect_tables(text)
            },
            "source_metadata": {
                "source_type": "confluence",
                "page_id": meta["id"],
                "space_key": meta.get("spaceKey", ""),
                "parent_id": meta.get("ancestors", [])[-1] if meta.get("ancestors") else None,
                "url": url,
                "title": meta.get("title", ""),
                "labels": labels,
                "version": meta.get("version", {}).get("number"),
                "created": meta.get("version", {}).get("when"),
                "updated": meta.get("version", {}).get("when")
            }
        }
        
        return [segment]
    
    def _build_path(self, meta: Dict, index: Dict) -> List[str]:
        """Build page hierarchy path from ancestors."""
        path = []
        for ancestor_id in meta.get("ancestors", []):
            ancestor = index.get(ancestor_id)
            if ancestor:
                path.append(ancestor.get("title", str(ancestor_id)))
        
        path.append(meta.get("title", "Untitled"))
        return path
    
    def _extract_labels(self, meta: Dict) -> List[str]:
        """Extract labels from metadata."""
        labels = meta.get("labels", [])
        if not labels:
            labels = meta.get("metadata", {}).get("labels", {}).get("results", [])
        
        if labels and isinstance(labels[0], dict):
            return [l.get("name") for l in labels]
        
        return labels or []
    
    def _build_url(self, meta: Dict) -> str:
        """Build full page URL."""
        links = meta.get("_links", {})
        url = links.get("tinyui") or links.get("webui") or ""
        base = links.get("base", "")
        
        if base and url and not url.startswith("http"):
            return base.rstrip("/") + url
        
        return url
    
    def _detect_code_blocks(self, text: str) -> bool:
        """Simple detection of code blocks in text."""
        return "```" in text or "<code>" in text
    
    def _detect_tables(self, text: str) -> bool:
        """Simple detection of tables in text."""
        return "|" in text and "---" in text  # Markdown table
    
    def _build_header(self, cards: List[Dict], source_path: Path, index: Dict) -> Dict:
        """Build unified header."""
        # Get space info from first page
        first_space = ""
        if cards:
            first_space = cards[0].get("source_metadata", {}).get("space_key", "")
        
        return {
            "segment_id": "__header__",
            "source": {
                "type": "confluence",
                "source_id": source_path.name,
                "title": f"Confluence Space: {first_space}",
                "space": first_space,
                "document_type": "wiki_space",
                "language": "en",  # TODO: detect
                "pages": len(index)
            },
            "book": first_space or source_path.name,
            "total_cards": len(cards),
            "segment_ids": [c["segment_id"] for c in cards],
            "dataset_created_at": utc_now_iso(),
            "version": "v4.3.8",
            "product": "archivist magika v4.3.8"
        }


class HTMLCleaner:
    """Clean Confluence HTML/XHTML to Markdown."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def to_markdown(self, html: str) -> str:
        """Convert Confluence Storage HTML to Markdown-like text."""
        if not html:
            return ""
        
        soup = BeautifulSoup(html, "lxml-xml")
        
        # Remove scripts, styles
        for tag in soup.find_all(["script", "style"]):
            tag.decompose()
        
        # Confluence macros: keep as placeholders
        if not self.config.get("remove_macros", False):
            for macro in soup.find_all(re.compile(r"^ac:")):
                name = macro.get("ac:name") or macro.name
                macro.replace_with(soup.new_string(f"<<macro:{name}>>"))
        
        # Headings → Markdown
        for level in range(6, 0, -1):
            for h in soup.find_all(f"h{level}"):
                text = h.get_text(" ", strip=True)
                h.replace_with(soup.new_string(f"\n{'#'*level} {text}\n"))
        
        # Links: [text](href)
        for a in soup.find_all("a"):
            text = a.get_text(" ", strip=True)
            href = a.get("href") or ""
            a.replace_with(soup.new_string(f"[{text}]({href})" if href else text))
        
        # Code blocks
        if self.config.get("preserve_code_blocks", True):
            for code in soup.find_all("code"):
                text = code.get_text()
                code.replace_with(soup.new_string(f"```\n{text}\n```"))
        
        # Tables: simple text conversion
        if self.config.get("preserve_tables", True):
            for table in soup.find_all("table"):
                # Convert to markdown table (simplified)
                rows = []
                for tr in table.find_all("tr"):
                    cells = [td.get_text(" ", strip=True) for td in tr.find_all(["td", "th"])]
                    rows.append("| " + " | ".join(cells) + " |")
                
                if rows:
                    # Add header separator
                    if len(rows) > 0:
                        sep = "|" + "|".join(["---"] * len(rows[0].split("|")[1:-1])) + "|"
                        rows.insert(1, sep)
                    
                    table.replace_with(soup.new_string("\n" + "\n".join(rows) + "\n"))
        
        # Get text
        text = soup.get_text("\n", strip=True)
        
        # Normalize whitespace
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        
        return text.strip()
```

---

## 🚀 Integration into MVP

### Updated am_config_v2.0.yaml:

```yaml
# Source adapters configuration
sources:
  enabled:
    - "pdf"
    - "confluence"       # ✨ Enable Confluence
  
  pdf:
    # Existing PDF config...
  
  confluence:           # ✨ NEW
    enabled: true
    config_file: "config/sources/confluence.yaml"
    
    input:
      format: "rest_export"
      root_path: "data/sources/confluence/"
    
    extraction:
      content_types: ["page", "blogpost"]
      html_cleaning:
        convert_to_markdown: true
        preserve_code_blocks: true
        preserve_tables: true
    
    segmentation:
      strategy: "by_page"
```

### Updated run_mvp.py:

```python
# run_mvp.py

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", choices=["pdf", "confluence", "all"], default="all")
    args = parser.parse_args()
    
    if args.source in ["pdf", "all"]:
        process_pdf_sources()
    
    if args.source in ["confluence", "all"]:
        process_confluence_sources()
```

---

## 📋 Implementation Plan for Confluence

### MVP Phase (optional - после основного MVP):
```
Day 13-14: Confluence Support
  - sources/base.py (BaseSourceAdapter)
  - sources/confluence/confluence_extractor.py
  - sources/confluence/html_cleaner.py
  - Test with real Confluence export
```

### Future Enhancements:
- Notion adapter
- Google Docs adapter
- Direct API integration (не через export)
- Incremental updates

---

## 🎯 Benefits of This Architecture:

1. **Модульность:** Легко добавлять новые источники
2. **Единый формат:** Всё в unified dataset → один pipeline
3. **Переиспользование:** Summarize, chunk, embed работают для всех источников
4. **Фильтрация:** Search может фильтровать по source_type
5. **Расширяемость:** BaseSourceAdapter → легко добавить что угодно

---

**Версия:** 1.0  
**Created:** 2025-01-28
