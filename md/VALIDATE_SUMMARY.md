# 🎉 validate.py - Dataset Validation Tool

## 📦 Созданные файлы

1. **validate.py** (700 lines)
   - Comprehensive validation tool
   - Stage-specific validators
   - Custom validation rules
   - Report generation

2. **VALIDATE_GUIDE.md** (800 lines)
   - Complete user guide
   - CLI usage examples
   - Programmatic API
   - Common issues & fixes

3. **VALIDATE_EXAMPLES.py** (450 lines)
   - 10 practical examples
   - Custom rules
   - Pipeline integration
   - Test suite usage

---

## ✅ Key Features

### 1. **Stage-Specific Validation**

Validators for each pipeline stage:
- ✅ Structural (segment, page_num, text quality)
- ✅ Structured (chapters, sections)
- ✅ Extended (extended_fields, navigation)
- ✅ Final (complete validation)
- ✅ Chunks (size, tokens, metadata)

---

### 2. **Validation Rules**

Built-in rules:
- ✅ **Required Fields** - Check presence
- ✅ **Type Validation** - Check types
- ✅ **Range Validation** - Numeric ranges
- ✅ **Text Quality** - Length, encoding, whitespace
- ✅ **Extended Fields** - Structure validation

---

### 3. **Severity Levels**

- **ERROR** - Critical issues (dataset invalid)
- **WARNING** - Quality issues (dataset valid)
- **INFO** - Informational messages

---

### 4. **Report Generation**

```python
# Validate and generate report
validator = DatasetValidator()
validator.validate_directory(Path('data/datasets/final'))

# Print summary
validator.print_summary()

# Save detailed report
validator.save_report(Path('reports/validation.json'))
```

**Report includes:**
- Summary statistics
- Per-dataset results
- Violations by rule
- Violations by severity

---

## 🚀 Quick Start

### CLI Usage

```bash
# Validate single dataset
python validate.py -i data/datasets/final/book.dataset.jsonl

# Validate directory
python validate.py -d data/datasets/final

# Validate entire pipeline
python validate.py --pipeline accelerate

# Generate report
python validate.py -d data/datasets/final -o reports/validation.json
```

---

### Programmatic API

```python
from validate import DatasetValidator
from pathlib import Path

# Initialize
validator = DatasetValidator()

# Validate dataset
result = validator.validate_dataset(
    Path('data/datasets/final/book.dataset.jsonl'),
    stage='final'
)

# Check result
if result['valid']:
    print("✅ Valid")
else:
    print(f"❌ Invalid: {result['error_count']} errors")
```

---

## 📊 Validation Flow

```
Dataset File
     ↓
Load Dataset (DatasetIO)
     ↓
Apply Validation Rules:
  ├── Required Fields Rule
  ├── Type Validation Rule
  ├── Range Validation Rule
  ├── Text Quality Rule
  └── Extended Fields Rule
     ↓
Collect Violations
     ↓
Determine Validity:
  - ERROR violations → Invalid
  - WARNING only → Valid (with warnings)
  - No violations → Valid
     ↓
Generate Report:
  ├── Summary
  ├── Per-dataset results
  └── Violation details
```

---

## 🎯 Integration Points

### 1. **Pipeline Integration**

```python
# In run_mvp.py
from validate import DatasetValidator

validator = DatasetValidator()

def run_stage(stage_name, input_path):
    # Process
    output = process(stage_name, input_path)
    
    # Validate
    result = validator.validate_dataset(output, stage_name)
    
    if not result['valid']:
        logger.error(f"Validation failed: {result['error_count']} errors")
        if strict_mode:
            raise ValueError("Invalid dataset")
    
    return output
```

---

### 2. **Quality Tracker Integration**

```python
from validate import DatasetValidator
from tools.quality_tracker import QualityTracker

validator = DatasetValidator()
quality_tracker = QualityTracker()

# Validate
result = validator.validate_dataset(dataset_path, stage)

# Track metrics
quality_tracker.track(stage, dataset_name, {
    'validation_valid': result['valid'],
    'validation_errors': result['error_count'],
    'validation_warnings': result['warning_count']
})
```

---

### 3. **CI/CD Integration**

```yaml
# In .github/workflows/validate.yml
- name: Validate Datasets
  run: |
    python validate.py -d data/datasets/final
    # Exit code 1 if validation fails
```

---

### 4. **Test Suite Integration**

```python
import unittest
from validate import DatasetValidator

class TestDatasetQuality(unittest.TestCase):
    def test_output_valid(self):
        validator = DatasetValidator()
        result = validator.validate_dataset(
            Path('test_data/output.jsonl'),
            stage='final'
        )
        self.assertTrue(result['valid'])
```

---

