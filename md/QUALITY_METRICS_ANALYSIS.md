# 📊 Quality Metrics for MVP - Lightweight Implementation

## ❓ Вопрос: Стоит ли добавлять quality metrics в MVP v2.0?

**Короткий ответ:** ДА! Это легковесно и критично полезно.

---

## 🎯 Lightweight Quality Metrics (БЕЗ дашборда)

### Что ВКЛЮЧАЕМ в MVP:
✅ Сбор метрик на каждом этапе
✅ Запись в JSON файлы
✅ Простые пороги (thresholds)
✅ Warnings в логи
✅ Summary report в конце

### Что НЕ включаем (Post-MVP):
❌ Grafana/Prometheus
❌ Web dashboard
❌ Real-time monitoring
❌ Alerts в Slack/Email
❌ Temporal graphs

---

## 💡 Концепция: Simple File-Based Metrics

```
data/quality/
├── structural_quality.json           # Metrics после structural
├── structure_detect_quality.json     # Metrics после structure_detect
├── summarize_quality.json            # Metrics после summarize
├── extended_quality.json             # Metrics после extended
├── finalize_quality.json             # Metrics после finalize
├── chunk_quality.json                # Metrics после chunk
├── embed_quality.json                # Metrics после embed
└── pipeline_summary.json             # Overall summary
```

**Формат:**
```json
{
  "stage": "structural",
  "timestamp": "2025-01-28T12:00:00Z",
  "file": "accelerate.pdf",
  "metrics": {
    "total_pages": 257,
    "empty_pages": 5,
    "empty_pages_ratio": 0.019,
    "avg_chars_per_page": 2450,
    "ocr_used_pages": 12,
    "ocr_avg_confidence": 0.89,
    "tables_detected": 47,
    "images_detected": 23,
    "unicode_errors": 3
  },
  "quality_score": 9.2,
  "warnings": [
    "OCR confidence below 0.9 on 3 pages"
  ],
  "status": "OK"
}
```

---

## 📈 Метрики по этапам

### Stage 1: Structural
```python
metrics = {
    "total_pages": len(pages),
    "empty_pages": count_empty,
    "empty_pages_ratio": count_empty / total,
    "avg_chars_per_page": sum(lens) / total,
    "min_chars_per_page": min(lens),
    "max_chars_per_page": max(lens),
    
    # OCR
    "ocr_used_pages": ocr_count,
    "ocr_avg_confidence": avg_confidence,
    "ocr_low_confidence_pages": low_conf_count,
    
    # Tables
    "tables_detected": table_count,
    "pages_with_tables": pages_with_tables,
    
    # Images
    "images_detected": image_count,
    "pages_with_images": pages_with_images,
    
    # Errors
    "unicode_errors": unicode_err_count,
    "pdf_read_errors": read_errors,
}

# Thresholds
warnings = []
if metrics["empty_pages_ratio"] > 0.1:
    warnings.append("High empty pages ratio (>10%)")
if metrics["ocr_avg_confidence"] < 0.8:
    warnings.append("Low OCR confidence (<80%)")
if metrics["unicode_errors"] > 50:
    warnings.append("Many unicode errors (>50)")
```

### Stage 2: Structure Detection
```python
metrics = {
    "total_pages": len(cards),
    "chapters_detected": len(chapters),
    "sections_detected": len(sections),
    "pages_with_structure": structured_count,
    "structure_coverage": structured_count / total,
    
    "chapter_detection_method": {
        "regex": regex_count,
        "heuristic": heuristic_count
    },
    
    "avg_chapter_length": avg_chapter_pages,
    "toc_entries": len(toc),
}

warnings = []
if metrics["structure_coverage"] < 0.7:
    warnings.append("Low structure coverage (<70%)")
if metrics["chapters_detected"] == 0:
    warnings.append("No chapters detected!")
```

### Stage 3: Summarize
```python
metrics = {
    "total_pages": len(cards),
    "summarized_pages": summarized_count,
    "summary_coverage": summarized_count / total,
    "skipped_pages": skipped_count,
    
    "avg_l1_length": avg_l1_chars,
    "avg_l2_length": avg_l2_chars,
    "avg_compression_ratio": avg(original_len / summary_len),
    
    "engine": "extractive",
    "processing_time": time_seconds,
}

warnings = []
if metrics["summary_coverage"] < 0.9:
    warnings.append("Summary coverage <90%")
if metrics["avg_l1_length"] < 50:
    warnings.append("L1 summaries too short")
```

