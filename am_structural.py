#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_structural.py - Structural Extraction (MVP v2.0)
===================================================
Stage 1: PDF → structural dataset (1 page = 1 card)

Features:
- OCR support (Tesseract) for scanned pages
- Table extraction (pdfplumber)
- PDF metadata extraction
- Quality metrics tracking
- Text normalization

Version: 2.0.0
Dependencies: pdfplumber, pytesseract, Pillow, PyYAML
"""

import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pdfplumber
from PIL import Image

# OCR imports (optional)
try:
    import pytesseract
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("[WARN] pytesseract not available. OCR disabled.")

# Project imports
from am_common import (
    DatasetIO, TextNormalizer, ConfigLoader, PathManager,
    utc_now_iso, sha256_file, format_size
)

logger = logging.getLogger('am_structural')

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"


class PDFExtractor:
    """PDF extraction with OCR and table support."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ocr_config = config.get('ocr', {})
        self.table_config = config.get('tables', {})
        self.normalizer = TextNormalizer()
        
        # OCR settings
        self.ocr_enabled = self.ocr_config.get('enabled', True) and OCR_AVAILABLE
        self.ocr_threshold = self.ocr_config.get('text_threshold', 50)
        self.tesseract_lang = self.ocr_config.get('tesseract_lang', 'eng')
        self.tesseract_config = self.ocr_config.get('tesseract_config', '--psm 6')
    
    def extract_page(self, page) -> Tuple[str, bool, float]:
        """
        Extract text from page with OCR fallback.
        
        Returns:
            (text, ocr_used, ocr_confidence)
        """
        # Try regular extraction
        text = page.extract_text() or ""
        text_clean = text.strip()
        
        # Check if OCR needed
        needs_ocr = (
            self.ocr_enabled and
            len(text_clean) < self.ocr_threshold
        )
        
        if needs_ocr:
            return self._extract_with_ocr(page)
        
        # Normal extraction
        normalized = self.normalizer.normalize(text)
        return normalized, False, 0.0
    
    def _extract_with_ocr(self, page) -> Tuple[str, bool, float]:
        """Extract text using OCR."""
        try:
            # Convert page to image
            img = page.to_image(resolution=300)
            pil_img = img.original
            
            # Run Tesseract
            data = pytesseract.image_to_data(
                pil_img,
                lang=self.tesseract_lang,
                config=self.tesseract_config,
                output_type=pytesseract.Output.DICT
            )
            
            # Extract text and confidence
            text_parts = []
            confidences = []
            
            for i, word in enumerate(data['text']):
                if word.strip():
                    text_parts.append(word)
                    conf = float(data['conf'][i])
                    if conf > 0:
                        confidences.append(conf)
            
            text = ' '.join(text_parts)
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            
            normalized = self.normalizer.normalize(text)
            return normalized, True, avg_conf / 100.0
            
        except Exception as e:
            logger.warning(f"OCR failed: {e}")
            return "", True, 0.0
    
    def extract_tables(self, page) -> List[Dict[str, Any]]:
        """Extract tables from page."""
        if not self.table_config.get('enabled', True):
            return []
        
        try:
            tables = page.extract_tables()
            if not tables:
                return []
            
            result = []
            for idx, table in enumerate(tables):
                if table and len(table) > 1:  # At least header + 1 row
                    result.append({
                        'index': idx,
                        'rows': len(table),
                        'cols': len(table[0]) if table else 0,
                        'data': table,
                    })
            return result
            
        except Exception as e:
            logger.warning(f"Table extraction failed: {e}")
            return []
    
    def extract_metadata(self, pdf_path: Path, pdf) -> Dict[str, Any]:
        """Extract PDF metadata."""
        metadata = pdf.metadata or {}
        
        return {
            'title': metadata.get('Title'),
            'author': metadata.get('Author'),
            'subject': metadata.get('Subject'),
            'creator': metadata.get('Creator'),
            'producer': metadata.get('Producer'),
            'creation_date': metadata.get('CreationDate'),
            'modification_date': metadata.get('ModDate'),
            'file_name': pdf_path.name,
            'file_size': pdf_path.stat().st_size,
            'file_sha256': sha256_file(pdf_path),
        }