## 📈 Validation Metrics

### What Gets Validated

**Schema:**
- Required fields present
- Correct data types
- Valid ranges

**Data Quality:**
- Text length (min/max)
- No encoding issues (null bytes)
- Reasonable whitespace ratio

**Stage-Specific:**
- Structural: extraction quality
- Structured: chapter/section structure
- Extended: extended_fields completeness
- Chunks: size and token counts

---

## 🛠️ Custom Validation Rules

### Create Custom Rule

```python
from validate import ValidationRule

class CustomRule(ValidationRule):
    def __init__(self):
        super().__init__("custom_rule", severity="WARNING")
    
    def validate(self, data, context=None):
        # Your logic
        if condition:
            self.add_violation("Issue found", context=context)
            return False
        return True
```

### Use Custom Validator

```python
from validate import StageValidator

class CustomValidator(StageValidator):
    def __init__(self):
        super().__init__('custom', {})
        self.add_rule(CustomRule())

# Validate
validator = CustomValidator()
result = validator.validate_dataset(dataset_path)
```

---

## 📊 Example Output

### Valid Dataset

```
============================================================
  Validating final: accelerate.dataset.jsonl
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

### Invalid Dataset

```
❌ INVALID - book.dataset.jsonl (3 errors, 2 warnings)

Violations:
  ERROR: Missing required fields: chapter_title
  ERROR: Invalid type for page_num: expected int, got str
  ERROR: segment too short (5 < 10)
  WARNING: extended_fields missing: content_type
  WARNING: text contains excessive whitespace (65%)
```

---

## 🎯 Best Practices

### 1. **Validate Early**
```bash
# After each stage
python am_structural.py -i book.pdf
python validate.py -i data/datasets/structural/book.jsonl ✓
```

---

### 2. **Use in CI/CD**
```bash
# In deployment pipeline
python validate.py -d data/datasets/final || exit 1
```

---

### 3. **Track Over Time**
```bash
# Timestamped reports
DATE=$(date +%Y%m%d)
python validate.py -d data/datasets/final -o reports/val_${DATE}.json
```

---

### 4. **Integrate with Quality Metrics**
```python
# Combine validation + quality tracking
validator.validate_dataset(dataset_path, stage)
quality_tracker.track(stage, dataset, metrics)
```

---

## 📚 Comparison

| Feature | Manual Checks | validate.py |
|---------|---------------|-------------|
| **Speed** | Slow (manual) | Fast (automated) |
| **Coverage** | Partial | Comprehensive |
| **Consistency** | Variable | Always same |
| **Reporting** | Manual | Automatic |
| **CI/CD** | Hard | Easy |
| **Tracking** | Manual | Built-in |

---

## 🎉 Benefits

### For Development:
- ✅ Catch issues early
- ✅ Faster debugging
- ✅ Consistent quality
- ✅ Less manual work

### For Production:
- ✅ Automated quality gates
- ✅ Comprehensive reports
- ✅ Tracking over time
- ✅ CI/CD integration

### For Team:
- ✅ Shared standards
- ✅ Clear expectations
- ✅ Objective metrics
- ✅ Better collaboration

---

## 📊 Statistics

**Created:**
- ✅ validate.py (700 lines)
- ✅ VALIDATE_GUIDE.md (800 lines)
- ✅ VALIDATE_EXAMPLES.py (450 lines)
- ✅ Total: ~1950 lines

**Features:**
- ✅ 5 stage validators
- ✅ 5 built-in rules
- ✅ Custom rule support
- ✅ Report generation
- ✅ CLI + API
- ✅ 10 practical examples

**Test Coverage:**
- Structural validation ✅
- Structured validation ✅
- Extended validation ✅
- Chunks validation ✅
- Custom rules ✅

---

## 🎯 Next Steps

### Immediate:
1. ✅ Place validate.py in tools/
2. ✅ Add to requirements.txt
3. ✅ Test on sample datasets
4. ✅ Integrate into run_mvp.py

### Short-term:
1. Add more stage-specific rules
2. Create validation dashboard
3. Add performance metrics
4. Enhance reporting

### Long-term:
1. ML-based validation
2. Auto-fix common issues
3. Real-time monitoring
4. Webhook alerts

---

## 🎉 Summary

**validate.py** provides:
- ✅ Comprehensive validation
- ✅ Easy to use (CLI + API)
- ✅ Extensible (custom rules)
- ✅ Production-ready
- ✅ Well-documented
- ✅ Integration-friendly

**Status:** ✅ Production Ready  
**Version:** 2.0.0  
**Lines:** ~1950 lines (code + docs)  
**Created:** 2025-01-28

---

**Recommendation:** Integrate validate.py into pipeline for automated quality assurance!
