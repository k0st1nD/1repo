#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_structural_robust.py - Robust Structural PDF Processing (MVP v2.0)
=====================================================================
Stage 1: Extract text, tables, images from PDF with multiple fallbacks

Features:
- Multi-extractor chain with fallback (pdfminer → pdfplumber → PyPDF2 → OCR)
- Retry logic with exponential backoff
- Smart blank page detection
- Graceful degradation (partial results on failure)
- Comprehensive error tracking
- Quality metrics tracking

Version: 2.0.0
Dependencies: pdfminer.six, pdfplumber, PyPDF2, pytesseract, Pillow, pdf2image
"""

import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
from enum import Enum

# PDF processing
try:
    from pdfminer.high_level import extract_text_to_fp
    from pdfminer.layout import LAParams
    PDFMINER_AVAILABLE = True
except ImportError:
    PDFMINER_AVAILABLE = False
    print("[WARN] pdfminer.six not available")

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("[WARN] pdfplumber not available")

try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False
    print("[WARN] PyPDF2 not available")

# OCR
try:
    import pytesseract
    from PIL import Image
    from pdf2image import convert_from_path
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("[WARN] OCR not available")

from am_common import (
    ConfigLoader, PathManager, DatasetIO, TextNormalizer, sha256_file,
    utc_now_iso, format_size
)

logger = logging.getLogger('am_structural_robust')

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"


class ExtractionMethod(Enum):
    """Extraction method used."""
    PDFMINER = "pdfminer"
    PDFPLUMBER = "pdfplumber"
    PYPDF2 = "pypdf2"
    OCR = "ocr"
    NONE = "none"


class RetryConfig:
    """Retry configuration."""
    MAX_RETRIES = 3
    INITIAL_DELAY = 1.0
    BACKOFF_FACTOR = 2.0
    MAX_DELAY = 10.0
    
    @staticmethod
    def get_delay(attempt: int) -> float:
        """Calculate delay for retry attempt."""
        delay = RetryConfig.INITIAL_DELAY * (RetryConfig.BACKOFF_FACTOR ** attempt)
        return min(delay, RetryConfig.MAX_DELAY)


class BlankPageDetector:
    """Detect truly blank pages vs. pages needing OCR."""
    
    def __init__(self, config: Dict[str, Any]):
        self.min_chars_ocr = config.get('min_chars_ocr', 50)
        self.min_chars_valid = config.get('min_chars_valid', 10)
        self.skip_front_matter = config.get('skip_front_matter', True)
    
    def is_truly_blank(self, text: str, page_num: int) -> bool:
        """Check if page is truly blank (no OCR needed)."""
        text_len = len(text.strip())
        
        # Completely empty
        if text_len == 0:
            return True
        
        # Skip front matter (covers, copyright, etc.)
        if self.skip_front_matter and page_num <= 5 and text_len < 20:
            return True
        
        # Has minimal text but not worth OCR
        if text_len < self.min_chars_valid:
            return True
        
        return False
    
    def needs_ocr(self, text: str, page_num: int) -> bool:
        """Check if page needs OCR."""
        if self.is_truly_blank(text, page_num):
            return False
        
        return len(text.strip()) < self.min_chars_ocr


class TextExtractorChain:
    """Chain of text extractors with fallback."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.ocr_config = config.get('ocr', {})
        self.blank_detector = BlankPageDetector(config.get('blank_detection', {}))
        self.text_normalizer = TextNormalizer()

        # Build extractor chain based on availability
        self.extractors = []
        
        if PDFMINER_AVAILABLE:
            self.extractors.append(('pdfminer', self._extract_pdfminer))
        
        if PDFPLUMBER_AVAILABLE:
            self.extractors.append(('pdfplumber', self._extract_pdfplumber))
        
        if PYPDF2_AVAILABLE:
            self.extractors.append(('pypdf2', self._extract_pypdf2))
        
        if OCR_AVAILABLE and self.ocr_config.get('enabled', True):
            self.extractors.append(('ocr', self._extract_ocr))
        
        if not self.extractors:
            raise RuntimeError("No text extractors available!")
        
        logger.info(f"Text extractor chain: {[name for name, _ in self.extractors]}")
    
    def extract(self, pdf_path: Path, page_num: int) -> Tuple[str, ExtractionMethod, Optional[float]]:
        """
        Extract text from page with fallback chain.
        
        Returns:
            (text, method_used, ocr_confidence)
        """
        # Try each extractor in chain
        for extractor_name, extractor_func in self.extractors:
            # Skip OCR if not needed (use blank detector)
            if extractor_name == 'ocr':
                # First, try non-OCR methods
                text_preview = self._try_non_ocr_preview(pdf_path, page_num)
                if not self.blank_detector.needs_ocr(text_preview, page_num):
                    # Don't waste time on OCR
                    if text_preview:
                        return text_preview, ExtractionMethod.PDFPLUMBER, None
                    else:
                        return "", ExtractionMethod.NONE, None
            
            # Try extraction with retry
            for attempt in range(RetryConfig.MAX_RETRIES):
                try:
                    result = extractor_func(pdf_path, page_num)
                    
                    if result:
                        text, confidence = result

                        # Normalize text
                        if text:
                            text = self.text_normalizer.normalize(text)
                            text = self.text_normalizer.remove_common_watermarks(text)

                        # Validate result
                        if text and len(text.strip()) >= 10:
                            method = ExtractionMethod[extractor_name.upper()]
                            logger.debug(f"[OK] Page {page_num}: {extractor_name} succeeded ({len(text)} chars)")
                            return text, method, confidence
                    
                    # Empty result, don't retry this method
                    break
                    
                except Exception as e:
                    if attempt < RetryConfig.MAX_RETRIES - 1:
                        delay = RetryConfig.get_delay(attempt)
                        logger.warning(f"[!] Page {page_num}: {extractor_name} failed (attempt {attempt+1}), retrying in {delay:.1f}s")
                        time.sleep(delay)
                    else:
                        logger.error(f"[X] Page {page_num}: {extractor_name} failed after {RetryConfig.MAX_RETRIES} attempts: {e}")

        # All extractors failed
        logger.error(f"[X] Page {page_num}: All extractors failed")
        return "", ExtractionMethod.NONE, None
    
    def _try_non_ocr_preview(self, pdf_path: Path, page_num: int) -> str:
        """Quick non-OCR preview for blank detection."""
        for name, func in self.extractors:
            if name == 'ocr':
                continue
            try:
                result = func(pdf_path, page_num)
                if result:
                    text, _ = result
                    return text
            except:
                continue
        return ""
    
    def _extract_pdfminer(self, pdf_path: Path, page_num: int) -> Tuple[str, None]:
        """Extract text using pdfminer.six."""
        from io import BytesIO
        
        output = BytesIO()
        
        with open(pdf_path, 'rb') as fp:
            extract_text_to_fp(
                fp,
                output,
                page_numbers=[page_num],
                laparams=LAParams(),
                output_type='text',
            )
        
        text = output.getvalue().decode('utf-8', errors='ignore')
        return text.strip(), None
    
    def _extract_pdfplumber(self, pdf_path: Path, page_num: int) -> Tuple[str, None]:
        """Extract text using pdfplumber."""
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return "", None
            
            page = pdf.pages[page_num]
            text = page.extract_text() or ""
            return text.strip(), None
    
    def _extract_pypdf2(self, pdf_path: Path, page_num: int) -> Tuple[str, None]:
        """Extract text using PyPDF2."""
        with open(pdf_path, 'rb') as f:
            reader = PyPDF2.PdfReader(f)
            
            if page_num >= len(reader.pages):
                return "", None
            
            page = reader.pages[page_num]
            text = page.extract_text() or ""
            return text.strip(), None
    
    def _extract_ocr(self, pdf_path: Path, page_num: int) -> Tuple[str, float]:
        """Extract text using OCR."""
        # Convert to image
        images = convert_from_path(
            pdf_path,
            dpi=300,
            first_page=page_num + 1,
            last_page=page_num + 1
        )
        
        if not images:
            return "", 0.0
        
        image = images[0]
        
        # Preprocess
        image = image.convert('L')  # Grayscale
        
        # Run OCR
        lang = self.ocr_config.get('language', 'eng')
        ocr_data = pytesseract.image_to_data(
            image,
            lang=lang,
            output_type=pytesseract.Output.DICT
        )
        
        # Extract text and confidence
        text_parts = []
        confidences = []
        
        for i, conf in enumerate(ocr_data['conf']):
            if conf > 0:
                text = ocr_data['text'][i]
                if text.strip():
                    text_parts.append(text)
                    confidences.append(conf)
        
        text = ' '.join(text_parts)
        avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        return text, avg_confidence / 100.0


