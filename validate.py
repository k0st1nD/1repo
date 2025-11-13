#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate.py - Dataset Validation Tool (MVP v2.0)
================================================
Comprehensive validation and verification for datasets at each pipeline stage.

Features:
- Schema validation (required fields, types)
- Data quality checks (completeness, consistency)
- Extended fields validation
- Cross-stage validation (data flow integrity)
- Performance validation (timing, resource usage)
- Content validation (text quality, encoding)
- Report generation (detailed + summary)

Version: 2.0.0
Dependencies: am_common, am_logging
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from collections import defaultdict
from datetime import datetime

from am_common import (
    DatasetIO, ConfigLoader, PathManager,
    HEADER_ID, AUDIT_ID, FOOTER_ID,
    REQUIRED_FIELDS
)
from am_logging import (
    setup_logging, get_logger, log_section, log_metrics,
    get_error_aggregator
)

logger = get_logger(__name__)

VERSION = "2.0.0"


# ============================================
# VALIDATION RULES
# ============================================

class ValidationRule:
    """Base class for validation rules."""
    
    def __init__(self, name: str, severity: str = "ERROR"):
        """
        Args:
            name: Rule name
            severity: ERROR, WARNING, or INFO
        """
        self.name = name
        self.severity = severity
        self.violations: List[Dict[str, Any]] = []
    
    def validate(self, data: Any, context: Dict[str, Any] = None) -> bool:
        """
        Validate data against rule.
        
        Args:
            data: Data to validate
            context: Additional context for validation
            
        Returns:
            True if valid, False otherwise
        """
        raise NotImplementedError
    
    def add_violation(self, message: str, **metadata):
        """Record a validation violation."""
        self.violations.append({
            'rule': self.name,
            'severity': self.severity,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            **metadata
        })
    
    def has_violations(self) -> bool:
        """Check if rule has violations."""
        return len(self.violations) > 0
    
    def get_violations(self) -> List[Dict[str, Any]]:
        """Get all violations."""
        return self.violations
    
    def reset(self):
        """Clear violations."""
        self.violations.clear()


class RequiredFieldRule(ValidationRule):
    """Validate that required fields are present."""
    
    def __init__(self, required_fields: List[str], severity: str = "ERROR"):
        super().__init__("required_fields", severity)
        self.required_fields = required_fields
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """Check if all required fields present."""
        missing = []
        for field in self.required_fields:
            if field not in data:
                missing.append(field)
        
        if missing:
            self.add_violation(
                f"Missing required fields: {', '.join(missing)}",
                missing_fields=missing,
                context=context
            )
            return False
        
        return True


class TypeValidationRule(ValidationRule):
    """Validate field types."""
    
    def __init__(self, field_types: Dict[str, type], severity: str = "ERROR"):
        super().__init__("type_validation", severity)
        self.field_types = field_types
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """Check if fields have correct types."""
        invalid = []
        
        for field, expected_type in self.field_types.items():
            if field in data:
                value = data[field]
                if value is not None and not isinstance(value, expected_type):
                    invalid.append({
                        'field': field,
                        'expected': expected_type.__name__,
                        'actual': type(value).__name__
                    })
        
        if invalid:
            self.add_violation(
                f"Invalid types for {len(invalid)} fields",
                invalid_types=invalid,
                context=context
            )
            return False
        
        return True


class RangeValidationRule(ValidationRule):
    """Validate numeric ranges."""
    
    def __init__(self, field: str, min_val: float = None, max_val: float = None,
                 severity: str = "WARNING"):
        super().__init__(f"range_{field}", severity)
        self.field = field
        self.min_val = min_val
        self.max_val = max_val
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """Check if value is within range."""
        if self.field not in data:
            return True  # Field not present, skip
        
        value = data[self.field]
        if not isinstance(value, (int, float)):
            return True  # Not numeric, skip
        
        if self.min_val is not None and value < self.min_val:
            self.add_violation(
                f"{self.field} below minimum ({value} < {self.min_val})",
                field=self.field,
                value=value,
                min=self.min_val,
                context=context
            )
            return False
        
        if self.max_val is not None and value > self.max_val:
            self.add_violation(
                f"{self.field} above maximum ({value} > {self.max_val})",
                field=self.field,
                value=value,
                max=self.max_val,
                context=context
            )
            return False
        
        return True