class StructuralProcessor:
    """Main processor for structural extraction."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.stage_config = self.config_loader.get_stage_config('structural')
        
        # Components
        self.extractor = PDFExtractor(self.stage_config)
        self.path_manager = PathManager()
        self.normalizer = TextNormalizer()
        
        # Quality tracking (будет добавлено когда создадим quality_tracker)
        self.quality_tracker = None
    
    def process_pdf(self, pdf_path: Path, output_dir: Optional[Path] = None) -> Path:
        """
        Process PDF file to structural dataset.
        
        Args:
            pdf_path: path to PDF file
            output_dir: output directory (default: auto from PathManager)
            
        Returns:
            path to created dataset
        """
        logger.info(f"Processing: {pdf_path.name}")
        
        if output_dir is None:
            output_dir = self.path_manager.dataset_structural
        
        # Open PDF
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            logger.info(f"Total pages: {total_pages}")
            
            # Extract metadata
            pdf_metadata = self.extractor.extract_metadata(pdf_path, pdf)
            
            # Process pages
            cards = []
            tables_data = []
            ocr_used_count = 0
            ocr_confidences = []
            
            for page_num, page in enumerate(pdf.pages, start=1):
                # Extract text
                text, ocr_used, ocr_conf = self.extractor.extract_page(page)
                
                if ocr_used:
                    ocr_used_count += 1
                    if ocr_conf > 0:
                        ocr_confidences.append(ocr_conf)
                
                # Extract tables
                tables = self.extractor.extract_tables(page)
                
                # Build card
                card = self._build_card(
                    page_num=page_num,
                    text=text,
                    ocr_used=ocr_used,
                    ocr_confidence=ocr_conf if ocr_used else None,
                    tables=tables,
                    source_file=pdf_path.name,
                )
                cards.append(card)
                
                # Collect tables for saving
                if tables:
                    for table in tables:
                        tables_data.append({
                            'page_num': page_num,
                            'table_index': table['index'],
                            'table': table,
                        })
            
            # Build header
            header = self._build_header(
                pdf_path=pdf_path,
                pdf_metadata=pdf_metadata,
                total_pages=total_pages,
                cards=cards,
            )
            
            # Build audit
            audit = self._build_audit(
                total_pages=total_pages,
                ocr_used_count=ocr_used_count,
                ocr_confidences=ocr_confidences,
                tables_count=len(tables_data),
            )
            
            # Save dataset
            output_path = output_dir / f"{pdf_path.stem}.dataset.jsonl"
            DatasetIO.save(output_path, header, cards, audit)
            
            # Save tables
            if tables_data:
                self._save_tables(pdf_path.stem, tables_data)
            
            # Quality tracking
            if self.quality_tracker:
                metrics = self._calculate_metrics(cards, ocr_used_count, ocr_confidences, tables_data)
                self.quality_tracker.track('structural', pdf_path.name, metrics)
            
            logger.info(f"Saved: {output_path.name}")
            return output_path
    
    def _build_card(self, page_num: int, text: str, ocr_used: bool,
                    ocr_confidence: Optional[float], tables: List[Dict],
                    source_file: str) -> Dict[str, Any]:
        """Build card for one page."""
        card = {
            'segment_id': f"{page_num:05d}",
            'segment': text,
            'page_num': page_num,
            'source_file': source_file,
            'ocr_used': ocr_used,
        }
        
        if ocr_used and ocr_confidence is not None:
            card['ocr_confidence'] = round(ocr_confidence, 3)
        
        if tables:
            card['has_table'] = True
            card['table_count'] = len(tables)
            card['table_refs'] = [f"page_{page_num}_table_{t['index']}" for t in tables]
        
        return card
    
    def _build_header(self, pdf_path: Path, pdf_metadata: Dict,
                     total_pages: int, cards: List[Dict]) -> Dict[str, Any]:
        """Build dataset header."""
        return {
            'book': pdf_path.stem,
            'title': pdf_metadata.get('title') or pdf_path.stem,
            'author': pdf_metadata.get('author'),
            'source_file': pdf_path.name,
            'source_path': str(pdf_path.absolute()),
            'total_pages': total_pages,
            'total_cards': len(cards),
            'pdf_metadata': pdf_metadata,
            'stage': 'structural',
            'version': VERSION,
            'product': PRODUCT_NAME,
            'created_at': utc_now_iso(),
        }
    
    def _build_audit(self, total_pages: int, ocr_used_count: int,
                    ocr_confidences: List[float], tables_count: int) -> Dict[str, Any]:
        """Build audit section."""
        audit = {
            'total_pages': total_pages,
            'ocr_used_pages': ocr_used_count,
            'ocr_avg_confidence': round(sum(ocr_confidences) / len(ocr_confidences), 3) if ocr_confidences else 0.0,
            'tables_detected': tables_count,
            'stage': 'structural',
            'version': VERSION,
        }
        return audit
    
    def _save_tables(self, book_name: str, tables_data: List[Dict]) -> None:
        """Save extracted tables to separate files."""
        tables_dir = self.path_manager.tables / book_name
        tables_dir.mkdir(parents=True, exist_ok=True)
        
        for item in tables_data:
            page_num = item['page_num']
            table_idx = item['table_index']
            table = item['table']
            
            table_path = tables_dir / f"page_{page_num:05d}_table_{table_idx}.json"
            
            with open(table_path, 'w', encoding='utf-8') as f:
                import json
                json.dump(table, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(tables_data)} tables to {tables_dir}")
    
    def _calculate_metrics(self, cards: List[Dict], ocr_used_count: int,
                          ocr_confidences: List[float], tables_data: List) -> Dict[str, Any]:
        """Calculate quality metrics."""
        total = len(cards)
        empty_count = sum(1 for c in cards if len(c.get('segment', '').strip()) < 50)
        
        return {
            'total_pages': total,
            'empty_pages': empty_count,
            'empty_pages_ratio': empty_count / total if total > 0 else 0,
            'avg_chars_per_page': sum(len(c.get('segment', '')) for c in cards) / total if total > 0 else 0,
            'ocr_used_pages': ocr_used_count,
            'ocr_avg_confidence': sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0,
            'tables_detected': len(tables_data),
        }


def main():
    """CLI interface."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Structural extraction (MVP v2.0)')
    parser.add_argument('-i', '--input', required=True, help='Input PDF or directory')
    parser.add_argument('-o', '--output', help='Output directory')
    parser.add_argument('-c', '--config', help='Config file path')
    parser.add_argument('--pattern', default='*.pdf', help='File pattern for directory input')
    
    args = parser.parse_args()
    
    # Initialize processor
    config_path = Path(args.config) if args.config else None
    processor = StructuralProcessor(config_path)
    
    # Process
    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else None
    
    if input_path.is_file():
        # Single file
        processor.process_pdf(input_path, output_dir)
    elif input_path.is_dir():
        # Directory
        pdf_files = sorted(input_path.glob(args.pattern))
        logger.info(f"Found {len(pdf_files)} PDF files")
        
        for pdf_path in pdf_files:
            try:
                processor.process_pdf(pdf_path, output_dir)
            except Exception as e:
                logger.error(f"Failed to process {pdf_path.name}: {e}")
    else:
        logger.error(f"Invalid input path: {input_path}")
        sys.exit(1)
    
    logger.info("Done!")


if __name__ == '__main__':
    main()