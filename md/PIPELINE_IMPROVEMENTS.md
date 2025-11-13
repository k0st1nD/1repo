# 🚀 Archivist Magika - Pipeline Improvements

Критический анализ текущего pipeline и предложения по улучшению.

---

## 📊 Текущий Pipeline (v1.1)

```
PDF → structural → summarize → extended → finalize → chunk → embed → search
```

**Проблемы:**
1. ❌ Нет реальной детекции структуры (главы, секции)
2. ❌ Таблицы только детектируются, но не извлекаются
3. ❌ OCR не поддерживается (сканированные PDF не работают)
4. ❌ Нет метрик качества на каждом этапе
5. ❌ Chunks "плоские" - нет иерархии
6. ❌ Нет дедупликации (могут быть дубли)
7. ❌ Метаданные PDF не используются

---

## 🎯 Категория A: Критичные для Production

### 1. **Детекция структуры документа** ⭐⭐⭐

**Проблема:** Сейчас просто "page/42", нет понимания глав/секций.

**Решение:** Новый модуль `am_structure_detect.py` между structural и summarize

```yaml
# am_config.yaml
structure_detection:
  enabled: true
  
  # Детекция глав
  chapters:
    patterns:
      - regex: "^CHAPTER\\s+(\\d+|[IVX]+)[:\\s](.+)"
        level: 1
      - regex: "^Chapter\\s+(\\d+)[:\\s](.+)"
        level: 1
      - regex: "^PART\\s+([IVX]+)[:\\s](.+)"
        level: 0
    
    # Эвристики
    heuristics:
      font_size_change: true      # Большой шрифт = заголовок
      all_caps: true              # ЗАГЛАВНЫЕ = заголовок
      short_line: true            # Короткая строка в начале страницы
      followed_by_empty: true     # После заголовка пустая строка
  
  # Детекция секций
  sections:
    patterns:
      - regex: "^\\d+\\.\\d+\\s+(.+)"  # 5.1 Introduction
        level: 2
      - regex: "^[A-Z][a-z]+(?:\\s+[A-Z][a-z]+)*$"  # Title Case
        level: 2
    
    heuristics:
      numbered: true              # 5.1, 5.2 etc
      bold_text: true             # Жирный текст
  
  # Output
  add_to_cards: true              # Добавить structure к каждой карте
  update_section_path: true       # Обновить section_path
  create_toc: true                # Создать TOC в __header__
```

**Результат в карте:**
```json
{
  "segment_id": "00042",
  "section_path": "part/1/chapter/5/section/5.1",
  "structure": {
    "part": "Part I: Foundations",
    "chapter": "Chapter 5: Architecture",
    "section": "5.1 Loosely Coupled Architecture",
    "level": 2
  },
  "segment": "..."
}
```

**Зачем:**
- ✅ Chunks получают правильный контекст `[CHAPTER: 5 | SECTION: 5.1]`
- ✅ Можно фильтровать поиск по главам/секциям
- ✅ Можно собрать автоматическое оглавление

---

### 2. **Извлечение таблиц** ⭐⭐⭐

**Проблема:** Сейчас только `flags.has_vector_table`, сама таблица не извлечена.

**Решение:** Улучшить `am_structural.py` или добавить `am_table_extract.py`

```yaml
table_extraction:
  enabled: true
  methods:
    - "pdfplumber"              # Лучше для таблиц чем pdfminer
    - "camelot"                 # Если нужна высокая точность
  
  # Конфигурация
  min_rows: 2
  min_cols: 2
  detect_headers: true
  export_format: "markdown"     # "markdown" | "json" | "csv"
  
  # Где хранить
  storage: "inline"             # "inline" (в segment) | "separate" (отдельный файл)
```

**Результат в карте:**
```json
{
  "segment_id": "00042",
  "segment": "Table 5.1 shows deployment metrics...",
  "tables": [
    {
      "table_id": "table_00042_1",
      "caption": "Table 5.1: Deployment Metrics",
      "format": "markdown",
      "data": "| Category | Deploys/day |\n|----------|-------------|\n| High     | 200+        |\n| Medium   | 1-7/week    |\n| Low      | 1/month     |",
      "rows": 3,
      "cols": 2,
      "position": {"page": 42, "bbox": [100, 200, 400, 350]}
    }
  ]
}
```

**Зачем:**
- ✅ Таблицы можно индексировать отдельно
- ✅ LLM может работать со структурированными данными
- ✅ Можно генерировать SQL-like запросы к таблицам

---

### 3. **Quality Metrics & Monitoring** ⭐⭐⭐

**Проблема:** Не знаем где проблемы качества, пока не посмотрим вручную.

**Решение:** Новый модуль `am_quality.py` - запускается после каждого этапа

