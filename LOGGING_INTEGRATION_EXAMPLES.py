#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LOGGING_INTEGRATION_EXAMPLES.md - How to use am_logging v2.0 in pipeline
=========================================================================

Examples of integrating enhanced logging into pipeline modules.
"""

# ============================================
# EXAMPLE 1: Basic Module Setup
# ============================================

"""
In any pipeline module (e.g., am_structural.py):
"""

from am_logging import (
    get_logger,
    log_stage,
    log_operation,
    log_performance,
    create_progress_bar,
    get_error_aggregator
)

# Get logger for this module
logger = get_logger(__name__)

class StructuralProcessor:
    def __init__(self, config_path=None):
        # ... config loading ...
        logger.info("StructuralProcessor initialized")
    
    def process_dataset(self, input_path, output_dir=None):
        # Log stage start
        log_stage(logger, "structural", "Starting")
        
        # Use context manager for the entire operation
        with log_operation(logger, "process_dataset", 
                          input=str(input_path),
                          output=str(output_dir)):
            
            # Load PDF
            cards = self._extract_pages(input_path)
            
            # Save dataset
            self._save_dataset(output_path, cards)
        
        # Log stage completion
        log_stage(logger, "structural", "Completed")


# ============================================
# EXAMPLE 2: Performance Tracking with Decorator
# ============================================

"""
Track performance of specific functions:
"""

from am_logging import log_performance

class StructuralProcessor:
    
    @log_performance('extract_single_page')
    def _extract_page(self, page_num, page_obj):
        """Extract text from a single page."""
        # This function's execution time will be tracked automatically
        text = self._run_extractors(page_obj)
        return text
    
    def _extract_pages(self, pdf_path):
        logger.info(f"Extracting pages from {pdf_path.name}")
        
        cards = []
        # Use progress bar for visual feedback
        for page_num in create_progress_bar(range(1, total_pages + 1), 
                                           desc="Extracting pages"):
            card = self._extract_page(page_num, page_obj)
            cards.append(card)
        
        return cards


# ============================================
# EXAMPLE 3: Error Aggregation
# ============================================

"""
Collect errors and warnings for later reporting:
"""

from am_logging import get_error_aggregator

class StructuralProcessor:
    
    def _extract_page(self, page_num, page_obj):
        aggregator = get_error_aggregator()
        
        try:
            # Try primary extractor
            text = self._pdfminer_extract(page_obj)
            
        except Exception as e:
            # Log error but continue
            logger.warning(f"PDFMiner failed for page {page_num}: {e}")
            aggregator.add_warning("structural", 
                                 f"PDFMiner failed on page {page_num}",
                                 page=page_num,
                                 error=str(e))
            
            # Try fallback
            try:
                text = self._ocr_extract(page_obj)
                aggregator.add_warning("structural",
                                     f"Used OCR fallback for page {page_num}",
                                     page=page_num)
            except Exception as e2:
                # Critical error
                aggregator.add_error("structural",
                                   f"All extraction methods failed for page {page_num}",
                                   page=page_num,
                                   error=str(e2))
                raise
        
        return text


# ============================================
# EXAMPLE 4: Structured Logging
# ============================================

"""
Use structured logging for machine-readable logs:
"""

from am_logging import get_logger

# Get structured logger
logger = get_logger(__name__, structured=True)

class ExtendedProcessor:
    
    def _extract_extended_fields(self, card):
        page_num = card.get('page_num')
        
        # Log with metadata
        logger.info("Starting extended field extraction",
                   page=page_num,
                   has_table=card.get('has_table', False),
                   text_length=len(card.get('segment', '')))
        
        try:
            fields = self._lm_extraction(card['segment'])
            
            # Log success with metrics
            logger.info("Extended fields extracted",
                       page=page_num,
                       field_count=len(fields),
                       extraction_method='lm')
            
            return fields
            
        except Exception as e:
            # Log error with context
            logger.error("Extended field extraction failed",
                        page=page_num,
                        error=str(e),
                        fallback='heuristic')
            
            # Use fallback
            return self._heuristic_extraction(card['segment'])


# ============================================
# EXAMPLE 5: Complete Pipeline Integration
# ============================================

"""
Example of run_mvp.py with enhanced logging:
"""

import sys
from pathlib import Path
from am_logging import (
    setup_logging_from_config,
    get_logger,
    log_section,
    log_stage,
    log_performance_summary,
    log_error_summary,
    reset_tracking
)
from am_common import ConfigLoader

def main():
    # Load config
    config_loader = ConfigLoader()
    config = config_loader.load()
    
    # Setup logging from config
    setup_logging_from_config(config)
    logger = get_logger(__name__)
    
    # Reset tracking at start
    reset_tracking()
    
    # Log pipeline start
    log_section(logger, "🚀 Archivist Magika Pipeline v2.0", "INFO")
    
    try:
        # Stage 1: Structural
        log_stage(logger, "structural", "Starting")
        structural_processor = StructuralProcessor(config)
        structural_output = structural_processor.process_dataset(input_path)
        log_stage(logger, "structural", "Completed")
        
        # Stage 2: Structure Detection
        log_stage(logger, "structure_detect", "Starting")
        structure_processor = StructureDetector(config)
        structured_output = structure_processor.process_dataset(structural_output)
        log_stage(logger, "structure_detect", "Completed")
        
        # ... more stages ...
        
        # Stage 7: Embedding
        log_stage(logger, "embed", "Starting")
        embed_processor = EmbeddingProcessor(config)
        embed_output = embed_processor.process_dataset(chunks_output)
        log_stage(logger, "embed", "Completed")
        
        # Pipeline completed
        log_section(logger, "✅ Pipeline Completed Successfully", "INFO")
        
    except Exception as e:
        log_section(logger, f"❌ Pipeline Failed: {e}", "ERROR")
        logger.exception("Pipeline error details:")
        sys.exit(1)
    
    finally:
        # Always log summaries at the end
        log_performance_summary(logger)
        log_error_summary(logger)


# ============================================
# EXAMPLE 6: Config File (config/mvp.yaml)
# ============================================

"""
Example logging configuration in YAML:
"""

YAML_CONFIG = """
logging:
  level: INFO
  detailed: false  # Set to true for filename:lineno in logs
  
  console:
    enabled: true
    colored: true
  
  file:
    enabled: true
    path: logs/pipeline.log
    max_bytes: 10485760  # 10MB
    backup_count: 5
  
  structured:
    enabled: true  # Enable JSON logs for analysis
    path: logs/pipeline.json
  
  use_tqdm_handler: true  # Enable progress bar integration
