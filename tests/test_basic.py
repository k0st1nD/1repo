#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_basic.py - Comprehensive Tests for Archivist Magika MVP v2.0
=================================================================
Unit and integration tests for core functionality

Version: 2.0.0
Dependencies: unittest, am_common, am_logging, quality_tracker, validate
"""

import unittest
import tempfile
import shutil
from pathlib import Path
import json
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from am_common import (
    DatasetIO, TextNormalizer, ConfigLoader, PathManager,
    sha256_file, utc_now_iso
)
from am_logging import (
    setup_logging, get_logger, get_performance_tracker,
    get_error_aggregator, reset_tracking
)


# ============================================
# TEST: Core Utilities
# ============================================

class TestDatasetIO(unittest.TestCase):
    """Test DatasetIO functionality."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / 'test.dataset.jsonl'
    
    def tearDown(self):
        """Clean up test files."""
        shutil.rmtree(self.temp_dir)
    
    def test_save_and_load(self):
        """Test saving and loading dataset."""
        # Create test data
        header = {
            'segment_id': '__header__',
            'book': 'test_book',
            'title': 'Test Book',
            'total_cards': 2,
        }
        
        cards = [
            {'segment_id': '00001', 'segment': 'First segment', 'page_num': 1},
            {'segment_id': '00002', 'segment': 'Second segment', 'page_num': 2},
        ]
        
        audit = {
            'segment_id': '__audit__',
            'total_cards': 2,
            'stage': 'test',
        }
        
        # Save
        DatasetIO.save(self.test_file, header, cards, audit)
        
        # Check file exists
        self.assertTrue(self.test_file.exists())
        
        # Load
        header_loaded, cards_loaded, audit_loaded, footer = DatasetIO.load(
            self.test_file, validate=False
        )
        
        # Verify
        self.assertEqual(header_loaded['book'], 'test_book')
        self.assertEqual(len(cards_loaded), 2)
        self.assertEqual(cards_loaded[0]['segment_id'], '00001')
        self.assertEqual(audit_loaded['total_cards'], 2)
    
    def test_load_nonexistent_file(self):
        """Test loading non-existent file."""
        fake_file = Path(self.temp_dir) / 'nonexistent.jsonl'
        
        with self.assertRaises(FileNotFoundError):
            DatasetIO.load(fake_file, validate=False)
    
    def test_save_with_footer(self):
        """Test saving with footer."""
        header = {'segment_id': '__header__', 'book': 'test'}
        cards = [{'segment_id': '00001', 'segment': 'test'}]
        audit = {'segment_id': '__audit__'}
        footer = {'segment_id': '__footer__', 'version': '2.0.0'}
        
        DatasetIO.save(self.test_file, header, cards, audit, footer)
        
        _, _, _, footer_loaded = DatasetIO.load(self.test_file, validate=False)
        
        self.assertIsNotNone(footer_loaded)
        self.assertEqual(footer_loaded['version'], '2.0.0')


class TestTextNormalizer(unittest.TestCase):
    """Test TextNormalizer functionality."""
    
    def setUp(self):
        """Set up normalizer."""
        self.normalizer = TextNormalizer()
    
    def test_normalize_whitespace(self):
        """Test whitespace normalization."""
        text = "Multiple    spaces\n\n\nand\n\nlines"
        result = self.normalizer.normalize(text)
        
        self.assertNotIn('    ', result)  # No multiple spaces
        self.assertNotIn('\n\n\n', result)  # No triple newlines
    
    def test_normalize_unicode(self):
        """Test Unicode normalization."""
        text = "café résumé"
        result = self.normalizer.normalize(text)
        
        # Should be normalized
        self.assertIn('café', result)
        self.assertIsInstance(result, str)
    
    def test_remove_control_chars(self):
        """Test control character removal."""
        text = "Hello\x00World\x01Test"
        result = self.normalizer.normalize(text)
        
        self.assertNotIn('\x00', result)
        self.assertNotIn('\x01', result)
        self.assertIn('Hello', result)
        self.assertIn('World', result)
    
    def test_empty_string(self):
        """Test empty string handling."""
        result = self.normalizer.normalize("")
        self.assertEqual(result, "")
    
    def test_preserve_important_chars(self):
        """Test that important characters are preserved."""
        text = "Test: Hello, World! (123) [test]"
        result = self.normalizer.normalize(text)
        
        self.assertIn(':', result)
        self.assertIn(',', result)
        self.assertIn('!', result)
        self.assertIn('(', result)
        self.assertIn('[', result)