### Stage 4: Extended
```python
metrics = {
    "total_pages": len(cards),
    "merged_pages": merged_count,
    "merge_ratio": merged_count / total,
    
    "duplicates_found": dup_count,
    "duplicate_ratio": dup_count / total,
    
    "continuity_gaps": gap_count,
    "avg_continuity_score": avg_score,
    
    "extended_fields_coverage": fields_count / total,
    "metrics_extracted": metrics_count,
    "frameworks_extracted": frameworks_count,
}

warnings = []
if metrics["duplicate_ratio"] > 0.2:
    warnings.append("High duplicate ratio (>20%)")
if metrics["continuity_gaps"] > total * 0.1:
    warnings.append("Many continuity gaps (>10%)")
```

### Stage 5: Chunk
```python
metrics = {
    "total_chunks": len(chunks),
    "chunks_per_page": len(chunks) / pages,
    
    "avg_chunk_tokens": avg_tokens,
    "min_chunk_tokens": min_tokens,
    "max_chunk_tokens": max_tokens,
    
    "chunks_with_tables": table_chunks,
    "chunks_with_code": code_chunks,
    
    "context_completeness": chunks_with_context / total,
    
    "token_distribution": {
        "0-100": count_0_100,
        "100-300": count_100_300,
        "300-512": count_300_512,
        "512+": count_512_plus
    }
}

warnings = []
if metrics["avg_chunk_tokens"] < 100:
    warnings.append("Chunks too small")
if metrics["avg_chunk_tokens"] > 600:
    warnings.append("Chunks too large")
if metrics["context_completeness"] < 0.95:
    warnings.append("Missing context in some chunks")
```

### Stage 6: Embed
```python
metrics = {
    "total_vectors": len(vectors),
    "embedding_dim": dim,
    "model": model_name,
    
    "embedding_failures": fail_count,
    "avg_embedding_time": avg_time,
    "total_time": total_seconds,
    
    "index_size_mb": index_size / 1024 / 1024,
    "metadata_size_mb": meta_size / 1024 / 1024,
}

warnings = []
if metrics["embedding_failures"] > 0:
    warnings.append(f"{fail_count} embeddings failed!")
```

---

## 💻 Implementation (ОЧЕНЬ простая)

### 1. QualityTracker Class (~100 lines)

