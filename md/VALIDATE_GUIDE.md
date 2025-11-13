# 📋 validate.py - Dataset Validation Tool

## 🎯 Overview

Comprehensive validation tool for Archivist Magika datasets at every pipeline stage.

**Features:**
- ✅ Schema validation (required fields, types)
- ✅ Data quality checks (completeness, consistency)
- ✅ Extended fields validation
- ✅ Text quality validation (encoding, length, whitespace)
- ✅ Cross-stage validation
- ✅ Detailed + summary reports
- ✅ CLI + programmatic API

---

## 🚀 Quick Start

### Basic Usage

```bash
# Validate single dataset
python validate.py -i data/datasets/final/book.dataset.jsonl

# Validate entire directory
python validate.py -d data/datasets/final

# Validate full pipeline for a book
python validate.py --pipeline accelerate

# Save report to file
python validate.py -d data/datasets/final -o reports/validation.json
```

---

## 📖 Detailed Usage

### 1. Single Dataset Validation

```bash
python validate.py -i data/datasets/structural/accelerate.dataset.jsonl
```

**Output:**
```
============================================================
  Validating structural: accelerate.dataset.jsonl
============================================================
✅ VALID - accelerate.dataset.jsonl

============================================================
  Validation Summary
============================================================
Overall Results:
  total_datasets: 1
  valid_datasets: 1
  invalid_datasets: 0
  total_errors: 0
  total_warnings: 0
  success_rate: 1.0
```

---

### 2. Directory Validation

```bash
python validate.py -d data/datasets/extended --pattern "*.dataset.jsonl"
```

**Output:**
```
Found 5 datasets
✅ VALID - book1.dataset.jsonl
✅ VALID - book2.dataset.jsonl
❌ INVALID - book3.dataset.jsonl (3 errors)
✅ VALID - book4.dataset.jsonl
✅ VALID - book5.dataset.jsonl

Per-dataset results:
  ✅ VALID - book1.dataset.jsonl (errors: 0, warnings: 0)
  ✅ VALID - book2.dataset.jsonl (errors: 0, warnings: 1)
  ❌ INVALID - book3.dataset.jsonl (errors: 3, warnings: 2)
  ✅ VALID - book4.dataset.jsonl (errors: 0, warnings: 0)
  ✅ VALID - book5.dataset.jsonl (errors: 0, warnings: 0)

Total: 4/5 valid (80%)
```

---

### 3. Pipeline Validation

```bash
python validate.py --pipeline accelerate
```

**Validates all stages:**
- structural/accelerate.dataset.jsonl
- structured/accelerate.dataset.jsonl
- summarized/accelerate.dataset.jsonl
- extended/accelerate.dataset.jsonl
- final/accelerate.dataset.jsonl

---

### 4. Generate Report

```bash
python validate.py -d data/datasets/final -o reports/validation_report.json
```

**Report structure:**
```json
{
  "summary": {
    "total_datasets": 5,
    "valid_datasets": 4,
    "invalid_datasets": 1,
    "total_errors": 3,
    "total_warnings": 2,
    "success_rate": 0.8
  },
  "results": [
    {
      "valid": true,
      "stage": "final",
      "dataset": "data/datasets/final/book1.dataset.jsonl",
      "total_cards": 257,
      "error_count": 0,
      "warning_count": 0,
      "violations": []
    }
  ],
  "violations_by_rule": {
    "required_fields": 2,
    "text_quality_segment": 1
  },
  "violations_by_severity": {
    "ERROR": 3,
    "WARNING": 2
  }
}
```

---

## 🔍 Validation Rules

### Stage-Specific Validations

#### 1. Structural Stage

**Required fields:**
- `segment_id` (str)
- `segment` (str)
- `page_num` (int)

**Checks:**
- ✅ Text quality (min 10 chars, max 50k chars)
- ✅ No null bytes in text
- ✅ Page number >= 1
- ✅ Boolean flags (has_table, ocr_used)

**Example violations:**
```
ERROR: Missing required field 'page_num'
WARNING: segment too short (5 < 10)
WARNING: segment contains null bytes
```

---

#### 2. Structured Stage

**Additional required fields:**
- `chapter_title` (str)
- `section_title` (str)

**Checks:**
- ✅ All structural checks
- ✅ Chapter/section structure

**Example violations:**
```
ERROR: Missing required field 'chapter_title'
WARNING: Invalid type for chapter_num (expected int, got str)
```

---

#### 3. Extended Stage

**Additional required fields:**
- `prev_page` (dict)
- `next_page` (dict)