class TestConfigLoader(unittest.TestCase):
    """Test ConfigLoader functionality."""
    
    def setUp(self):
        """Set up test config."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / 'test_config.yaml'
        
        # Create test config
        config_content = """
version: "2.0"

pipeline:
  structural:
    ocr:
      enabled: true
      language: eng
  
  chunk:
    chunk_size: 512
    overlap: 128
"""
        
        with open(self.config_file, 'w') as f:
            f.write(config_content)
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_load_config(self):
        """Test loading config."""
        loader = ConfigLoader(self.config_file)
        config = loader.load()
        
        self.assertEqual(config['version'], '2.0')
        self.assertIn('pipeline', config)
    
    def test_get_stage_config(self):
        """Test getting stage config."""
        loader = ConfigLoader(self.config_file)
        loader.load()
        
        structural_config = loader.get_stage_config('structural')
        
        self.assertIn('ocr', structural_config)
        self.assertTrue(structural_config['ocr']['enabled'])
    
    def test_missing_config(self):
        """Test missing config file."""
        loader = ConfigLoader(Path('nonexistent.yaml'))
        
        # Should return default config
        config = loader.load()
        self.assertIsInstance(config, dict)


class TestPathManager(unittest.TestCase):
    """Test PathManager functionality."""
    
    def test_default_paths(self):
        """Test default path structure."""
        manager = PathManager()
        
        # Check key paths exist
        self.assertTrue(manager.base_dir.exists())
        self.assertTrue(manager.data_dir.exists())
        
    def test_path_properties(self):
        """Test path properties."""
        manager = PathManager()
        
        # Dataset paths
        self.assertEqual(manager.dataset_structural.name, 'structural')
        self.assertEqual(manager.dataset_chunks.name, 'chunks')
        
        # Index paths
        self.assertEqual(manager.index_faiss.name, 'faiss')
        self.assertEqual(manager.index_metadata.name, 'metadata')
    
    def test_path_creation(self):
        """Test that paths are created on access."""
        manager = PathManager()
        
        # Access paths (should create them)
        _ = manager.dataset_structural
        _ = manager.index_faiss
        
        # Verify they exist
        self.assertTrue(manager.dataset_structural.exists())
        self.assertTrue(manager.index_faiss.exists())


class TestHashFunction(unittest.TestCase):
    """Test hash functions."""
    
    def setUp(self):
        """Create test file."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / 'test.txt'
        
        with open(self.test_file, 'w') as f:
            f.write('Test content')
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_sha256_file(self):
        """Test SHA256 hashing."""
        hash1 = sha256_file(self.test_file)
        
        # Hash should be consistent
        hash2 = sha256_file(self.test_file)
        self.assertEqual(hash1, hash2)
        
        # Hash should be 64 chars (256 bits in hex)
        self.assertEqual(len(hash1), 64)
        
        # Modify file
        with open(self.test_file, 'a') as f:
            f.write(' modified')
        
        hash3 = sha256_file(self.test_file)
        self.assertNotEqual(hash1, hash3)


# ============================================
# TEST: Logging v2.0
# ============================================

class TestLoggingV2(unittest.TestCase):
    """Test am_logging v2.0 functionality."""
    
    @classmethod
    def setUpClass(cls):
        """Set up logging for tests."""
        setup_logging(
            level='DEBUG',
            console=False,  # Disable console for tests
            log_file=None
        )
    
    def setUp(self):
        """Reset tracking before each test."""
        reset_tracking()
    
    def test_performance_tracker(self):
        """Test performance tracking."""
        from am_logging import log_performance
        import time
        
        @log_performance('test_operation')
        def test_func():
            time.sleep(0.1)
            return 'done'
        
        # Run function
        result = test_func()
        self.assertEqual(result, 'done')
        
        # Check metrics
        tracker = get_performance_tracker()
        stats = tracker.get_stats('test_operation')
        
        self.assertGreater(stats['count'], 0)
        self.assertGreater(stats['avg'], 0.09)  # ~0.1s
    
    def test_error_aggregator(self):
        """Test error aggregation."""
        aggregator = get_error_aggregator()
        
        # Add errors
        aggregator.add_error('structural', 'Test error', page=42)
        aggregator.add_warning('extended', 'Test warning', page=15)
        
        # Check summary
        summary = aggregator.get_summary()
        
        self.assertEqual(summary['total_errors'], 1)
        self.assertEqual(summary['total_warnings'], 1)
        self.assertIn('structural', summary['errors_by_stage'])
        self.assertIn('extended', summary['warnings_by_stage'])
    
    def test_context_manager(self):
        """Test log_operation context manager."""
        from am_logging import log_operation
        import time
        
        logger = get_logger(__name__)
        
        with log_operation(logger, 'test_context', test_param='value'):
            time.sleep(0.05)
        
        # Check performance tracking
        tracker = get_performance_tracker()
        stats = tracker.get_stats('test_context')
        
        self.assertGreater(stats['count'], 0)


