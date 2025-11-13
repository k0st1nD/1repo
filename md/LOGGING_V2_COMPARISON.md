# 📊 am_logging.py - Сравнение v1.0 → v2.0

## 🔄 Что изменилось

### ✅ Добавлено в v2.0

| Feature | Описание | Польза |
|---------|----------|--------|
| **Structured Logging** | JSON логи с метаданными | Машинная обработка, анализ |
| **Performance Tracking** | Автоматический timing функций | Оптимизация bottlenecks |
| **Context Managers** | `log_operation()` для операций | Чистый код, автотайминг |
| **Error Aggregation** | Сбор ошибок по стадиям | Лучшая отладка |
| **Progress Bar Integration** | Работа с tqdm | Визуальный feedback |
| **Stage Logging** | `log_stage()` с emoji | Читаемость pipeline |
| **Metrics Logging** | `log_metrics()` | Структурированный вывод |
| **Performance Summary** | Итоговая статистика | Видно узкие места |
| **Error Summary** | Итоговый отчёт по ошибкам | Debugging |
| **Decorators** | `@log_performance` | Простая интеграция |

### 🔧 Улучшено

| Feature | v1.0 | v2.0 |
|---------|------|------|
| **Форматирование** | Базовое | + ColoredFormatter с компонентами |
| **Файловые логи** | Один файл | + Отдельный JSON для анализа |
| **Конфигурация** | Простая | + Детальная с scenarios |
| **Утилиты** | 2 функции | + 10 функций |
| **Handlers** | Standard | + TqdmLoggingHandler |

---

## 📝 Примеры использования

### v1.0 (старый способ)

```python
from am_logging import setup_logging, get_logger

logger = setup_logging(level="INFO", log_file=Path("logs/test.log"))

def process_page(page_num):
    logger.info(f"Processing page {page_num}")
    # ... code ...
    logger.info(f"Page {page_num} done")
```

**Проблемы:**
- ❌ Нет автоматического timing
- ❌ Нет aggregation ошибок
- ❌ Нет structured логов
- ❌ Много manual logging

---

### v2.0 (новый способ)

```python
from am_logging import (
    setup_logging,
    get_logger,
    log_operation,
    log_performance,
    create_progress_bar
)

logger = setup_logging(
    level="INFO",
    log_file=Path("logs/test.log"),
    structured_file=Path("logs/test.json")  # NEW
)

@log_performance('process_page')  # NEW - автотайминг
def process_page(page_num):
    # Функция автоматически tracked
    # ... code ...
    pass

def process_dataset(pages):
    # Context manager для операции
    with log_operation(logger, "process_dataset", total_pages=len(pages)):
        
        # Progress bar
        for page in create_progress_bar(pages, desc="Processing"):
            process_page(page)
```

**Преимущества:**
- ✅ Автоматический timing
- ✅ Структурированные метаданные
- ✅ Progress bar integration
- ✅ Меньше boilerplate кода

---

## 🎯 Ключевые улучшения для Pipeline

### 1. Performance Tracking

**До v2.0:**
```python
import time

start = time.time()
result = process_something()
duration = time.time() - start
logger.info(f"Took {duration:.2f}s")
```

**После v2.0:**
```python
@log_performance('process_something')
def process_something():
    # Автоматически tracked!
    pass

# В конце pipeline:
log_performance_summary(logger)
# Выведет статистику по всем операциям
```

---

### 2. Error Aggregation

**До v2.0:**
```python
errors = []
for page in pages:
    try:
        process(page)
    except Exception as e:
        logger.error(f"Failed page {page}: {e}")
        errors.append((page, str(e)))

# Manual reporting
logger.info(f"Total errors: {len(errors)}")
```

**После v2.0:**
```python
from am_logging import get_error_aggregator

aggregator = get_error_aggregator()

for page in pages:
    try:
        process(page)
    except Exception as e:
        aggregator.add_error('structural', f"Failed page {page}", 
                            page=page, error=str(e))

# Автоматический отчёт
log_error_summary(logger)
```

---

### 3. Structured Logging

**До v2.0:**
```python
logger.info(f"Processed page {page_num}, found {table_count} tables")
# → "2025-01-28 14:30:00 - INFO - Processed page 42, found 3 tables"
```

