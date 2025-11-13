#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_finalize.py - Dataset Finalization (MVP v2.0)
================================================
Stage 5: Final validation and preparation for chunking

Features:
- Validate all required fields
- Clean and normalize data
- Remove invalid cards
- Add final metadata
- Quality metrics tracking

Version: 2.0.0
Dependencies: am_common
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from am_common import (
    DatasetIO, ConfigLoader, PathManager, Validators,
    utc_now_iso
)

logger = logging.getLogger('am_finalize')

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"

# Required fields for final dataset
REQUIRED_FIELDS = [
    'segment_id',
    'segment',
    'page_num',
    'source_file',
]

# Optional but expected fields
EXPECTED_FIELDS = [
    'chapter_num',
    'chapter_title',
    'section_num',
    'section_title',
    'l1_summary',
    'l2_summary',
    'ocr_used',
    'has_table',
    'prev_page',
    'next_page',
]


class DataValidator:
    """Validate dataset cards."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.strict_mode = config.get('strict_mode', False)
        self.remove_invalid = config.get('remove_invalid', False)
        self.min_segment_length = config.get('min_segment_length', 10)
    
    def validate_card(self, card: Dict[str, Any]) -> List[str]:
        """
        Validate single card.
        
        Returns:
            List of validation errors (empty if valid)
        """
        errors = []
        
        # Check required fields
        for field in REQUIRED_FIELDS:
            if field not in card:
                errors.append(f"Missing required field: {field}")
            elif not card[field]:
                errors.append(f"Empty required field: {field}")
        
        # Validate types
        if 'page_num' in card and not isinstance(card['page_num'], int):
            errors.append(f"Invalid type for page_num: {type(card['page_num'])}")
        
        if 'segment' in card:
            if not isinstance(card['segment'], str):
                errors.append(f"Invalid type for segment: {type(card['segment'])}")
            elif len(card['segment'].strip()) < self.min_segment_length:
                errors.append(f"Segment too short: {len(card['segment'])} chars")
        
        # Validate segment_id format
        if 'segment_id' in card:
            sid = card['segment_id']
            if not isinstance(sid, str) or not sid:
                errors.append("Invalid segment_id format")
        
        return errors
    
    def validate_dataset(self, cards: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Validate entire dataset.
        
        Returns:
            Validation report with errors and warnings
        """
        errors = []
        warnings = []
        invalid_cards = []
        
        # Track seen segment_ids
        seen_ids: Set[str] = set()
        
        for idx, card in enumerate(cards):
            card_errors = self.validate_card(card)
            
            if card_errors:
                if self.strict_mode:
                    errors.extend([f"Card {idx}: {e}" for e in card_errors])
                else:
                    warnings.extend([f"Card {idx}: {e}" for e in card_errors])
                
                invalid_cards.append({
                    'index': idx,
                    'segment_id': card.get('segment_id', 'unknown'),
                    'errors': card_errors,
                })
            
            # Check for duplicate segment_ids
            sid = card.get('segment_id')
            if sid:
                if sid in seen_ids:
                    warnings.append(f"Duplicate segment_id: {sid}")
                seen_ids.add(sid)
            
            # Check expected fields
            for field in EXPECTED_FIELDS:
                if field not in card:
                    warnings.append(f"Card {idx}: Missing expected field: {field}")
        
        return {
            'valid': len(errors) == 0,
            'error_count': len(errors),
            'warning_count': len(warnings),
            'errors': errors[:10],  # Limit output
            'warnings': warnings[:20],
            'invalid_cards': invalid_cards,
        }