# ============================================
# TEST: Quality Tracker v2.0
# ============================================

class TestQualityTracker(unittest.TestCase):
    """Test quality_tracker.py v2.0."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        
        # Import here to avoid circular dependencies
        from quality_tracker import QualityTracker
        
        self.tracker = QualityTracker(output_dir=Path(self.temp_dir))
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_track_metrics(self):
        """Test tracking metrics."""
        metrics = {
            'total_pages': 100,
            'success_ratio': 0.98,
            'avg_page_length': 1500,
        }
        
        self.tracker.track('structural', 'test_book', metrics)
        
        # Check that record was stored
        self.assertIn('structural', self.tracker.metrics)
        self.assertEqual(len(self.tracker.metrics['structural']), 1)
    
    def test_threshold_checking(self):
        """Test threshold checking."""
        # Good metrics (should pass)
        good_metrics = {
            'min_success_ratio': 0.98,
            'max_empty_ratio': 0.05,
            'min_avg_page_length': 1000,
            'max_error_ratio': 0.02,
        }
        
        result = self.tracker.check_thresholds('structural', good_metrics)
        self.assertTrue(result['passed'])
        self.assertEqual(len(result['violations']), 0)
        
        # Bad metrics (should fail)
        bad_metrics = {
            'min_success_ratio': 0.80,  # Too low
            'max_empty_ratio': 0.20,    # Too high
        }
        
        result = self.tracker.check_thresholds('structural', bad_metrics)
        self.assertFalse(result['passed'])
        self.assertGreater(len(result['violations']), 0)
    
    def test_report_generation(self):
        """Test report generation."""
        # Track multiple runs
        for i in range(3):
            metrics = {
                'total_pages': 100 + i * 10,
                'success_ratio': 0.95 + i * 0.01,
            }
            self.tracker.track('structural', f'book_{i}', metrics)
        
        # Generate report
        report = self.tracker.generate_report('structural')
        
        self.assertIn('stages', report)
        self.assertIn('structural', report['stages'])
        
        stage_data = report['stages']['structural']
        self.assertEqual(stage_data['total_runs'], 3)
        self.assertIn('statistics', stage_data)


# ============================================
# TEST: Validation
# ============================================

class TestValidation(unittest.TestCase):
    """Test validate.py functionality."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_validate_dataset(self):
        """Test dataset validation."""
        from validate import DatasetValidator
        
        # Create valid dataset
        dataset_path = Path(self.temp_dir) / 'test.dataset.jsonl'
        
        header = {
            'segment_id': '__header__',
            'book': 'test',
            'title': 'Test',
            'total_cards': 1,
        }
        
        cards = [{
            'segment_id': '00001',
            'segment': 'Test content',
            'page_num': 1,
        }]
        
        audit = {
            'segment_id': '__audit__',
            'total_cards': 1,
        }
        
        DatasetIO.save(dataset_path, header, cards, audit)
        
        # Validate
        validator = DatasetValidator()
        result = validator.validate_dataset(dataset_path, stage='structural')
        
        self.assertIsInstance(result, dict)
        self.assertIn('valid', result)
        self.assertIn('error_count', result)


# ============================================
# TEST: Integration
# ============================================