**Checks:**
- ✅ Navigation links present
- ✅ Extended fields structure (if present)
- ✅ Deduplication info

**Example violations:**
```
ERROR: Missing required field 'prev_page'
WARNING: extended_fields missing: content_type, domain
ERROR: extended_fields must be a dictionary
```

---

#### 4. Final Stage

**Checks:**
- ✅ All previous validations
- ✅ Data completeness
- ✅ Consistency

---

#### 5. Chunks Stage

**Required fields:**
- `chunk_id` (str)
- `text` (str)
- `tokens` (int)
- `metadata` (dict)

**Checks:**
- ✅ Chunk size (50-2000 chars)
- ✅ Token count (10-1000)
- ✅ Metadata structure

**Example violations:**
```
ERROR: Missing required field 'metadata'
WARNING: text too short (30 < 50)
WARNING: tokens above maximum (1200 > 1000)
```

---

## 📊 Validation Severity Levels

### ERROR
- **Critical issues** that prevent proper processing
- Dataset marked as INVALID
- Examples:
  - Missing required fields
  - Invalid data types
  - Corrupted data

### WARNING
- **Quality issues** that don't break processing
- Dataset marked as VALID but with warnings
- Examples:
  - Text shorter than recommended
  - Missing optional fields
  - Suboptimal values

### INFO
- **Informational messages**
- No impact on validity
- Examples:
  - Statistics
  - Recommendations

---

## 🔧 Programmatic API

### Basic Usage

```python
from validate import DatasetValidator
from pathlib import Path

# Initialize validator
validator = DatasetValidator()

# Validate single dataset
result = validator.validate_dataset(
    Path('data/datasets/final/book.dataset.jsonl'),
    stage='final'
)

print(f"Valid: {result['valid']}")
print(f"Errors: {result['error_count']}")
print(f"Warnings: {result['warning_count']}")

# Print violations
for violation in result['violations']:
    print(f"{violation['severity']}: {violation['message']}")
```

---

### Validate Directory

```python
# Validate all datasets in directory
results = validator.validate_directory(
    Path('data/datasets/extended'),
    stage='extended'
)

# Check results
for result in results:
    print(f"{result['dataset']}: {result['valid']}")
```

---

### Validate Pipeline

```python
# Validate entire pipeline for a book
pipeline_results = validator.validate_pipeline('accelerate')

for stage, result in pipeline_results.items():
    print(f"{stage}: {result['valid']}")
```

---

### Generate Report

```python
# Validate multiple datasets
validator.validate_directory(Path('data/datasets/final'))

# Print summary
validator.print_summary()

# Save detailed report
validator.save_report(Path('reports/validation.json'))
```

---

## 🎨 Custom Validation Rules

### Creating Custom Rules

```python
from validate import ValidationRule

class CustomRule(ValidationRule):
    def __init__(self):
        super().__init__("custom_rule", severity="WARNING")
    
    def validate(self, data, context=None):
        # Your validation logic
        if some_condition:
            self.add_violation(
                "Custom rule violated",
                context=context
            )
            return False
        return True

# Add to validator
from validate import StageValidator

class CustomValidator(StageValidator):
    def __init__(self, config=None):
        super().__init__('custom_stage', config)
        self.add_rule(CustomRule())
```

---

## 📈 Integration with Pipeline

### In run_mvp.py

```python
from validate import DatasetValidator

class PipelineOrchestrator:
    def __init__(self):
        self.validator = DatasetValidator()
    
    def run_stage(self, stage_name, input_path):
        # Process stage
        output = self.process_stage(stage_name, input_path)
        
        # Validate output
        result = self.validator.validate_dataset(output, stage_name)
        
        if not result['valid']:
            logger.error(f"Validation failed: {result['error_count']} errors")
            if self.config.get('strict_validation', False):
                raise ValueError("Invalid dataset produced")
        
        return output
```

---

### In tests

```python
import unittest
from validate import DatasetValidator

class TestPipeline(unittest.TestCase):
    def test_structural_output(self):
        validator = DatasetValidator()
        
        result = validator.validate_dataset(
            Path('test_data/structural_output.jsonl'),
            stage='structural'
        )
        
        self.assertTrue(result['valid'])
        self.assertEqual(result['error_count'], 0)
```

---

## 🐛 Common Validation Issues

### Issue 1: Missing Required Fields

**Error:**
```
ERROR: Missing required fields: chapter_title, section_title
```

**Cause:** Structure detection stage didn't run or failed

**Fix:**
```bash
# Re-run structure detection
python am_structure_detect.py -i data/datasets/structural/book.jsonl
```