"""


# ============================================
# EXAMPLE 7: Quality Tracker Integration
# ============================================

"""
Integrate logging with quality tracking:
"""

from am_logging import get_logger, log_metrics
from quality_tracker import QualityTracker

class StructuralProcessor:
    
    def __init__(self, config_path=None):
        self.logger = get_logger(__name__)
        self.quality_tracker = QualityTracker(config)
    
    def process_dataset(self, input_path, output_dir=None):
        with log_operation(self.logger, "structural_processing",
                          input=str(input_path)):
            
            # Process
            cards = self._extract_pages(input_path)
            
            # Calculate metrics
            metrics = {
                'total_pages': len(cards),
                'ocr_pages': sum(1 for c in cards if c.get('ocr_used')),
                'tables_extracted': sum(1 for c in cards if c.get('has_table')),
                'avg_text_length': sum(len(c.get('segment', '')) for c in cards) / len(cards)
            }
            
            # Log metrics
            log_metrics(self.logger, metrics, "Structural Metrics")
            
            # Track quality
            self.quality_tracker.track('structural', input_path.name, metrics)
            
            return output_path


# ============================================
# EXAMPLE 8: Testing with Logging
# ============================================

"""
Example test with logging:
"""

import unittest
from am_logging import setup_logging, get_logger

class TestStructuralProcessor(unittest.TestCase):
    
    @classmethod
    def setUpClass(cls):
        # Setup logging for tests
        setup_logging(
            level="DEBUG",
            log_file=Path("logs/test.log"),
            console=True,
            colored=True
        )
        cls.logger = get_logger(__name__)
    
    def test_extract_page(self):
        self.logger.info("Testing page extraction")
        
        processor = StructuralProcessor()
        result = processor._extract_page(1, mock_page)
        
        self.assertIsNotNone(result)
        self.logger.info(f"Page extraction test passed: {len(result['segment'])} chars")


# ============================================
# EXPECTED OUTPUT EXAMPLES
# ============================================

"""
Example console output with colors:

2025-01-28 14:30:00 - am_structural - INFO - ============================================================
2025-01-28 14:30:00 - am_structural - INFO -   📄 Starting: STRUCTURAL
2025-01-28 14:30:00 - am_structural - INFO - ============================================================
2025-01-28 14:30:00 - am_structural - INFO - Starting: process_dataset
Extracting pages: 100%|████████████████████| 257/257 [00:45<00:00,  5.71it/s]
2025-01-28 14:30:45 - am_structural - INFO - Completed: process_dataset (45.23s)
2025-01-28 14:30:45 - am_structural - INFO - ============================================================
2025-01-28 14:30:45 - am_structural - INFO -   📄 Completed: STRUCTURAL
2025-01-28 14:30:45 - am_structural - INFO - ============================================================

2025-01-28 14:30:45 - am_structural - INFO - ============================================================
2025-01-28 14:30:45 - am_structural - INFO -   Performance Summary
2025-01-28 14:30:45 - am_structural - INFO - ============================================================
2025-01-28 14:30:45 - am_structural - INFO - 
extract_single_page:
2025-01-28 14:30:45 - am_structural - INFO -   Count: 257
2025-01-28 14:30:45 - am_structural - INFO -   Total: 42.50s
2025-01-28 14:30:45 - am_structural - INFO -   Avg: 0.17s
2025-01-28 14:30:45 - am_structural - INFO -   Min: 0.05s
2025-01-28 14:30:45 - am_structural - INFO -   Max: 2.34s
"""

"""
Example structured JSON log line:

{"timestamp": "2025-01-28T14:30:00Z", "level": "INFO", "message": "Starting extended field extraction", "page": 42, "has_table": true, "text_length": 1523}
{"timestamp": "2025-01-28T14:30:01Z", "level": "INFO", "message": "Extended fields extracted", "page": 42, "field_count": 15, "extraction_method": "lm"}
"""


# ============================================
# MIGRATION GUIDE
# ============================================

"""
To migrate from old am_logging.py to v2.0:

1. Replace am_logging.py with new version
2. Update imports:
   
   OLD:
   from am_logging import setup_logging, get_logger
   
   NEW (same, but more features available):
   from am_logging import (
       setup_logging_from_config,
       get_logger,
       log_stage,
       log_operation,
       log_performance,
       create_progress_bar
   )

3. Add performance tracking to heavy functions:
   
   @log_performance('extract_page')
   def _extract_page(self, page_num, page_obj):
       ...

4. Use context managers for operations:
   
   with log_operation(logger, 'process_dataset', input=str(input_path)):
       # your code here
       pass

5. Add progress bars:
   
   for item in create_progress_bar(items, desc="Processing"):
       process(item)

6. Enable structured logging in config:
   
   logging:
     structured:
       enabled: true
       path: logs/pipeline.json

7. Add summaries at end of pipeline:
   
   from am_logging import log_performance_summary, log_error_summary
   
   log_performance_summary(logger)
   log_error_summary(logger)
"""


# ============================================
# BENEFITS OF v2.0
# ============================================

"""
✅ Performance Tracking
   - Automatic timing of functions
   - Statistics (avg, min, max)
   - Per-operation metrics

✅ Structured Logging
   - Machine-readable JSON logs
   - Easy to parse and analyze
   - Integration with log analysis tools

✅ Error Aggregation
   - Collect all errors/warnings
   - Summary by stage
   - Better debugging

✅ Progress Bars
   - Visual feedback
   - Compatible with logging
   - No console clutter

✅ Pipeline Integration
   - Stage tracking with emojis
   - Context managers
   - Automatic metrics logging

✅ Better Organization
   - Separate handlers for console/file/JSON
   - Rotating log files
   - Colored output for readability
"""

if __name__ == "__main__":
    print(__doc__)