class TestIntegration(unittest.TestCase):
    """Integration tests."""
    
    def setUp(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        reset_tracking()
    
    def tearDown(self):
        """Clean up."""
        shutil.rmtree(self.temp_dir)
    
    def test_full_dataset_workflow(self):
        """Test complete dataset workflow."""
        # Create dataset
        header = {
            'segment_id': '__header__',
            'book': 'integration_test',
            'title': 'Integration Test Book',
            'total_cards': 3,
            'created_at': utc_now_iso(),
        }
        
        cards = [
            {
                'segment_id': '00001',
                'segment': 'First page content',
                'page_num': 1,
            },
            {
                'segment_id': '00002',
                'segment': 'Second page content',
                'page_num': 2,
            },
            {
                'segment_id': '00003',
                'segment': 'Third page content',
                'page_num': 3,
            },
        ]
        
        audit = {
            'segment_id': '__audit__',
            'total_cards': 3,
            'stage': 'test',
        }
        
        # Save dataset
        dataset_path = Path(self.temp_dir) / 'test.dataset.jsonl'
        DatasetIO.save(dataset_path, header, cards, audit)
        
        # Verify file exists
        self.assertTrue(dataset_path.exists())
        
        # Load dataset
        header_loaded, cards_loaded, audit_loaded, _ = DatasetIO.load(
            dataset_path, validate=False
        )
        
        # Validate
        self.assertEqual(header_loaded['book'], 'integration_test')
        self.assertEqual(len(cards_loaded), 3)
        self.assertEqual(audit_loaded['total_cards'], 3)
    
    def test_pipeline_with_logging_and_quality(self):
        """Test pipeline integration with logging and quality tracking."""
        from am_logging import log_operation, get_logger
        from quality_tracker import QualityTracker
        
        logger = get_logger(__name__)
        tracker = QualityTracker(output_dir=Path(self.temp_dir))
        
        # Simulate pipeline stage
        with log_operation(logger, 'test_stage', book='test_book'):
            # Simulate processing
            import time
            time.sleep(0.05)
            
            # Track quality metrics
            metrics = {
                'total_items': 100,
                'success_rate': 0.95,
            }
            tracker.track('test_stage', 'test_book', metrics)
        
        # Check results
        performance = get_performance_tracker()
        stats = performance.get_stats('test_stage')
        
        self.assertGreater(stats['count'], 0)
        self.assertIn('test_stage', tracker.metrics)


class TestChunkGeneration(unittest.TestCase):
    """Test chunk generation logic."""
    
    def test_chunk_with_overlap(self):
        """Test chunking with overlap."""
        # Simulate chunking
        text = "This is a test sentence. " * 100  # ~2500 chars
        chunk_size = 500
        overlap = 50
        
        chunks = []
        start = 0
        
        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunk = text[start:end]
            chunks.append(chunk)
            
            if end >= len(text):
                break
            
            start = end - overlap
        
        # Should have multiple chunks
        self.assertGreater(len(chunks), 1)
        
        # Chunks should overlap
        if len(chunks) > 1:
            # Last chars of chunk 1 should be in chunk 2
            overlap_text = chunks[0][-overlap:]
            self.assertTrue(any(overlap_text[:20] in chunks[i] for i in range(1, len(chunks))))
    
    def test_chunk_metadata_preservation(self):
        """Test that metadata is preserved in chunks."""
        metadata = {
            'book': 'test_book',
            'chapter': 'Chapter 1',
            'page_num': 42,
        }
        
        # Simulate chunk creation
        chunk = {
            'chunk_id': 'test_chunk_001',
            'text': 'Test content',
            'metadata': metadata.copy(),
        }
        
        # Verify metadata
        self.assertEqual(chunk['metadata']['book'], 'test_book')
        self.assertEqual(chunk['metadata']['chapter'], 'Chapter 1')
        self.assertEqual(chunk['metadata']['page_num'], 42)


# ============================================
# TEST RUNNER
# ============================================

def run_tests(verbosity=2):
    """Run all tests."""
    # Create test suite
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add all test classes
    test_classes = [
        TestDatasetIO,
        TestTextNormalizer,
        TestConfigLoader,
        TestPathManager,
        TestHashFunction,
        TestLoggingV2,
        TestQualityTracker,
        TestValidation,
        TestIntegration,
        TestChunkGeneration,
    ]
    
    for test_class in test_classes:
        tests = loader.loadTestsFromTestCase(test_class)
        suite.addTests(tests)
    
    # Run tests
    runner = unittest.TextTestRunner(verbosity=verbosity)
    result = runner.run(suite)
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"Tests run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")
    print(f"Skipped: {len(result.skipped)}")
    
    # Return exit code
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    sys.exit(run_tests())