```yaml
quality_metrics:
  enabled: true
  
  # Метрики по этапам
  structural:
    - empty_pages_ratio          # % пустых страниц
    - avg_chars_per_page
    - unicode_errors_count
    - encoding_issues_count
  
  summarize:
    - summary_coverage           # % страниц с L1
    - avg_summary_length
    - summary_quality_score      # Heuristic: не слишком короткие/длинные
  
  extended:
    - merge_ratio                # % merged pages
    - continuity_gaps_ratio
    - extended_fields_coverage   # % страниц с extracted fields
  
  chunks:
    - avg_chunk_size
    - chunks_per_page
    - token_distribution         # Histogram
    - context_completeness       # % chunks с полным контекстом
  
  embed:
    - embedding_failures
    - vector_dimension_check
    - index_integrity
  
  # Thresholds для алертов
  alerts:
    empty_pages_ratio: 0.1       # Если >10% пустых - WARNING
    unicode_errors_count: 50     # Если >50 ошибок - WARNING
    summary_coverage: 0.9        # Если <90% покрытие - WARNING
  
  # Output
  report_path: "data/quality/quality_report.json"
  per_file_reports: true
```

**Output:**
```json
{
  "file": "accelerate.pdf",
  "pipeline_version": "v4.3.8",
  "stages": {
    "structural": {
      "status": "OK",
      "metrics": {
        "empty_pages_ratio": 0.03,
        "avg_chars_per_page": 2450,
        "unicode_errors_count": 12
      },
      "alerts": []
    },
    "summarize": {
      "status": "WARNING",
      "metrics": {
        "summary_coverage": 0.87
      },
      "alerts": ["summary_coverage below threshold (0.87 < 0.9)"]
    }
  },
  "overall_quality_score": 8.5
}
```

**Зачем:**
- ✅ Видим проблемы сразу
- ✅ Можем улучшать параметры на основе метрик
- ✅ Production monitoring

---

### 4. **OCR Support** ⭐⭐

**Проблема:** Сканированные PDF не работают (нет текстового слоя).

**Решение:** Добавить OCR fallback в `am_structural.py`

```yaml
structural:
  ocr:
    enabled: true
    trigger: "auto"              # "auto" | "always" | "never"
    threshold_chars: 50          # Если <50 chars → включить OCR
    
    engine: "tesseract"          # "tesseract" | "easyocr" | "paddleocr"
    languages: ["eng", "rus"]
    
    # Качество
    preprocess: true             # Улучшить изображение перед OCR
    deskew: true                 # Выровнять перекошенный текст
    denoise: true                # Убрать шум
    
    # Performance
    parallel: true
    dpi: 300                     # DPI для конвертации PDF→Image
```

**Результат в карте:**
```json
{
  "segment_id": "00042",
  "segment": "Extracted text via OCR...",
  "flags": {
    "ocr_used": true,
    "ocr_confidence": 0.92
  }
}
```

**Зачем:**
- ✅ Работает со сканами
- ✅ Старые книги доступны
- ✅ Больше охват

---

## 🎯 Категория B: Желательные (сильно улучшат качество)

### 5. **Entity Extraction (NER)** ⭐⭐

**Проблема:** Нет автоматической детекции компаний, людей, технологий.

**Решение:** Добавить в `am_extended.py` или новый `am_entities.py`

```yaml
entity_extraction:
  enabled: true
  
  # NER модель
  model: "en_core_web_sm"        # spaCy model
  custom_entities:
    - type: "COMPANY"
      patterns: ["Google", "Amazon", "Netflix", "ING", "Capital One"]
    - type: "TECHNOLOGY"
      patterns: ["Kubernetes", "Docker", "Jenkins", "AWS"]
    - type: "METRIC"
      patterns: ["deployment frequency", "lead time", "MTTR"]
  
  # Output
  add_to_extended_fields: true
  create_entity_index: true      # Отдельный индекс сущностей
```

**Результат:**
```json
{
  "segment_id": "00042",
  "entities": {
    "companies": ["ING", "Google"],
    "technologies": ["Kubernetes", "microservices"],
    "people": ["Gene Kim", "Jez Humble"],
    "metrics": ["deployment frequency", "lead time"]
  }
}
```

**Зачем:**
- ✅ Фильтр: "найди все про ING"
- ✅ Фильтр: "найди все про Kubernetes"
- ✅ Автоматические связи между книгами

---

### 6. **Hierarchical Chunking** ⭐⭐

**Проблема:** Chunks одного размера - нет гибкости.

**Решение:** Создавать chunks разных уровней детализации

```yaml
chunking:
  hierarchical:
    enabled: true
    
    levels:
      # Level 1: Крупные (целые главы/секции)
      - name: "section"
        size_tokens: 2000
        overlap: 100
        boundary: "section"
      
      # Level 2: Средние (текущий подход)
      - name: "paragraph"
        size_tokens: 512
        overlap: 50
        boundary: "paragraph"
      
      # Level 3: Мелкие (предложения)
      - name: "sentence"
        size_tokens: 128
        overlap: 20
        boundary: "sentence"
    
    # Связи между уровнями
    link_levels: true              # Chunk L2 знает свой parent L1
```