class TableExtractorChain:
    """Chain of table extractors with fallback."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('enabled', True)
        self.min_rows = config.get('min_rows', 2)
        self.min_cols = config.get('min_cols', 2)
        
        # Build extractor chain
        self.extractors = []
        
        if PDFPLUMBER_AVAILABLE:
            self.extractors.append(('pdfplumber', self._extract_pdfplumber))
        
        # Future: camelot, tabula
        
        if not self.extractors:
            logger.warning("No table extractors available")
        else:
            logger.info(f"Table extractor chain: {[name for name, _ in self.extractors]}")
    
    def extract(self, pdf_path: Path, page_num: int) -> List[Dict[str, Any]]:
        """Extract tables from page with fallback."""
        if not self.enabled or not self.extractors:
            return []
        
        for extractor_name, extractor_func in self.extractors:
            for attempt in range(RetryConfig.MAX_RETRIES):
                try:
                    tables = extractor_func(pdf_path, page_num)
                    
                    if tables:
                        logger.debug(f"[OK] Page {page_num}: {extractor_name} found {len(tables)} tables")
                        return tables
                    
                    # No tables found, don't retry
                    break
                    
                except Exception as e:
                    if attempt < RetryConfig.MAX_RETRIES - 1:
                        delay = RetryConfig.get_delay(attempt)
                        logger.warning(f"[!] Page {page_num}: table extraction failed (attempt {attempt+1}), retrying in {delay:.1f}s")
                        time.sleep(delay)
                    else:
                        logger.error(f"[X] Page {page_num}: table extraction failed: {e}")
        
        return []
    
    def _extract_pdfplumber(self, pdf_path: Path, page_num: int) -> List[Dict[str, Any]]:
        """Extract tables using pdfplumber."""
        with pdfplumber.open(pdf_path) as pdf:
            if page_num >= len(pdf.pages):
                return []
            
            page = pdf.pages[page_num]
            tables = page.extract_tables()
            
            if not tables:
                return []
            
            result = []
            for idx, table in enumerate(tables):
                if not table or len(table) < self.min_rows:
                    continue
                
                if not table[0] or len(table[0]) < self.min_cols:
                    continue
                
                # Format table
                formatted = self._format_table(table, idx)
                if formatted:
                    result.append(formatted)
            
            return result
    
    def _format_table(self, table: List[List[str]], table_idx: int) -> Dict[str, Any]:
        """Format table to structured data."""
        # Clean cells
        cleaned = []
        for row in table:
            cleaned_row = [str(cell).strip() if cell else '' for cell in row]
            cleaned.append(cleaned_row)
        
        # Generate markdown
        markdown = self._to_markdown(cleaned)
        
        return {
            'table_id': f"table_{table_idx + 1}",
            'rows': len(cleaned),
            'cols': len(cleaned[0]) if cleaned else 0,
            'data': cleaned,
            'markdown': markdown,
        }
    
    def _to_markdown(self, table: List[List[str]]) -> str:
        """Convert table to markdown."""
        if not table:
            return ""
        
        lines = []
        header = table[0]
        lines.append('| ' + ' | '.join(header) + ' |')
        lines.append('|' + '|'.join(['---'] * len(header)) + '|')
        
        for row in table[1:]:
            padded_row = row + [''] * (len(header) - len(row))
            lines.append('| ' + ' | '.join(padded_row[:len(header)]) + ' |')
        
        return '\n'.join(lines)


class PDFMetadataExtractor:
    """Extract PDF metadata with fallback."""
    
    @staticmethod
    def extract(pdf_path: Path) -> Dict[str, Any]:
        """Extract PDF metadata."""
        metadata = {
            'title': None,
            'author': None,
            'subject': None,
            'creator': None,
            'producer': None,
            'creation_date': None,
        }
        
        # Try pdfplumber
        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    info = pdf.metadata
                    if info:
                        metadata.update({
                            'title': info.get('Title'),
                            'author': info.get('Author'),
                            'subject': info.get('Subject'),
                            'creator': info.get('Creator'),
                            'producer': info.get('Producer'),
                            'creation_date': str(info.get('CreationDate', '')),
                        })
            except Exception as e:
                logger.warning(f"pdfplumber metadata extraction failed: {e}")
        
        # Try PyPDF2 as fallback
        if not metadata['title'] and PYPDF2_AVAILABLE:
            try:
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    info = reader.metadata
                    if info:
                        metadata.update({
                            'title': info.get('/Title'),
                            'author': info.get('/Author'),
                            'subject': info.get('/Subject'),
                            'creator': info.get('/Creator'),
                            'producer': info.get('/Producer'),
                        })
            except Exception as e:
                logger.warning(f"PyPDF2 metadata extraction failed: {e}")
        
        # Fallback: use filename as title
        if not metadata['title']:
            metadata['title'] = pdf_path.stem
        
        return metadata


class RobustStructuralProcessor:
    """Main processor with robust error handling."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.stage_config = self.config_loader.get_stage_config('structural')
        
        # Components
        self.path_manager = PathManager()
        self.text_chain = TextExtractorChain(self.stage_config.get('text_extraction', {}))
        self.table_chain = TableExtractorChain(self.stage_config.get('table_extraction', {}))
        
        # Quality tracking
        self.quality_tracker = None
    
    def process_pdf(self, pdf_path: Path, 
                   output_dir: Optional[Path] = None) -> Optional[Path]:
        """
        Process PDF with robust error handling.
        
        Returns:
            path to output dataset, or None if completely failed
        """
        logger.info(f"Processing: {pdf_path.name}")
        
        if output_dir is None:
            output_dir = self.path_manager.dataset_structural
        
        try:
            # Extract metadata
            pdf_metadata = PDFMetadataExtractor.extract(pdf_path)
            logger.info(f"PDF: {pdf_metadata.get('title', 'N/A')}")
            
            # Get page count (with fallback)
            total_pages = self._get_page_count(pdf_path)
            if total_pages == 0:
                logger.error("Failed to determine page count")
                return self._create_error_dataset(pdf_path, "Cannot determine page count", output_dir)
            
            logger.info(f"Total pages: {total_pages}")
            
            # Process pages
            cards = []
            extraction_stats = {
                'success': 0,
                'failed': 0,
                'ocr_used': 0,
                'tables_found': 0,
                'methods': {},
            }
            
            for page_num in range(total_pages):
                try:
                    card, stats = self._process_page(pdf_path, page_num, pdf_metadata)
                    cards.append(card)
                    
                    # Update stats
                    extraction_stats['success'] += 1
                    if stats['method'] != ExtractionMethod.NONE:
                        extraction_stats['methods'][stats['method'].value] = \
                            extraction_stats['methods'].get(stats['method'].value, 0) + 1
                    if stats['ocr_used']:
                        extraction_stats['ocr_used'] += 1
                    extraction_stats['tables_found'] += stats['table_count']
                    
                    if (page_num + 1) % 50 == 0:
                        logger.info(f"  Processed {page_num + 1}/{total_pages} pages")
                    
                except Exception as e:
                    logger.error(f"Failed to process page {page_num}: {e}")
                    cards.append(self._create_error_card(page_num, pdf_path))
                    extraction_stats['failed'] += 1
            
            logger.info(f"Extraction complete: {extraction_stats['success']} success, {extraction_stats['failed']} failed")
            logger.info(f"  Methods used: {extraction_stats['methods']}")
            logger.info(f"  OCR used: {extraction_stats['ocr_used']} pages")
            logger.info(f"  Tables found: {extraction_stats['tables_found']}")
            
            # Build dataset
            header = self._build_header(pdf_path, pdf_metadata, cards)
            audit = self._build_audit(cards, extraction_stats)
            footer = self._build_footer()
            
            # Save
            book_name = pdf_path.stem.lower().replace(' ', '_')
            output_path = output_dir / f"{book_name}.dataset.jsonl"
            self._save_dataset(output_path, header, cards, audit, footer)
            
            # Quality tracking
            if self.quality_tracker:
                metrics = self._calculate_metrics(cards, extraction_stats)
                self.quality_tracker.track('structural', pdf_path.name, metrics)
            
            logger.info(f"[OK] Saved: {output_path.name}")
            return output_path
            
        except Exception as e:
            logger.error(f"[X] Fatal error processing {pdf_path.name}: {e}")
            return self._create_error_dataset(pdf_path, str(e), output_dir)
    
    def _get_page_count(self, pdf_path: Path) -> int:
        """Get page count with fallback."""
        # Try pdfplumber
        if PDFPLUMBER_AVAILABLE:
            try:
                with pdfplumber.open(pdf_path) as pdf:
                    return len(pdf.pages)
            except:
                pass
        
        # Try PyPDF2
        if PYPDF2_AVAILABLE:
            try:
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    return len(reader.pages)
            except:
                pass
        
        return 0
    
    def _process_page(self, pdf_path: Path, page_num: int, 
                     pdf_metadata: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """Process single page."""
        # Extract text
        text, method, ocr_confidence = self.text_chain.extract(pdf_path, page_num)
        
        # Extract tables
        tables = self.table_chain.extract(pdf_path, page_num)
        
        # Build card
        card = {
            'segment_id': f"{page_num + 1:05d}",
            'page_num': page_num + 1,
            'segment': text,
            'source_file': pdf_path.name,
            'extraction_method': method.value,
            'ocr_used': method == ExtractionMethod.OCR,
            'has_table': len(tables) > 0,
        }
        
        if method == ExtractionMethod.OCR and ocr_confidence is not None:
            card['ocr_confidence'] = round(ocr_confidence, 3)
        
        if tables:
            card['tables'] = tables
            card['table_count'] = len(tables)
        
        # Stats for tracking
        stats = {
            'method': method,
            'ocr_used': method == ExtractionMethod.OCR,
            'table_count': len(tables),
        }
        
        return card, stats
    
    def _create_error_card(self, page_num: int, pdf_path: Path) -> Dict[str, Any]:
        """Create error card for failed page."""
        return {
            'segment_id': f"{page_num + 1:05d}",
            'page_num': page_num + 1,
            'segment': "",
            'source_file': pdf_path.name,
            'extraction_method': 'none',
            'ocr_used': False,
            'has_table': False,
            'error': True,
        }
    
    def _create_error_dataset(self, pdf_path: Path, error_msg: str,
                             output_dir: Path) -> Optional[Path]:
        """Create minimal error dataset."""
        logger.error(f"Creating error dataset for {pdf_path.name}")
        
        header = {
            'segment_id': '__header__',
            'book': pdf_path.stem,
            'title': pdf_path.stem,
            'source_file': pdf_path.name,
            'total_cards': 0,
            'error': error_msg,
            'stage': 'structural',
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
        
        audit = {
            'segment_id': '__audit__',
            'error': error_msg,
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
        
        footer = self._build_footer()
        
        book_name = pdf_path.stem.lower().replace(' ', '_')
        output_path = output_dir / f"{book_name}.error.dataset.jsonl"
        
        self._save_dataset(output_path, header, [], audit, footer)
        
        return output_path
    
    def _build_header(self, pdf_path: Path, pdf_metadata: Dict[str, Any],
                     cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build header."""
        return {
            'segment_id': '__header__',
            'source': {
                'title': pdf_metadata.get('title'),
                'author': pdf_metadata.get('author'),
                'file_name': pdf_path.name,
                'file_size': pdf_path.stat().st_size,
                'pages': len(cards),
            },
            'book': pdf_path.stem.lower().replace(' ', '_'),
            'total_cards': len(cards),
            'segment_ids': [c['segment_id'] for c in cards],
            'dataset_created_at': utc_now_iso(),
            'pdf_sha256': sha256_file(pdf_path),
            'version': VERSION,
            'product': f"{PRODUCT_NAME} {VERSION}",
        }
    
    def _build_audit(self, cards: List[Dict[str, Any]], 
                    extraction_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Build audit."""
        empty_pages = sum(1 for c in cards if len(c.get('segment', '').strip()) < 50)
        error_pages = sum(1 for c in cards if c.get('error', False))
        
        ocr_confidences = [
            c.get('ocr_confidence', 0) 
            for c in cards 
            if c.get('ocr_used', False)
        ]
        avg_ocr = sum(ocr_confidences) / len(ocr_confidences) if ocr_confidences else 0
        
        return {
            'segment_id': '__audit__',
            'total_cards': len(cards),
            'success_pages': extraction_stats['success'],
            'failed_pages': extraction_stats['failed'],
            'empty_pages': empty_pages,
            'error_pages': error_pages,
            'extraction_methods': extraction_stats['methods'],
            'ocr_used_count': extraction_stats['ocr_used'],
            'ocr_avg_confidence': round(avg_ocr, 3),
            'tables_extracted': extraction_stats['tables_found'],
            'stage': 'structural',
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
    
    def _build_footer(self) -> Dict[str, Any]:
        """Build footer."""
        return {
            'segment_id': '__footer__',
            'created_at': utc_now_iso(),
            'version': VERSION,
            'product': f"{PRODUCT_NAME} {VERSION}",
        }
    
    def _save_dataset(self, path: Path, header: Dict[str, Any],
                     cards: List[Dict[str, Any]], audit: Dict[str, Any],
                     footer: Dict[str, Any]) -> None:
        """Save dataset."""
        DatasetIO.save(path, header, cards, audit, footer, validate=False)
        
        file_size = path.stat().st_size
        logger.info(f"Dataset saved: {format_size(file_size)}")
    
    def _calculate_metrics(self, cards: List[Dict[str, Any]],
                          extraction_stats: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate metrics."""
        total = len(cards)
        text_lengths = [len(c.get('segment', '')) for c in cards]
        
        return {
            'total_pages': total,
            'success_pages': extraction_stats['success'],
            'failed_pages': extraction_stats['failed'],
            'success_ratio': extraction_stats['success'] / total if total > 0 else 0,
            'empty_pages': sum(1 for l in text_lengths if l < 50),
            'avg_page_length': sum(text_lengths) / total if total > 0 else 0,
            'extraction_methods': extraction_stats['methods'],
            'ocr_used': extraction_stats['ocr_used'],
            'tables_found': extraction_stats['tables_found'],
        }


def main():
    """CLI interface."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Robust structural extraction (MVP v2.0)')
    parser.add_argument('-i', '--input', required=True,
                       help='Input PDF file or directory')
    parser.add_argument('-o', '--output',
                       help='Output directory')
    parser.add_argument('-c', '--config',
                       help='Config file path')
    parser.add_argument('--pattern', default='*.pdf',
                       help='File pattern for directory input')
    parser.add_argument('--no-ocr', action='store_true',
                       help='Disable OCR')
    
    args = parser.parse_args()
    
    # Initialize processor
    config_path = Path(args.config) if args.config else None
    processor = RobustStructuralProcessor(config_path)
    
    # Process
    input_path = Path(args.input)
    output_dir = Path(args.output) if args.output else None
    
    if input_path.is_file():
        if not input_path.suffix.lower() == '.pdf':
            logger.error("Input must be a PDF file")
            sys.exit(1)
        
        result = processor.process_pdf(input_path, output_dir)
        if not result:
            sys.exit(1)
    
    elif input_path.is_dir():
        pdf_files = sorted(input_path.glob(args.pattern))
        logger.info(f"Found {len(pdf_files)} PDF files")
        
        success_count = 0
        for pdf_path in pdf_files:
            try:
                result = processor.process_pdf(pdf_path, output_dir)
                if result:
                    success_count += 1
            except Exception as e:
                logger.error(f"Fatal error processing {pdf_path.name}: {e}")
        
        logger.info(f"Processed {success_count}/{len(pdf_files)} PDFs successfully")
    
    else:
        logger.error(f"Invalid input path: {input_path}")
        sys.exit(1)
    
    logger.info("Done!")


if __name__ == '__main__':
    main()