```python
# tools/quality_tracker.py

import json
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime, timezone

class QualityTracker:
    """
    Simple file-based quality metrics tracker.
    No database, no dashboard - just JSON files + logs.
    """
    
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def track(self, 
              stage: str,
              file_name: str, 
              metrics: Dict[str, Any],
              thresholds: Dict[str, float] = None) -> Dict[str, Any]:
        """
        Track metrics for a pipeline stage.
        
        Args:
            stage: Pipeline stage name
            file_name: Source file name
            metrics: Dictionary of metrics
            thresholds: Optional thresholds for warnings
        
        Returns:
            Quality report with warnings
        """
        # Calculate quality score (0-10)
        quality_score = self._calculate_score(metrics, thresholds or {})
        
        # Check thresholds
        warnings = self._check_thresholds(metrics, thresholds or {})
        
        # Determine status
        status = "ERROR" if quality_score < 5 else "WARNING" if warnings else "OK"
        
        # Build report
        report = {
            "stage": stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "file": file_name,
            "metrics": metrics,
            "quality_score": round(quality_score, 1),
            "warnings": warnings,
            "status": status
        }
        
        # Save to file
        output_path = self.output_dir / f"{stage}_quality.json"
        self._append_to_file(output_path, report)
        
        # Log warnings
        if warnings:
            logger = logging.getLogger(f"quality.{stage}")
            for warning in warnings:
                logger.warning(f"[{file_name}] {warning}")
        
        return report
    
    def _calculate_score(self, metrics: Dict, thresholds: Dict) -> float:
        """Simple quality score calculation (0-10)."""
        score = 10.0
        
        # Deduct points for bad metrics
        for key, threshold in thresholds.items():
            value = metrics.get(key)
            if value is None:
                continue
            
            if key.endswith("_ratio") or key.endswith("_coverage"):
                # Higher is better
                if value < threshold:
                    score -= (threshold - value) * 10
            else:
                # Lower is better (e.g., errors)
                if value > threshold:
                    score -= min((value - threshold) / threshold, 5)
        
        return max(0.0, min(10.0, score))
    
    def _check_thresholds(self, metrics: Dict, thresholds: Dict) -> List[str]:
        """Check metrics against thresholds."""
        warnings = []
        
        for key, threshold in thresholds.items():
            value = metrics.get(key)
            if value is None:
                continue
            
            if key.endswith("_ratio") or key.endswith("_coverage"):
                # Higher is better
                if value < threshold:
                    warnings.append(f"{key} below threshold ({value:.2f} < {threshold})")
            else:
                # Lower is better
                if value > threshold:
                    warnings.append(f"{key} above threshold ({value} > {threshold})")
        
        return warnings
    
    def _append_to_file(self, path: Path, report: Dict):
        """Append report to JSONL file."""
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(report, ensure_ascii=False) + "\n")
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate overall pipeline summary."""
        all_reports = []
        
        for stage_file in self.output_dir.glob("*_quality.json"):
            with open(stage_file) as f:
                for line in f:
                    all_reports.append(json.loads(line))
        
        if not all_reports:
            return {"error": "No reports found"}
        
        # Aggregate
        summary = {
            "total_files": len(set(r["file"] for r in all_reports)),
            "stages_completed": len(set(r["stage"] for r in all_reports)),
            "avg_quality_score": sum(r["quality_score"] for r in all_reports) / len(all_reports),
            "total_warnings": sum(len(r["warnings"]) for r in all_reports),
            "error_count": sum(1 for r in all_reports if r["status"] == "ERROR"),
            "by_stage": {}
        }
        
        for stage in set(r["stage"] for r in all_reports):
            stage_reports = [r for r in all_reports if r["stage"] == stage]
            summary["by_stage"][stage] = {
                "avg_score": sum(r["quality_score"] for r in stage_reports) / len(stage_reports),
                "warnings": sum(len(r["warnings"]) for r in stage_reports),
                "status_ok": sum(1 for r in stage_reports if r["status"] == "OK")
            }
        
        # Save summary
        summary_path = self.output_dir / "pipeline_summary.json"
        summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
        
        return summary
```

### 2. Usage in Pipeline (~5 lines per stage)

```python
# pipeline/am_structural.py

from tools.quality_tracker import QualityTracker

def process_pdf(pdf_path: Path, config: Dict):
    # ... existing code ...
    
    # Track quality (добавляем в конце)
    tracker = QualityTracker(Path("data/quality"))
    
    metrics = {
        "total_pages": len(pages),
        "empty_pages": sum(1 for p in pages if len(p.strip()) < 50),
        "avg_chars_per_page": sum(len(p) for p in pages) / len(pages),
        "ocr_used_pages": ocr_count,
        "tables_detected": table_count,
    }
    
    thresholds = {
        "empty_pages": 25,        # Max 25 empty pages
        "avg_chars_per_page": 500,  # Min 500 chars
    }
    
    report = tracker.track("structural", pdf_path.name, metrics, thresholds)
    
    if report["status"] == "ERROR":
        logger.error(f"Quality check failed: {report['warnings']}")
    
    # ... continue ...
```

### 3. Summary Report at End

```python
# run_mvp.py

def main():
    # ... run pipeline ...
    
    # Generate quality summary
    tracker = QualityTracker(Path("data/quality"))
    summary = tracker.generate_summary()
    
    print("\n" + "="*60)
    print("QUALITY SUMMARY")
    print("="*60)
    print(f"Files processed: {summary['total_files']}")
    print(f"Average quality score: {summary['avg_quality_score']:.1f}/10")
    print(f"Total warnings: {summary['total_warnings']}")
    print(f"Errors: {summary['error_count']}")
    print("\nBy Stage:")
    for stage, data in summary['by_stage'].items():
        print(f"  {stage}: {data['avg_score']:.1f}/10 ({data['warnings']} warnings)")
    print("="*60)
```