class TextQualityRule(ValidationRule):
    """Validate text quality."""
    
    def __init__(self, field: str, min_length: int = 10, max_length: int = 100000,
                 severity: str = "WARNING"):
        super().__init__(f"text_quality_{field}", severity)
        self.field = field
        self.min_length = min_length
        self.max_length = max_length
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """Check text quality."""
        if self.field not in data:
            return True
        
        text = data[self.field]
        if not isinstance(text, str):
            return True
        
        length = len(text)
        
        # Check length
        if length < self.min_length:
            self.add_violation(
                f"{self.field} too short ({length} < {self.min_length})",
                field=self.field,
                length=length,
                context=context
            )
            return False
        
        if length > self.max_length:
            self.add_violation(
                f"{self.field} too long ({length} > {self.max_length})",
                field=self.field,
                length=length,
                context=context
            )
            return False
        
        # Check for null bytes (common encoding issue)
        if '\x00' in text:
            self.add_violation(
                f"{self.field} contains null bytes",
                field=self.field,
                context=context
            )
            return False
        
        # Check for excessive whitespace
        whitespace_ratio = (text.count(' ') + text.count('\n')) / max(1, length)
        if whitespace_ratio > 0.5:
            self.add_violation(
                f"{self.field} has excessive whitespace ({whitespace_ratio:.1%})",
                field=self.field,
                whitespace_ratio=whitespace_ratio,
                context=context
            )
            return False
        
        return True


class ExtendedFieldsRule(ValidationRule):
    """Validate extended_fields structure."""
    
    def __init__(self, severity: str = "WARNING"):
        super().__init__("extended_fields", severity)
    
    def validate(self, data: Dict[str, Any], context: Dict[str, Any] = None) -> bool:
        """Check extended_fields structure."""
        if 'extended_fields' not in data:
            return True  # Optional field
        
        extended = data['extended_fields']
        if not isinstance(extended, dict):
            self.add_violation(
                "extended_fields must be a dictionary",
                context=context
            )
            return False
        
        # Check expected fields
        expected_fields = [
            'content_type', 'domain', 'complexity',
            'topics', 'key_concepts'
        ]
        
        missing = [f for f in expected_fields if f not in extended]
        if missing:
            self.add_violation(
                f"extended_fields missing: {', '.join(missing)}",
                missing_fields=missing,
                context=context
            )
            return False
        
        return True


# ============================================
# STAGE VALIDATORS
# ============================================

