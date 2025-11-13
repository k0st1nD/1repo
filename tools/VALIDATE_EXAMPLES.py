#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
VALIDATE_EXAMPLES.py - Usage Examples for validate.py
======================================================
Practical examples of using the validation tool.
"""

# ============================================
# EXAMPLE 1: Basic Validation
# ============================================

def example_basic_validation():
    """Simple dataset validation."""
    from validate import DatasetValidator
    from pathlib import Path
    
    # Initialize validator
    validator = DatasetValidator()
    
    # Validate single dataset
    result = validator.validate_dataset(
        Path('data/datasets/final/accelerate.dataset.jsonl'),
        stage='final'
    )
    
    # Check result
    if result['valid']:
        print(f"✅ Dataset is valid")
    else:
        print(f"❌ Dataset has {result['error_count']} errors")
        
        # Print violations
        for violation in result['violations']:
            print(f"  {violation['severity']}: {violation['message']}")


# ============================================
# EXAMPLE 2: Batch Validation
# ============================================

def example_batch_validation():
    """Validate multiple datasets."""
    from validate import DatasetValidator
    from pathlib import Path
    
    validator = DatasetValidator()
    
    # Validate directory
    results = validator.validate_directory(
        Path('data/datasets/extended'),
        stage='extended',
        pattern='*.dataset.jsonl'
    )
    
    # Analyze results
    valid_count = sum(1 for r in results if r['valid'])
    total_count = len(results)
    
    print(f"Valid: {valid_count}/{total_count} ({valid_count/total_count:.1%})")
    
    # Find datasets with issues
    invalid = [r for r in results if not r['valid']]
    
    for result in invalid:
        print(f"\n❌ {Path(result['dataset']).name}")
        print(f"   Errors: {result['error_count']}")
        print(f"   Warnings: {result['warning_count']}")


# ============================================
# EXAMPLE 3: Pipeline Validation
# ============================================

def example_pipeline_validation():
    """Validate entire pipeline for a book."""
    from validate import DatasetValidator
    
    validator = DatasetValidator()
    
    # Validate all stages
    pipeline_results = validator.validate_pipeline('accelerate')
    
    # Check each stage
    for stage, result in pipeline_results.items():
        status = "✅" if result['valid'] else "❌"
        print(f"{status} {stage:15} - errors: {result['error_count']}, warnings: {result['warning_count']}")


# ============================================
# EXAMPLE 4: Custom Validation Rule
# ============================================

def example_custom_rule():
    """Create and use custom validation rule."""
    from validate import ValidationRule, StageValidator
    from pathlib import Path
    
    # Define custom rule
    class HasImageRule(ValidationRule):
        """Check if page mentions images."""
        
        def __init__(self):
            super().__init__("has_image_reference", severity="INFO")
        
        def validate(self, data, context=None):
            text = data.get('segment', '')
            
            # Check for image references
            image_keywords = ['Figure', 'Fig.', 'Image', 'Diagram', 'Chart']
            has_image = any(kw in text for kw in image_keywords)
            
            if has_image:
                self.add_violation(
                    "Page contains image reference",
                    context=context,
                    keywords_found=[kw for kw in image_keywords if kw in text]
                )
            
            return True  # Always valid, just informational
    
    # Create custom validator
    class CustomValidator(StageValidator):
        def __init__(self):
            super().__init__('custom', {})
            self.add_rule(HasImageRule())
    
    # Use it
    validator = CustomValidator()
    result = validator.validate_dataset(
        Path('data/datasets/final/accelerate.dataset.jsonl')
    )
    
    # Print image references
    image_refs = [v for v in result['violations'] if v['rule'] == 'has_image_reference']
    print(f"Found {len(image_refs)} pages with image references")


# ============================================
# EXAMPLE 5: Validation in Pipeline
# ============================================

def example_validation_in_pipeline():
    """Integrate validation into pipeline processing."""
    from validate import DatasetValidator
    from pathlib import Path
    import sys
    
    validator = DatasetValidator()
    
    def process_with_validation(stage_name, input_path, process_func):
        """Process and validate."""
        print(f"Processing {stage_name}...")
        
        # Process
        output_path = process_func(input_path)
        
        # Validate
        print(f"Validating {stage_name} output...")
        result = validator.validate_dataset(output_path, stage_name)
        
        if not result['valid']:
            print(f"❌ Validation failed: {result['error_count']} errors")
            
            # Print first 5 violations
            for violation in result['violations'][:5]:
                print(f"  - {violation['message']}")
            
            # Decide whether to continue
            if result['error_count'] > 10:
                print("Too many errors, stopping pipeline")
                sys.exit(1)
        else:
            print(f"✅ Validation passed")
        
        return output_path
    
    # Example usage
    # output = process_with_validation('structural', input_pdf, structural_processor)


# ============================================
# EXAMPLE 6: Quality Report Generation
# ============================================

def example_quality_report():
    """Generate comprehensive quality report."""
    from validate import DatasetValidator
    from pathlib import Path
    import json
    
    validator = DatasetValidator()
    
    # Validate all stages for multiple books
    books = ['accelerate', 'devops_handbook', 'phoenix_project']
    
    for book in books:
        print(f"\nValidating {book}...")
        validator.validate_pipeline(book)
    
    # Generate report
    report = validator.report.generate_detailed()
    
    # Save report
    output_path = Path('reports/quality_report.json')
    validator.save_report(output_path)
    
    # Print summary
    summary = report['summary']
    print(f"\n{'='*60}")
    print(f"Quality Report Summary")
    print(f"{'='*60}")
    print(f"Total datasets: {summary['total_datasets']}")
    print(f"Valid: {summary['valid_datasets']}")
    print(f"Invalid: {summary['invalid_datasets']}")
    print(f"Success rate: {summary['success_rate']:.1%}")
    print(f"\nReport saved: {output_path}")


# ============================================
# EXAMPLE 7: Validation with Error Recovery
# ============================================

def example_error_recovery():
    """Validate and attempt to fix common issues."""
    from validate import DatasetValidator
    from pathlib import Path
    from am_common import DatasetIO
    
    validator = DatasetValidator()
    
    dataset_path = Path('data/datasets/extended/book.dataset.jsonl')
    
    # Validate
    result = validator.validate_dataset(dataset_path, stage='extended')
    
    if not result['valid']:
        print(f"Found {result['error_count']} errors")
        
        # Analyze violations
        missing_fields = [
            v for v in result['violations'] 
            if v['rule'] == 'required_fields'
        ]
        
        if missing_fields:
            print("\nAttempting to fix missing fields...")
            
            # Load dataset
            header, cards, audit, footer = DatasetIO.load(dataset_path, validate=False)
            
            # Fix cards
            fixed_count = 0
            for card in cards:
                # Add missing prev_page/next_page if needed
                if 'prev_page' not in card:
                    card['prev_page'] = None
                    fixed_count += 1
                if 'next_page' not in card:
                    card['next_page'] = None
                    fixed_count += 1
            
            # Save fixed dataset
            fixed_path = dataset_path.parent / f"{dataset_path.stem}_fixed.dataset.jsonl"
            DatasetIO.save(fixed_path, header, cards, audit, footer)
            
            print(f"Fixed {fixed_count} issues, saved to {fixed_path}")
            
            # Re-validate
            result2 = validator.validate_dataset(fixed_path, stage='extended')
            if result2['valid']:
                print("✅ Fixed dataset is now valid!")


# ============================================
# EXAMPLE 8: Continuous Validation
# ============================================

def example_continuous_validation():
    """Monitor directory for new datasets and validate."""
    from validate import DatasetValidator
    from pathlib import Path
    import time
    
    validator = DatasetValidator()
    watch_dir = Path('data/datasets/final')
    
    print(f"Watching {watch_dir} for new datasets...")
    
    validated_files = set()
    
    while True:
        # Find datasets
        datasets = set(watch_dir.glob('*.dataset.jsonl'))
        
        # Find new datasets
        new_datasets = datasets - validated_files
        
        for dataset_path in new_datasets:
            print(f"\n🔍 New dataset detected: {dataset_path.name}")
            
            # Validate
            result = validator.validate_dataset(dataset_path, stage='final')
            
            if result['valid']:
                print(f"✅ Valid")
            else:
                print(f"❌ Invalid: {result['error_count']} errors")
                
                # Send alert (example)
                # send_alert(f"Invalid dataset: {dataset_path.name}")
            
            validated_files.add(dataset_path)
        
        # Wait before next check
        time.sleep(10)


# ============================================
# EXAMPLE 9: Test Suite Integration
# ============================================

def example_test_suite():
    """Use validation in test suite."""
    import unittest
    from validate import DatasetValidator
    from pathlib import Path
    
    class TestDatasetQuality(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            cls.validator = DatasetValidator()
        
        def test_structural_output_valid(self):
            """Test structural stage produces valid output."""
            result = self.validator.validate_dataset(
                Path('test_data/structural_output.jsonl'),
                stage='structural'
            )
            
            self.assertTrue(result['valid'], 
                          f"Validation failed with {result['error_count']} errors")
            self.assertEqual(result['error_count'], 0)
        
        def test_extended_has_extended_fields(self):
            """Test extended stage has extended_fields."""
            result = self.validator.validate_dataset(
                Path('test_data/extended_output.jsonl'),
                stage='extended'
            )
            
            # Should have no violations about missing extended_fields
            extended_violations = [
                v for v in result['violations']
                if 'extended_fields' in v['message']
            ]
            
            self.assertEqual(len(extended_violations), 0,
                           "Extended fields should be present")
        
        def test_chunks_token_count(self):
            """Test chunks have valid token counts."""
            result = self.validator.validate_dataset(
                Path('test_data/chunks_output.jsonl'),
                stage='chunks'
            )
            
            # Should have no token range violations
            token_violations = [
                v for v in result['violations']
                if 'tokens' in v['message']
            ]
            
            self.assertEqual(len(token_violations), 0,
                           "All chunks should have valid token counts")
    
    # Run tests
    # unittest.main()


# ============================================
# EXAMPLE 10: Validation Dashboard Data
# ============================================

def example_dashboard_data():
    """Generate data for validation dashboard."""
    from validate import DatasetValidator
    from pathlib import Path
    import json
    from datetime import datetime
    
    validator = DatasetValidator()
    
    # Validate all datasets
    all_stages = ['structural', 'structured', 'extended', 'final']
    
    dashboard_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'stages': {}
    }
    
    for stage in all_stages:
        stage_dir = Path(f'data/datasets/{stage}')
        
        if not stage_dir.exists():
            continue
        
        results = validator.validate_directory(stage_dir, stage)
        
        # Aggregate metrics
        total = len(results)
        valid = sum(1 for r in results if r['valid'])
        total_errors = sum(r['error_count'] for r in results)
        total_warnings = sum(r['warning_count'] for r in results)
        
        dashboard_data['stages'][stage] = {
            'total_datasets': total,
            'valid_datasets': valid,
            'invalid_datasets': total - valid,
            'success_rate': valid / max(1, total),
            'total_errors': total_errors,
            'total_warnings': total_warnings,
            'avg_errors_per_dataset': total_errors / max(1, total),
            'avg_warnings_per_dataset': total_warnings / max(1, total)
        }
    
    # Save for dashboard
    output_path = Path('reports/dashboard_data.json')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(dashboard_data, f, indent=2)
    
    print(f"Dashboard data saved: {output_path}")
    
    # Print summary
    print("\n" + "="*60)
    print("Validation Dashboard Summary")
    print("="*60)
    
    for stage, data in dashboard_data['stages'].items():
        print(f"\n{stage.upper()}:")
        print(f"  Success rate: {data['success_rate']:.1%}")
        print(f"  Avg errors/dataset: {data['avg_errors_per_dataset']:.1f}")
        print(f"  Avg warnings/dataset: {data['avg_warnings_per_dataset']:.1f}")


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    print("Validation Examples")
    print("="*60)
    print("\n1. Basic validation")
    print("2. Batch validation")
    print("3. Pipeline validation")
    print("4. Custom rule")
    print("5. Validation in pipeline")
    print("6. Quality report")
    print("7. Error recovery")
    print("8. Continuous validation")
    print("9. Test suite")
    print("10. Dashboard data")
    print("\nRun individual examples by calling the functions")