---

## 📊 Что получаем

### Во время работы:
```
[INFO] Processing accelerate.pdf...
[INFO] Structural extraction complete
[WARNING] [accelerate.pdf] Low OCR confidence (<80%)
[WARNING] [accelerate.pdf] High empty pages ratio (>10%)
[INFO] Quality score: 7.2/10
```

### После обработки:
```
data/quality/
├── structural_quality.json        # 1 строка на файл
├── structure_detect_quality.json
├── summarize_quality.json
├── extended_quality.json
├── finalize_quality.json
├── chunk_quality.json
├── embed_quality.json
└── pipeline_summary.json          # Overall summary

QUALITY SUMMARY
============================================================
Files processed: 5
Average quality score: 8.7/10
Total warnings: 12
Errors: 0

By Stage:
  structural: 8.9/10 (3 warnings)
  structure_detect: 8.2/10 (5 warnings)
  summarize: 9.1/10 (1 warnings)
  extended: 8.5/10 (2 warnings)
  chunk: 9.0/10 (1 warnings)
  embed: 9.5/10 (0 warnings)
============================================================
```

---

## ⏱️ Effort Estimation

### Добавление в MVP:

**Implementation:**
- `tools/quality_tracker.py`: **1-2 hours**
- Integration в 6 pipeline stages: **3-4 hours** (по 30-40 мин на stage)
- Thresholds configuration: **30 min**
- Testing: **1-2 hours**

**Total: ~0.5-1 день** (4-8 часов)

**Complexity:** ⭐⭐ (2/10) - Очень простая имплементация

---

## ✅ Benefits vs Cost

### Benefits (ОГРОМНЫЕ):
1. ✅ **Instant feedback** - видим проблемы сразу
2. ✅ **Debug faster** - понятно где именно сломалось
3. ✅ **Validate quality** - уверенность что всё работает правильно
4. ✅ **Compare configs** - A/B тест параметров
5. ✅ **Track improvements** - видим прогресс
6. ✅ **Production readiness** - уже есть метрики для monitoring

### Cost (МИНИМАЛЬНЫЙ):
- ❌ Добавляет ~0.5-1 день к MVP
- ❌ ~150 lines of code
- ❌ Negligible performance overhead (<1%)
- ❌ Simple JSON files (no database)

### ROI: 🌟🌟🌟🌟🌟 (Excellent!)

---

## 🎯 Recommendation

### ✅ **ВКЛЮЧИТЬ в MVP v2.0**

**Почему:**
1. Очень простая реализация (~0.5-1 день)
2. Огромная польза для отладки и валидации
3. Не утяжеляет архитектуру (простые JSON файлы)
4. Будет использоваться постоянно в разработке
5. Готова база для Post-MVP dashboard

**Updated MVP Timeline:**
- **Original:** 10-12 дней
- **With lightweight metrics:** 10.5-13 дней (+0.5-1 день)

**Impact:** Минимальный (+4-8%)  
**Value:** Максимальный

---

## 📋 Updated Implementation Plan

### Day 8.5: Quality Metrics (NEW!)

**Morning:**
- [ ] Implement `tools/quality_tracker.py` (2 hours)
- [ ] Define thresholds per stage (30 min)

**Afternoon:**
- [ ] Integrate into am_structural.py (30 min)
- [ ] Integrate into am_structure_detect.py (30 min)
- [ ] Integrate into am_summarize.py (30 min)
- [ ] Integrate into am_extended.py (30 min)
- [ ] Integrate into am_chunk.py (30 min)
- [ ] Integrate into am_embed.py (30 min)
- [ ] Test & fix (1 hour)

**Total: 0.5-1 день**

---

## 💡 Conclusion

**Lightweight quality metrics БЕЗ дашборда** - это:
- ✅ Легко реализовать
- ✅ Критично полезно
- ✅ Не утяжеляет MVP
- ✅ Используется постоянно

**Рекомендация:** ДОБАВИТЬ В MVP v2.0

---

**Version:** 1.0  
**Created:** 2025-01-28