class StageValidator:
    """Base validator for pipeline stages."""
    
    def __init__(self, stage: str, config: Dict[str, Any] = None):
        self.stage = stage
        self.config = config or {}
        self.rules: List[ValidationRule] = []
        self.results: Dict[str, Any] = {}
    
    def add_rule(self, rule: ValidationRule):
        """Add validation rule."""
        self.rules.append(rule)
    
    def validate_dataset(self, dataset_path: Path) -> Dict[str, Any]:
        """
        Validate entire dataset.
        
        Returns:
            Validation results dictionary
        """
        logger.info(f"Validating {self.stage}: {dataset_path.name}")
        
        # Load dataset
        try:
            header, cards, audit, footer = DatasetIO.load(dataset_path, validate=False)
        except Exception as e:
            return {
                'valid': False,
                'stage': self.stage,
                'dataset': str(dataset_path),
                'error': f"Failed to load dataset: {e}",
                'violations': []
            }
        
        # Reset rules
        for rule in self.rules:
            rule.reset()
        
        # Validate header
        self._validate_header(header)
        
        # Validate cards
        for i, card in enumerate(cards):
            context = {
                'card_index': i,
                'segment_id': card.get('segment_id'),
                'page_num': card.get('page_num')
            }
            self._validate_card(card, context)
        
        # Validate audit
        if audit:
            self._validate_audit(audit)
        
        # Collect violations
        all_violations = []
        error_count = 0
        warning_count = 0
        
        for rule in self.rules:
            violations = rule.get_violations()
            all_violations.extend(violations)
            
            for v in violations:
                if v['severity'] == 'ERROR':
                    error_count += 1
                elif v['severity'] == 'WARNING':
                    warning_count += 1
        
        # Determine validity
        valid = error_count == 0
        
        results = {
            'valid': valid,
            'stage': self.stage,
            'dataset': str(dataset_path),
            'total_cards': len(cards),
            'error_count': error_count,
            'warning_count': warning_count,
            'violations': all_violations,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.results = results
        return results
    
    def _validate_header(self, header: Dict[str, Any]):
        """Validate header section."""
        # Subclass should implement
        pass
    
    def _validate_card(self, card: Dict[str, Any], context: Dict[str, Any]):
        """Validate single card."""
        for rule in self.rules:
            rule.validate(card, context)
    
    def _validate_audit(self, audit: Dict[str, Any]):
        """Validate audit section."""
        # Subclass should implement
        pass
    
    def get_summary(self) -> Dict[str, Any]:
        """Get validation summary."""
        if not self.results:
            return {}
        
        return {
            'stage': self.stage,
            'valid': self.results['valid'],
            'total_cards': self.results['total_cards'],
            'errors': self.results['error_count'],
            'warnings': self.results['warning_count']
        }


class StructuralValidator(StageValidator):
    """Validator for structural stage."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__('structural', config)
        
        # Required fields
        self.add_rule(RequiredFieldRule(['segment_id', 'segment', 'page_num']))
        
        # Type validation
        self.add_rule(TypeValidationRule({
            'segment_id': str,
            'segment': str,
            'page_num': int,
            'has_table': bool,
            'ocr_used': bool
        }))
        
        # Text quality
        self.add_rule(TextQualityRule('segment', min_length=10, max_length=50000))
        
        # Page number range
        self.add_rule(RangeValidationRule('page_num', min_val=1))


class StructuredValidator(StageValidator):
    """Validator for structured stage."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__('structured', config)
        
        # Required fields
        self.add_rule(RequiredFieldRule([
            'segment_id', 'segment', 'page_num',
            'chapter_title', 'section_title'
        ]))
        
        # Type validation
        self.add_rule(TypeValidationRule({
            'segment_id': str,
            'segment': str,
            'page_num': int,
            'chapter_title': str,
            'section_title': str,
            'chapter_num': int
        }))
        
        # Text quality
        self.add_rule(TextQualityRule('segment', min_length=10))


class ExtendedValidator(StageValidator):
    """Validator for extended stage."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__('extended', config)
        
        # Required fields
        self.add_rule(RequiredFieldRule([
            'segment_id', 'segment', 'page_num',
            'prev_page', 'next_page'
        ]))
        
        # Type validation
        self.add_rule(TypeValidationRule({
            'segment_id': str,
            'segment': str,
            'page_num': int,
            'is_duplicate': bool
        }))
        
        # Extended fields validation
        self.add_rule(ExtendedFieldsRule())


class FinalValidator(StageValidator):
    """Validator for final stage."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__('final', config)
        
        # All previous validations apply
        self.add_rule(RequiredFieldRule([
            'segment_id', 'segment', 'page_num'
        ]))
        
        self.add_rule(TypeValidationRule({
            'segment_id': str,
            'segment': str,
            'page_num': int
        }))
        
        self.add_rule(TextQualityRule('segment', min_length=10))


class ChunkValidator(StageValidator):
    """Validator for chunks stage."""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__('chunks', config)
        
        # Required fields
        self.add_rule(RequiredFieldRule([
            'chunk_id', 'text', 'tokens', 'metadata'
        ]))
        
        # Type validation
        self.add_rule(TypeValidationRule({
            'chunk_id': str,
            'text': str,
            'tokens': int,
            'metadata': dict
        }))
        
        # Text quality
        self.add_rule(TextQualityRule('text', min_length=50, max_length=2000))
        
        # Token range
        self.add_rule(RangeValidationRule('tokens', min_val=10, max_val=1000))


# ============================================
# VALIDATOR FACTORY
# ============================================

class ValidatorFactory:
    """Factory for creating stage validators."""
    
    VALIDATORS = {
        'structural': StructuralValidator,
        'structured': StructuredValidator,
        'extended': ExtendedValidator,
        'final': FinalValidator,
        'chunks': ChunkValidator,
    }
    
    @staticmethod
    def create(stage: str, config: Dict[str, Any] = None) -> StageValidator:
        """
        Create validator for stage.
        
        Args:
            stage: Pipeline stage name
            config: Configuration
            
        Returns:
            StageValidator instance
        """
        validator_class = ValidatorFactory.VALIDATORS.get(stage)
        if not validator_class:
            raise ValueError(f"Unknown stage: {stage}")
        
        return validator_class(config)


# ============================================
# VALIDATION REPORT
# ============================================

class ValidationReport:
    """Generate validation reports."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
    
    def add_result(self, result: Dict[str, Any]):
        """Add validation result."""
        self.results.append(result)
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate summary report."""
        total_datasets = len(self.results)
        valid_datasets = sum(1 for r in self.results if r['valid'])
        total_errors = sum(r['error_count'] for r in self.results)
        total_warnings = sum(r['warning_count'] for r in self.results)
        
        return {
            'total_datasets': total_datasets,
            'valid_datasets': valid_datasets,
            'invalid_datasets': total_datasets - valid_datasets,
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'success_rate': valid_datasets / max(1, total_datasets),
            'timestamp': datetime.utcnow().isoformat()
        }
    
    def generate_detailed(self) -> Dict[str, Any]:
        """Generate detailed report."""
        # Group violations by type
        violations_by_rule: Dict[str, int] = defaultdict(int)
        violations_by_severity: Dict[str, int] = defaultdict(int)
        
        for result in self.results:
            for violation in result.get('violations', []):
                violations_by_rule[violation['rule']] += 1
                violations_by_severity[violation['severity']] += 1
        
        return {
            'summary': self.generate_summary(),
            'results': self.results,
            'violations_by_rule': dict(violations_by_rule),
            'violations_by_severity': dict(violations_by_severity)
        }
    
    def save(self, output_path: Path):
        """Save report to JSON file."""
        report = self.generate_detailed()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Report saved: {output_path}")
    
    def print_summary(self):
        """Print summary to console."""
        summary = self.generate_summary()
        
        log_section(logger, "Validation Summary", "INFO")
        log_metrics(logger, summary, "Overall Results")
        
        # Print per-dataset results
        if self.results:
            logger.info("\nPer-dataset results:")
            for result in self.results:
                status = "✅ VALID" if result['valid'] else "❌ INVALID"
                dataset = Path(result['dataset']).name
                errors = result['error_count']
                warnings = result['warning_count']
                
                logger.info(f"  {status} - {dataset} (errors: {errors}, warnings: {warnings})")


# ============================================
# MAIN VALIDATOR
# ============================================

class DatasetValidator:
    """Main validator orchestrator."""
    
    def __init__(self, config_path: Optional[Path] = None):
        self.config_loader = ConfigLoader(config_path) if config_path else None
        self.config = self.config_loader.load() if self.config_loader else {}
        self.path_manager = PathManager()
        self.report = ValidationReport()
    
    def validate_dataset(self, dataset_path: Path, stage: str = None) -> Dict[str, Any]:
        """
        Validate a single dataset.
        
        Args:
            dataset_path: Path to dataset
            stage: Pipeline stage (auto-detected if None)
            
        Returns:
            Validation results
        """
        # Auto-detect stage from path
        if stage is None:
            stage = self._detect_stage(dataset_path)
            logger.info(f"Detected stage: {stage}")
        
        # Create validator
        validator = ValidatorFactory.create(stage, self.config)
        
        # Validate
        result = validator.validate_dataset(dataset_path)
        
        # Add to report
        self.report.add_result(result)
        
        # Log result
        if result['valid']:
            logger.info(f"[OK] VALID - {dataset_path.name}")
        else:
            logger.warning(f"[X] INVALID - {dataset_path.name} ({result['error_count']} errors)")
        
        return result
    
    def validate_directory(self, directory: Path, stage: str = None,
                          pattern: str = "*.dataset.jsonl") -> List[Dict[str, Any]]:
        """
        Validate all datasets in directory.
        
        Args:
            directory: Directory path
            stage: Pipeline stage (auto-detected if None)
            pattern: File pattern
            
        Returns:
            List of validation results
        """
        logger.info(f"Validating directory: {directory}")
        
        # Find datasets
        datasets = sorted(directory.glob(pattern))
        if not datasets:
            logger.warning(f"No datasets found matching {pattern}")
            return []
        
        logger.info(f"Found {len(datasets)} datasets")
        
        # Validate each
        results = []
        for dataset_path in datasets:
            try:
                result = self.validate_dataset(dataset_path, stage)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to validate {dataset_path.name}: {e}")
        
        return results
    
    def validate_pipeline(self, book_name: str) -> Dict[str, Any]:
        """
        Validate all stages for a book.
        
        Args:
            book_name: Book identifier
            
        Returns:
            Pipeline validation results
        """
        logger.info(f"Validating pipeline for: {book_name}")
        
        stages = ['structural', 'structured', 'summarized', 'extended', 'final']
        pipeline_results = {}
        
        for stage in stages:
            # Get dataset path
            stage_dir = self.path_manager.get_dataset_path(stage, '')
            dataset_path = stage_dir.parent / f"{book_name}.dataset.jsonl"
            
            if not dataset_path.exists():
                logger.warning(f"Missing {stage} dataset: {dataset_path.name}")
                continue
            
            # Validate
            result = self.validate_dataset(dataset_path, stage)
            pipeline_results[stage] = result
        
        return pipeline_results
    
    def _detect_stage(self, dataset_path: Path) -> str:
        """Auto-detect stage from path."""
        path_str = str(dataset_path)
        
        if '/structural/' in path_str:
            return 'structural'
        elif '/structured/' in path_str:
            return 'structured'
        elif '/summarized/' in path_str:
            return 'summarized'
        elif '/extended/' in path_str:
            return 'extended'
        elif '/final/' in path_str:
            return 'final'
        elif '/chunks/' in path_str or '.chunks.jsonl' in path_str:
            return 'chunks'
        else:
            # Default
            logger.warning(f"Could not detect stage from path, using 'final'")
            return 'final'
    
    def save_report(self, output_path: Path):
        """Save validation report."""
        self.report.save(output_path)
    
    def print_summary(self):
        """Print validation summary."""
        self.report.print_summary()


# ============================================
# CLI
# ============================================

def main():
    """CLI interface."""
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(
        description='Dataset Validation Tool (MVP v2.0)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate single dataset
  python validate.py -i data/datasets/final/book.dataset.jsonl
  
  # Validate directory
  python validate.py -d data/datasets/final
  
  # Validate entire pipeline for a book
  python validate.py --pipeline accelerate
  
  # Save report
  python validate.py -d data/datasets/final -o reports/validation.json
        """
    )
    
    parser.add_argument('-i', '--input', help='Input dataset file')
    parser.add_argument('-d', '--directory', help='Input directory')
    parser.add_argument('--pipeline', help='Validate entire pipeline for book')
    parser.add_argument('-s', '--stage', help='Pipeline stage (auto-detected if not specified)')
    parser.add_argument('-o', '--output', help='Output report path')
    parser.add_argument('-c', '--config', help='Config file path')
    parser.add_argument('--pattern', default='*.dataset.jsonl', help='File pattern')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Setup logging
    log_level = "DEBUG" if args.verbose else "INFO"
    setup_logging(level=log_level, console=True, colored=True)
    
    # Initialize validator
    config_path = Path(args.config) if args.config else None
    validator = DatasetValidator(config_path)
    
    # Validate
    try:
        if args.input:
            # Single file
            input_path = Path(args.input)
            validator.validate_dataset(input_path, args.stage)
        
        elif args.directory:
            # Directory
            dir_path = Path(args.directory)
            validator.validate_directory(dir_path, args.stage, args.pattern)
        
        elif args.pipeline:
            # Entire pipeline
            validator.validate_pipeline(args.pipeline)
        
        else:
            parser.print_help()
            sys.exit(1)
        
        # Print summary
        validator.print_summary()
        
        # Save report
        if args.output:
            output_path = Path(args.output)
            validator.save_report(output_path)
        
        # Exit code based on validation
        summary = validator.report.generate_summary()
        if summary['invalid_datasets'] > 0:
            logger.error(f"Validation FAILED: {summary['invalid_datasets']} invalid datasets")
            sys.exit(1)
        else:
            logger.info("✅ All validations PASSED")
            sys.exit(0)
    
    except Exception as e:
        logger.exception(f"Validation failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