**После v2.0:**
```python
logger = get_logger(__name__, structured=True)
logger.info("Processed page", page=page_num, table_count=table_count)
# → {"timestamp": "2025-01-28T14:30:00Z", "level": "INFO", 
#     "message": "Processed page", "page": 42, "table_count": 3}
```

**Польза:** Легко парсить, анализировать, строить дашборды

---

### 4. Stage Logging

**До v2.0:**
```python
logger.info("="*60)
logger.info("  Starting Structural Processing")
logger.info("="*60)
```

**После v2.0:**
```python
log_stage(logger, "structural", "Starting")
# → ============================================================
# →   📄 Starting: STRUCTURAL
# → ============================================================
```

---

### 5. Progress Bars

**До v2.0:**
```python
# Либо без progress, либо конфликт с логами
for i, page in enumerate(pages):
    logger.info(f"Processing {i+1}/{len(pages)}")
    process(page)
```

**После v2.0:**
```python
for page in create_progress_bar(pages, desc="Processing"):
    process(page)
# → Processing: 100%|████████████| 257/257 [00:45<00:00, 5.71it/s]
# → Логи не конфликтуют с progress bar!
```

---

## 📊 Метрики производительности

### Что теперь можно отследить автоматически:

```python
# После выполнения pipeline:
log_performance_summary(logger)

# Вывод:
# ============================================================
#   Performance Summary
# ============================================================
# 
# extract_single_page:
#   Count: 257
#   Total: 42.50s
#   Avg: 0.17s
#   Min: 0.05s
#   Max: 2.34s
# 
# lm_extraction:
#   Count: 245
#   Total: 1250.00s
#   Avg: 5.10s
#   Min: 2.10s
#   Max: 15.34s
```

**→ Сразу видно узкие места!**

---

## 🔧 Миграция v1.0 → v2.0

### Шаг 1: Замена файла
```bash
# Backup старого
cp am_logging.py am_logging_v1_backup.py

# Копирование нового
cp am_logging_v2.py am_logging.py
```

### Шаг 2: Обновление конфигов
```yaml
# Добавить в config/mvp.yaml:
logging:
  structured:
    enabled: true
    path: logs/pipeline.json
  
  use_tqdm_handler: true
```

### Шаг 3: Добавление декораторов
```python
# В тяжёлых функциях:
@log_performance('extract_page')
def _extract_page(self, page_num, page_obj):
    ...
```

### Шаг 4: Использование context managers
```python
# Обернуть главные операции:
with log_operation(logger, 'process_dataset', input=str(input_path)):
    # existing code
    pass
```

### Шаг 5: Добавление summaries
```python
# В конце run_mvp.py:
from am_logging import log_performance_summary, log_error_summary

try:
    # ... pipeline ...
    pass
finally:
    log_performance_summary(logger)
    log_error_summary(logger)
```

---

## ✅ Checklist миграции

- [ ] Заменён am_logging.py
- [ ] Обновлён config (добавлен structured logging)
- [ ] Добавлены `@log_performance` decorators
- [ ] Добавлены `log_operation` context managers
- [ ] Заменены loops на `create_progress_bar`
- [ ] Добавлены summaries в конце pipeline
- [ ] Протестировано на тестовом датасете

---

## 📈 Ожидаемые улучшения

| Метрика | До v2.0 | После v2.0 |
|---------|---------|------------|
| **Debugging time** | ~30 min | ~10 min |
| **Performance visibility** | 20% | 95% |
| **Error tracking** | Manual | Automatic |
| **Code lines (logging)** | 100 | 40 |
| **Log analysis time** | ~1 hour | ~5 min |

---

## 🎉 Итого

### v2.0 делает логирование:
- ✅ **Проще** - меньше boilerplate
- ✅ **Мощнее** - больше возможностей
- ✅ **Быстрее** - меньше ручной работы
- ✅ **Нагляднее** - progress bars, цвета, emoji
- ✅ **Полезнее** - метрики, aggregation, summaries

### Рекомендация:
**Обновить am_logging.py до v2.0 перед production deployment!**

---

**Version:** 2.0.0  
**Date:** 2025-01-28  
**Author:** Claude (Anthropic)