---

### Issue 2: Invalid Types

**Error:**
```
ERROR: Invalid type for page_num: expected int, got str
```

**Cause:** Data serialization issue

**Fix:**
```python
# Ensure proper types when creating cards
card['page_num'] = int(page_num)  # Not str(page_num)
```

---

### Issue 3: Text Quality

**Warning:**
```
WARNING: segment too short (5 < 10)
```

**Cause:** Extracted text is minimal (blank page, etc.)

**Options:**
- Filter out short segments
- Lower min_length threshold
- Mark as valid but note warning

---

### Issue 4: Extended Fields

**Warning:**
```
WARNING: extended_fields missing: content_type, domain
```

**Cause:** LM extraction failed or incomplete

**Fix:**
```bash
# Re-run extended stage with LM enabled
python am_extended.py -i data/datasets/summarized/book.jsonl
```

---

## ⚙️ Configuration

### In config/mvp.yaml

```yaml
validation:
  # Strict mode (fail on warnings)
  strict: false
  
  # Text quality thresholds
  min_text_length: 10
  max_text_length: 100000
  max_whitespace_ratio: 0.5
  
  # Chunk validation
  min_chunk_size: 50
  max_chunk_size: 2000
  min_tokens: 10
  max_tokens: 1000
  
  # Auto-validate after each stage
  auto_validate: true
  
  # Report output
  save_reports: true
  report_dir: "data/quality/validation"
```

---

## 📊 Example Reports

### Summary Report

```
============================================================
  Validation Summary
============================================================
Overall Results:
  total_datasets: 10
  valid_datasets: 9
  invalid_datasets: 1
  total_errors: 3
  total_warnings: 5
  success_rate: 0.9

Per-dataset results:
  ✅ VALID - book1.dataset.jsonl (errors: 0, warnings: 0)
  ✅ VALID - book2.dataset.jsonl (errors: 0, warnings: 1)
  ❌ INVALID - book3.dataset.jsonl (errors: 3, warnings: 2)
  ...
```

---

### Detailed Violations

```json
{
  "violations": [
    {
      "rule": "required_fields",
      "severity": "ERROR",
      "message": "Missing required fields: chapter_title",
      "context": {
        "card_index": 42,
        "segment_id": "00042",
        "page_num": 42
      },
      "missing_fields": ["chapter_title"]
    },
    {
      "rule": "text_quality_segment",
      "severity": "WARNING",
      "message": "segment too short (5 < 10)",
      "context": {
        "card_index": 156,
        "segment_id": "00156",
        "page_num": 156
      },
      "length": 5
    }
  ]
}
```

---

## 🎯 Best Practices

### 1. Validate Early and Often
```bash
# After each stage
python am_structural.py -i book.pdf
python validate.py -i data/datasets/structural/book.jsonl

python am_structure_detect.py -i data/datasets/structural/book.jsonl
python validate.py -i data/datasets/structured/book.jsonl
```

---

### 2. Use Strict Mode in CI/CD
```yaml
# In CI pipeline
- name: Validate datasets
  run: |
    python validate.py -d data/datasets/final
    # Exit code 1 if validation fails
```

---

### 3. Track Validation Over Time
```bash
# Save timestamped reports
DATE=$(date +%Y%m%d_%H%M%S)
python validate.py -d data/datasets/final \
  -o reports/validation_${DATE}.json
```

---

### 4. Integrate with Quality Tracker
```python
from validate import DatasetValidator
from tools.quality_tracker import QualityTracker

validator = DatasetValidator()
quality_tracker = QualityTracker()

result = validator.validate_dataset(dataset_path, stage)

# Track validation metrics
quality_tracker.track(stage, dataset_name, {
    'validation_valid': result['valid'],
    'validation_errors': result['error_count'],
    'validation_warnings': result['warning_count']
})
```

---

## 🔄 Exit Codes

| Code | Meaning |
|------|---------|
| 0 | All validations passed |
| 1 | Validation failed (errors found) |

**Usage in scripts:**
```bash
python validate.py -d data/datasets/final
if [ $? -eq 0 ]; then
    echo "Validation passed, proceeding..."
else
    echo "Validation failed, stopping pipeline"
    exit 1
fi
```

---

## 📚 See Also

- **am_common.py** - DatasetIO, validators
- **am_logging.py** - Logging integration
- **quality_tracker.py** - Quality metrics tracking
- **tests/test_basic.py** - Validation tests

---

**Version:** 2.0.0  
**Status:** ✅ Production Ready  
**Lines of Code:** ~700 lines  
**Created:** 2025-01-28
