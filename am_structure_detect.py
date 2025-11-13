#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_structure_detect.py - Structure Detection (MVP v2.0)
=======================================================
Stage 2: Detect document structure (chapters, sections)

Features:
- Chapter detection (patterns: "Chapter 1", "Глава 1", etc)
- Section detection (patterns: "1.1", "Section A", etc)
- TOC-based detection (if available)
- Heuristic-based detection (font size, formatting)
- Quality metrics tracking

Version: 2.0.0
Dependencies: am_common
"""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from am_common import (
    DatasetIO, ConfigLoader, PathManager,
    utc_now_iso
)

logger = logging.getLogger('am_structure_detect')

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"

# Chapter patterns (English)
CHAPTER_PATTERNS_EN = [
    r'^\s*Chapter\s+(\d+|[IVXLCDM]+)\s*[:\-\.]?\s*(.*)$',
    r'^\s*CHAPTER\s+(\d+|[IVXLCDM]+)\s*[:\-\.]?\s*(.*)$',
    r'^\s*Ch\.\s*(\d+)\s*[:\-\.]?\s*(.*)$',
]

# Chapter patterns (Russian)
CHAPTER_PATTERNS_RU = [
    r'^\s*Глава\s+(\d+|[IVXLCDM]+)\s*[:\-\.]?\s*(.*)$',
    r'^\s*ГЛАВА\s+(\d+|[IVXLCDM]+)\s*[:\-\.]?\s*(.*)$',
]

# Section patterns
SECTION_PATTERNS = [
    r'^\s*(\d+\.\d+(?:\.\d+)?)\s+(.+)$',  # 1.1 Title, 1.1.1 Title
    r'^\s*Section\s+(\d+|[A-Z])\s*[:\-\.]?\s*(.*)$',
    r'^\s*§\s*(\d+)\s*[:\-\.]?\s*(.*)$',  # § 1 Title
]

# Special markers
TOC_MARKERS = [
    'table of contents',
    'contents',
    'содержание',
    'оглавление',
]

APPENDIX_MARKERS = [
    'appendix',
    'приложение',
]


class StructureDetector:
    """Detect document structure from text."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.min_chapter_gap = config.get('min_chapter_gap', 3)  # min pages between chapters
        self.min_title_length = config.get('min_title_length', 3)
        self.max_title_length = config.get('max_title_length', 200)
        
        # Compile patterns
        self.chapter_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE) 
            for p in CHAPTER_PATTERNS_EN + CHAPTER_PATTERNS_RU
        ]
        self.section_patterns = [
            re.compile(p, re.MULTILINE) 
            for p in SECTION_PATTERNS
        ]
    
    def detect_chapters(self, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect chapters in document.
        
        Returns:
            List of chapter info: [{'page_num': 1, 'num': '1', 'title': 'Introduction'}]
        """
        chapters = []
        last_chapter_page = -self.min_chapter_gap
        
        for card in cards:
            page_num = card.get('page_num', 0)
            text = card.get('segment', '')
            
            # Skip if too close to last chapter
            if page_num - last_chapter_page < self.min_chapter_gap:
                continue
            
            # Try to match chapter patterns
            chapter_info = self._match_chapter(text)
            if chapter_info:
                chapter_num, chapter_title = chapter_info
                
                # Validate title length
                if self.min_title_length <= len(chapter_title) <= self.max_title_length:
                    chapters.append({
                        'page_num': page_num,
                        'num': chapter_num,
                        'title': chapter_title.strip(),
                        'detection_method': 'pattern',
                    })
                    last_chapter_page = page_num
        
        return chapters
    
    def _match_chapter(self, text: str) -> Optional[Tuple[str, str]]:
        """Try to match chapter pattern in text."""
        # Check first few lines (chapters usually at page start)
        lines = text.strip().split('\n')[:5]
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Try each pattern
            for pattern in self.chapter_patterns:
                match = pattern.match(line)
                if match:
                    chapter_num = match.group(1)
                    chapter_title = match.group(2) if match.lastindex >= 2 else ''
                    return (chapter_num, chapter_title)
        
        return None
    
    def detect_sections(self, cards: List[Dict[str, Any]], 
                       chapters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Detect sections within chapters.
        
        Returns:
            List of section info
        """
        sections = []
        current_chapter_num = None
        
        # Build chapter page map
        chapter_pages = {ch['page_num']: ch['num'] for ch in chapters}
        
        for card in cards:
            page_num = card.get('page_num', 0)
            text = card.get('segment', '')
            
            # Update current chapter
            if page_num in chapter_pages:
                current_chapter_num = chapter_pages[page_num]
            
            # Try to match section patterns
            section_info = self._match_section(text)
            if section_info:
                section_num, section_title = section_info
                
                # Validate
                if self.min_title_length <= len(section_title) <= self.max_title_length:
                    sections.append({
                        'page_num': page_num,
                        'chapter_num': current_chapter_num,
                        'num': section_num,
                        'title': section_title.strip(),
                        'detection_method': 'pattern',
                    })
        
        return sections
    
    def _match_section(self, text: str) -> Optional[Tuple[str, str]]:
        """Try to match section pattern in text."""
        lines = text.strip().split('\n')[:10]  # Check more lines for sections
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            for pattern in self.section_patterns:
                match = pattern.match(line)
                if match:
                    section_num = match.group(1)
                    section_title = match.group(2) if match.lastindex >= 2 else ''
                    return (section_num, section_title)
        
        return None
    
    def detect_toc(self, cards: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Try to detect Table of Contents.
        
        Returns:
            TOC info if found
        """
        for i, card in enumerate(cards[:20]):  # Check first 20 pages
            text = card.get('segment', '').lower()
            
            # Check for TOC markers
            if any(marker in text for marker in TOC_MARKERS):
                # Estimate TOC span
                toc_pages = [card.get('page_num')]
                
                # Check next few pages
                for j in range(i + 1, min(i + 10, len(cards))):
                    next_text = cards[j].get('segment', '')
                    # TOC usually has lots of numbers (page references)
                    num_count = sum(1 for char in next_text if char.isdigit())
                    if num_count > 50:  # Heuristic
                        toc_pages.append(cards[j].get('page_num'))
                    else:
                        break
                
                return {
                    'found': True,
                    'start_page': toc_pages[0],
                    'end_page': toc_pages[-1],
                    'page_count': len(toc_pages),
                }
        
        return None


class StructureProcessor:
    """Main processor for structure detection."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.stage_config = self.config_loader.get_stage_config('structure_detect')
        
        # Components
        self.path_manager = PathManager()
        self.detector = StructureDetector(self.stage_config)
        
        # Quality tracking
        self.quality_tracker = None
    
    def process_dataset(self, input_path: Path, 
                       output_dir: Optional[Path] = None) -> Path:
        """
        Process dataset to detect structure.
        
        Args:
            input_path: path to structural dataset
            output_dir: output directory (default: auto from PathManager)
            
        Returns:
            path to output dataset with structure
        """
        logger.info(f"Processing: {input_path.name}")
        
        if output_dir is None:
            output_dir = self.path_manager.dataset_structured
        
        # Load dataset
        header, cards, audit, footer = DatasetIO.load(input_path)
        
        # Detect TOC
        toc_info = self.detector.detect_toc(cards)
        if toc_info and toc_info.get('found'):
            logger.info(f"TOC found: pages {toc_info['start_page']}-{toc_info['end_page']}")
        
        # Detect chapters
        chapters = self.detector.detect_chapters(cards)
        logger.info(f"Detected {len(chapters)} chapters")
        
        # Detect sections
        sections = self.detector.detect_sections(cards, chapters)
        logger.info(f"Detected {len(sections)} sections")
        
        # Apply structure to cards
        self._apply_structure(cards, chapters, sections)
        
        # Update header
        header['stage'] = 'structured'
        header['structure_detected_at'] = utc_now_iso()
        header['chapters'] = len(chapters)
        header['sections'] = len(sections)
        if toc_info:
            header['toc'] = toc_info
        
        # Update audit
        audit = self._build_audit(
            cards=cards,
            chapters=chapters,
            sections=sections,
            toc=toc_info,
        )
        
        # Save dataset
        output_path = output_dir / input_path.name
        DatasetIO.save(output_path, header, cards, audit, footer)
        
        # Quality tracking
        if self.quality_tracker:
            metrics = self._calculate_metrics(cards, chapters, sections)
            self.quality_tracker.track('structure_detect', input_path.name, metrics)
        
        logger.info(f"Saved: {output_path.name}")
        return output_path
    
    def _apply_structure(self, cards: List[Dict[str, Any]],
                        chapters: List[Dict[str, Any]],
                        sections: List[Dict[str, Any]]) -> None:
        """Apply detected structure to cards."""
        # Build lookup maps
        chapter_map = {ch['page_num']: ch for ch in chapters}
        section_map = {sec['page_num']: sec for sec in sections}
        
        # Track current chapter/section
        current_chapter = None
        current_section = None
        
        for card in cards:
            page_num = card.get('page_num', 0)
            
            # Update current chapter
            if page_num in chapter_map:
                current_chapter = chapter_map[page_num]
            
            # Update current section
            if page_num in section_map:
                current_section = section_map[page_num]
            
            # Apply to card
            if current_chapter:
                card['chapter_num'] = current_chapter['num']
                card['chapter_title'] = current_chapter['title']
            else:
                card['chapter_num'] = None
                card['chapter_title'] = None
            
            if current_section:
                card['section_num'] = current_section['num']
                card['section_title'] = current_section['title']
            else:
                card['section_num'] = None
                card['section_title'] = None
    
    def _build_audit(self, cards: List[Dict[str, Any]],
                    chapters: List[Dict[str, Any]],
                    sections: List[Dict[str, Any]],
                    toc: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Build audit section."""
        # Calculate coverage
        pages_with_structure = sum(
            1 for card in cards 
            if card.get('chapter_num') or card.get('section_num')
        )
        coverage = pages_with_structure / len(cards) if cards else 0
        
        return {
            'total_cards': len(cards),
            'chapters_detected': len(chapters),
            'sections_detected': len(sections),
            'structure_coverage': round(coverage, 3),
            'toc_found': bool(toc and toc.get('found')),
            'stage': 'structure_detect',
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
    
    def _calculate_metrics(self, cards: List[Dict[str, Any]],
                          chapters: List[Dict[str, Any]],
                          sections: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate quality metrics."""
        total = len(cards)
        pages_with_structure = sum(
            1 for card in cards 
            if card.get('chapter_num') or card.get('section_num')
        )
        
        return {
            'total_pages': total,
            'chapters_detected': len(chapters),
            'sections_detected': len(sections),
            'pages_with_structure': pages_with_structure,
            'structure_coverage': pages_with_structure / total if total > 0 else 0,
            'avg_chapter_length': total / len(chapters) if chapters else 0,
        }


def main():
    """CLI interface."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Structure detection (MVP v2.0)')
    parser.add_argument('-i', '--input', required=True,
                       help='Input dataset or directory')
    parser.add_argument('-o', '--output',
                       help='Output directory')
    parser.add_argument('-c', '--config',
                       help='Config file path')
    parser.add_argument('--pattern', default='*.dataset.jsonl',
                       help='File pattern for directory input')
    
    args = parser.parse_args()
    
    # Initialize processor
    config_path = Path(args.config) if args.config else None
    processor = StructureProcessor(config_path)
    
    # Process
    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else None
    
    if input_path.is_file():
        # Single file
        processor.process_dataset(input_path, output_dir)
    elif input_path.is_dir():
        # Directory
        dataset_files = sorted(input_path.glob(args.pattern))
        logger.info(f"Found {len(dataset_files)} datasets")
        
        for dataset_path in dataset_files:
            try:
                processor.process_dataset(dataset_path, output_dir)
            except Exception as e:
                logger.error(f"Failed to process {dataset_path.name}: {e}")
    else:
        logger.error(f"Invalid input path: {input_path}")
        sys.exit(1)
    
    logger.info("Done!")


if __name__ == '__main__':
    main()