**Результат:**
```json
{
  "chunk_id": "accelerate_ch5_sect5.1_para2",
  "level": "paragraph",
  "text": "...",
  "parent_chunk": "accelerate_ch5_sect5.1",
  "child_chunks": [
    "accelerate_ch5_sect5.1_para2_sent1",
    "accelerate_ch5_sect5.1_para2_sent2"
  ]
}
```

**Зачем:**
- ✅ Можно получить разный уровень детализации
- ✅ Query: summary? → L1 chunks. Details? → L3 chunks.
- ✅ Better reranking

---

### 7. **Deduplication** ⭐⭐

**Проблема:** Могут быть дубли страниц (оглавление повторяется, appendix дублируется).

**Решение:** Добавить в `am_extended.py`

```yaml
deduplication:
  enabled: true
  
  methods:
    - "exact"                    # Точное совпадение текста
    - "fuzzy"                    # Похожий текст (>95% overlap)
    - "semantic"                 # Семантически идентичные
  
  threshold: 0.95                # Для fuzzy/semantic
  action: "mark"                 # "mark" | "remove" | "merge"
  
  # Что делать с дублями
  mark_as_duplicate: true        # Флаг в карте
  keep_first: true               # Оставлять первый экземпляр
```

**Результат:**
```json
{
  "segment_id": "00245",
  "segment": "Appendix A: ...",
  "flags": {
    "duplicate_of": "00015"
  }
}
```

---

### 8. **PDF Metadata Extraction** ⭐

**Проблема:** Не используем метаданные из PDF (автор, год, ISBN).

**Решение:** Улучшить `am_structural.py`

```yaml
structural:
  extract_metadata:
    enabled: true
    
    fields:
      - "title"
      - "author"
      - "subject"
      - "keywords"
      - "creator"
      - "producer"
      - "creation_date"
      - "modification_date"
    
    # Попытка извлечь из первой страницы
    fallback_from_first_page: true
    
    # Внешние источники
    external_lookup:
      enabled: false
      sources: ["openlibrary", "google_books"]
```

**Результат в header:**
```json
{
  "segment_id": "__header__",
  "source": {
    "title": "Accelerate",
    "author": "Nicole Forsgren, Jez Humble, Gene Kim",
    "year": 2018,
    "publisher": "IT Revolution Press",
    "isbn": "978-1942788331",
    "pages": 257
  }
}
```

---

## 🎯 Категория C: Nice-to-Have (опционально)

### 9. **Code Block Detection & Extraction**

```yaml
code_extraction:
  enabled: true
  languages: ["python", "javascript", "sql", "yaml", "bash"]
  preserve_formatting: true
  syntax_highlight: false        # Для MVP
```

### 10. **Math Formula Handling**

```yaml
math_extraction:
  enabled: false                 # MVP: skip
  format: "latex"                # "latex" | "mathml"
```

### 11. **Cross-Document Linking**

```yaml
cross_document:
  enabled: false                 # MVP: skip
  detect_references: true        # "See Chapter 3 in Book X"
  create_graph: true             # Knowledge graph
```

### 12. **Incremental Processing**

```yaml
incremental:
  enabled: false                 # MVP: always full reprocess
  cache_unchanged: true
  detect_changes: "hash"         # Compare PDF hash
```

---

## 📋 Рекомендуемый порядок внедрения

### MVP (текущий scope):
```
✅ structural → summarize → extended → finalize → chunk → embed → search
```

### MVP+ (добавить в течение 2-3 недель):
```
✅ + structure_detection    # Главы/секции
✅ + table_extraction       # Извлечение таблиц
✅ + quality_metrics        # Мониторинг качества
```

### Production (1-2 месяца):
```
✅ + ocr_support            # Сканированные PDF
✅ + entity_extraction      # NER
✅ + hierarchical_chunking  # Разные уровни детализации
✅ + deduplication          # Удаление дублей
✅ + pdf_metadata          # Извлечение метаданных
```

### Advanced (опционально):
```
⬜ code_extraction
⬜ math_formulas
⬜ cross_document_linking
⬜ incremental_processing
```

---

## 🎯 Итоговая улучшенная архитектура

```
PDF
 ↓
[structural] → per-page extraction + OCR fallback + metadata + tables
 ↓
[structure_detect] → chapters/sections detection + TOC
 ↓
[summarize] → L1/L2 summaries
 ↓
[extended] → merge + continuity + extended_fields + entities + dedup
 ↓
[quality_check] → metrics + alerts
 ↓
[finalize] → validation + policies
 ↓
[chunk] → hierarchical chunking с контекстом
 ↓
[embed] → FAISS + metadata
 ↓
[search] → semantic search с фильтрами
```

---

## 💡 Главный вывод

**Для MVP:** текущий pipeline достаточен.

**Для Production:** критично добавить:
1. **structure_detection** - без этого контекст chunks плохой
2. **table_extraction** - технические книги полны таблиц
3. **quality_metrics** - без этого не знаем где проблемы

Остальное можно добавлять итеративно по мере необходимости.

---

**Версия:** 1.0  
**Дата:** 2025-01-28