class DataCleaner:
    """Clean and normalize dataset."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.remove_empty_fields = config.get('remove_empty_fields', True)
        self.normalize_types = config.get('normalize_types', True)
    
    def clean_card(self, card: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean single card.
        
        Returns:
            Cleaned card
        """
        cleaned = card.copy()
        
        # Remove empty fields if enabled (but keep required fields + fields needed for downstream stages)
        if self.remove_empty_fields:
            # Fields needed for downstream stages (chunking, embedding)
            keep_fields = set(REQUIRED_FIELDS + ['l1_summary', 'l2_summary'])
            cleaned = {
                k: v for k, v in cleaned.items()
                if v is not None and (v != '' or k in keep_fields)
            }
        
        # Normalize types
        if self.normalize_types:
            # Ensure page_num is int
            if 'page_num' in cleaned:
                try:
                    cleaned['page_num'] = int(cleaned['page_num'])
                except (ValueError, TypeError):
                    pass
            
            # Ensure boolean fields are bool
            bool_fields = ['ocr_used', 'has_table', 'is_duplicate']
            for field in bool_fields:
                if field in cleaned:
                    cleaned[field] = bool(cleaned[field])
            
            # Ensure string fields are strings
            string_fields = ['segment', 'l1_summary', 'l2_summary', 'chapter_title', 'section_title']
            for field in string_fields:
                if field in cleaned and cleaned[field] is not None:
                    cleaned[field] = str(cleaned[field])
        
        return cleaned
    
    def clean_dataset(self, cards: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean all cards in dataset."""
        return [self.clean_card(card) for card in cards]


class FinalizeProcessor:
    """Main processor for finalization stage."""
    
    def __init__(self, config_path: Optional[Path] = None):
        # Load config
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.load()
        self.stage_config = self.config_loader.get_stage_config('finalize')
        
        # Components
        self.path_manager = PathManager()
        self.validator = DataValidator(self.stage_config.get('validation', {}))
        self.cleaner = DataCleaner(self.stage_config.get('cleaning', {}))
        
        # Quality tracking
        self.quality_tracker = None
    
    def process_dataset(self, input_path: Path,
                       output_dir: Optional[Path] = None) -> Path:
        """
        Process dataset to finalize it.
        
        Args:
            input_path: path to input dataset (from extended)
            output_dir: output directory (default: auto from PathManager)
            
        Returns:
            path to output dataset
        """
        logger.info(f"Processing: {input_path.name}")
        
        if output_dir is None:
            output_dir = self.path_manager.dataset_final
        
        # Load dataset
        header, cards, audit, footer = DatasetIO.load(input_path)
        
        # Validate dataset
        validation_report = self.validator.validate_dataset(cards)
        
        if not validation_report['valid']:
            if self.validator.strict_mode:
                raise ValueError(f"Dataset validation failed: {validation_report['error_count']} errors")
            else:
                logger.warning(f"Dataset has {validation_report['warning_count']} warnings")
        
        # Remove invalid cards if configured
        if self.validator.remove_invalid and validation_report['invalid_cards']:
            invalid_indices = {c['index'] for c in validation_report['invalid_cards']}
            cards = [c for i, c in enumerate(cards) if i not in invalid_indices]
            logger.info(f"Removed {len(invalid_indices)} invalid cards")
        
        # Clean cards
        cards = self.cleaner.clean_dataset(cards)
        
        # Update header
        header['stage'] = 'final'
        header['finalized_at'] = utc_now_iso()
        header['total_cards'] = len(cards)
        header['validation_passed'] = validation_report['valid']
        
        # Update audit
        audit = self._build_audit(
            cards=cards,
            validation=validation_report,
        )
        
        # Save dataset
        output_path = output_dir / input_path.name
        DatasetIO.save(output_path, header, cards, audit, footer)
        
        # Quality tracking
        if self.quality_tracker:
            metrics = self._calculate_metrics(cards, validation_report)
            self.quality_tracker.track('finalize', input_path.name, metrics)
        
        logger.info(f"Saved: {output_path.name}")
        return output_path
    
    def _build_audit(self, cards: List[Dict[str, Any]],
                    validation: Dict[str, Any]) -> Dict[str, Any]:
        """Build audit section."""
        # Calculate field coverage
        field_coverage = {}
        for field in EXPECTED_FIELDS:
            count = sum(1 for c in cards if field in c and c[field])
            field_coverage[field] = {
                'present': count,
                'coverage': count / len(cards) if cards else 0,
            }
        
        return {
            'total_cards': len(cards),
            'validation': {
                'valid': validation['valid'],
                'errors': validation['error_count'],
                'warnings': validation['warning_count'],
            },
            'field_coverage': field_coverage,
            'stage': 'finalize',
            'version': VERSION,
            'created_at': utc_now_iso(),
        }
    
    def _calculate_metrics(self, cards: List[Dict[str, Any]],
                          validation: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate quality metrics."""
        total = len(cards)
        
        # Calculate field completeness
        completeness_scores = []
        for card in cards:
            present = sum(1 for field in EXPECTED_FIELDS if field in card and card[field])
            score = present / len(EXPECTED_FIELDS)
            completeness_scores.append(score)
        
        avg_completeness = sum(completeness_scores) / len(completeness_scores) if completeness_scores else 0
        
        # Count cards with structure
        with_structure = sum(
            1 for c in cards 
            if c.get('chapter_num') or c.get('section_num')
        )
        
        # Count cards with summaries
        with_summaries = sum(1 for c in cards if c.get('l1_summary'))
        
        return {
            'total_cards': total,
            'validation_errors': validation['error_count'],
            'validation_warnings': validation['warning_count'],
            'avg_completeness': round(avg_completeness, 3),
            'cards_with_structure': with_structure,
            'structure_coverage': with_structure / total if total > 0 else 0,
            'cards_with_summaries': with_summaries,
            'summary_coverage': with_summaries / total if total > 0 else 0,
        }


def main():
    """CLI interface."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description='Dataset finalization (MVP v2.0)')
    parser.add_argument('-i', '--input', required=True,
                       help='Input dataset or directory')
    parser.add_argument('-o', '--output',
                       help='Output directory')
    parser.add_argument('-c', '--config',
                       help='Config file path')
    parser.add_argument('--pattern', default='*.dataset.jsonl',
                       help='File pattern for directory input')
    parser.add_argument('--strict', action='store_true',
                       help='Strict validation mode (fail on errors)')
    parser.add_argument('--remove-invalid', action='store_true',
                       help='Remove invalid cards')
    
    args = parser.parse_args()
    
    # Initialize processor
    config_path = Path(args.config) if args.config else None
    processor = FinalizeProcessor(config_path)
    
    # Override settings if specified
    if args.strict:
        processor.validator.strict_mode = True
    if args.remove_invalid:
        processor.validator.remove_invalid = True
    
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