# Performance Optimization Guide
## Archivist Magika v2.0 - Batch Processing

**Дата:** 2025-11-05
**Версия:** 1.0

---

## Текущая производительность

### Baseline (Sequential Processing)
- **Метод:** Последовательная обработка (1 книга за раз)
- **Скорость:** ~9-15 минут на книгу (зависит от размера)
- **Время для 20 книг:** ~3-4 часа
- **Ресурсы:** 1 CPU core + Ollama API

### Система
- **CPU:** 16 cores / 32 threads
- **RAM:** 32 GB
- **Использование:** ~5% CPU, ~2 GB RAM (sequential mode)

---

## Узкие места (Bottlenecks)

### 1. LM Extraction (Extended Stage)
**Самое медленное:** 60-70% времени обработки

- Ollama API вызовы для каждой страницы
- Model: `qwen2.5:7b`
- ~120 запросов на книгу (по 1 на страницу)
- ~2-3 секунды на запрос

**Расчет:**
```
120 pages × 2.5 sec = 300 sec = 5 min (только LM)
+ 4 min (остальные stages) = 9 min total
```

### 2. PDF Extraction (Structural Stage)
**Второе по медленности:** 15-20% времени

- pdfminer.six для текста
- OCR через Tesseract (если нужно)
- Обработка таблиц

### 3. Embedding (Embed Stage)
**Третье:** 10-15% времени

- BGE-M3 через Ollama
- Batch encoding chunks
- FAISS index creation

---

## Стратегии оптимизации

### ⚡ Уровень 1: Параллелизация книг (Easy, 2-3x speedup)

**Идея:** Обрабатывать 2-3 книги одновременно

**Плюсы:**
- ✅ Простая реализация (готовый скрипт: `batch_parallel.sh`)
- ✅ Использует больше CPU cores
- ✅ 2-3x ускорение (3-4 часа → 1-1.5 часа)

**Минусы:**
- ⚠️ Ollama может стать bottleneck (зависит от concurrent requests)
- ⚠️ Увеличение RAM usage (~6 GB)

**Рекомендация:** Запускать 2-3 параллельных процесса

**Команда:**
```bash
# В batch_parallel.sh установить:
PARALLEL_JOBS=3

# Запуск:
./batch_parallel.sh
```

---

### ⚡⚡ Уровень 2: Batch LM requests (Medium, 1.5-2x speedup на stage)

**Идея:** Отправлять несколько страниц в Ollama одновременно

**Изменения в коде:**
```python
# am_extended.py - добавить async batch processing

import asyncio
import aiohttp

async def extract_batch(self, pages: List[dict]) -> List[dict]:
    """Extract extended fields for batch of pages."""
    tasks = [self._extract_single_page(page) for page in pages]
    return await asyncio.gather(*tasks)

# Usage:
batch_size = 5  # 5 pages at once
for i in range(0, len(pages), batch_size):
    batch = pages[i:i+batch_size]
    results = await extract_batch(batch)
```

**Плюсы:**
- ✅ Значительное ускорение LM stage (5x faster)
- ✅ Лучшее использование Ollama capacity

**Минусы:**
- ⚠️ Требует рефакторинга кода (async/await)
- ⚠️ Ollama должен поддерживать concurrent requests

**Рекомендация:** Для production use после тестирования

---

### ⚡⚡⚡ Уровень 3: GPU acceleration (Hard, 5-10x speedup)

**Идея:** Использовать GPU для inference вместо CPU

**Требования:**
- NVIDIA GPU с CUDA
- Ollama с GPU support
- VRAM: 8+ GB для qwen2.5:7b

**Изменения:**
```bash
# Установить Ollama с GPU support
# Проверить:
ollama run qwen2.5:7b --verbose

# В конфиге:
extended:
  lm_provider: "ollama"
  lm_model: "qwen2.5:7b"
  device: "cuda"  # Добавить поддержку
```

**Плюсы:**
- ✅ Огромное ускорение LM inference (10x+)
- ✅ Можно увеличить batch_size

**Минусы:**
- ⚠️ Требует GPU
- ⚠️ Сложная настройка

**Рекомендация:** Если есть GPU - обязательно использовать

---

### 🔧 Уровень 4: Optimization tweaks (Small gains)

#### 4.1 Reduce logging level
```bash
# В config/batch_full.yaml:
logging:
  level: "WARNING"  # Вместо INFO
  console: false
```

**Экономия:** ~5% времени (меньше I/O)

#### 4.2 Skip duplicate detection
```yaml
# Если дубликаты не критичны:
extended:
  skip_duplicate_detection: true
```

**Экономия:** ~2-3% времени

#### 4.3 Disable quality tracking
```yaml
quality:
  enabled: false  # Для batch runs
```

**Экономия:** ~1-2% времени

#### 4.4 Smaller embedding model
```yaml
embedding:
  model: "bge-small-en-v1.5"  # Вместо bge-m3
  dimensions: 384 → 256
```

**Экономия:** ~20% времени на embed stage
**Минус:** Чуть хуже качество векторов

---

## Рекомендованная конфигурация

### Для вашей системы (16 cores, 32 GB RAM):

**Быстрая обработка (Best performance):**
```bash
# 1. Параллелизация: 3 книги одновременно
PARALLEL_JOBS=3

# 2. Reduce logging
logging:
  level: "WARNING"
  console: false

# 3. Skip non-critical checks
extended:
  skip_duplicate_detection: true

quality:
  enabled: false
```

**Ожидаемый результат:**
- **Время:** 1-1.5 часа (вместо 3-4)
- **RAM usage:** ~6-8 GB
- **CPU usage:** ~30-40%

---

### Для максимального качества (Best quality):

```bash
# 1. Sequential processing (текущий режим)
PARALLEL_JOBS=1

# 2. Full logging
logging:
  level: "INFO"
  console: true

# 3. All checks enabled
extended:
  skip_duplicate_detection: false

quality:
  enabled: true
```

**Ожидаемый результат:**
- **Время:** 3-4 часа
- **Quality:** Maximum
- **Logs:** Полные детальные логи

---

## Практические примеры

### Пример 1: Quick reprocessing (после bugfix)

```bash
# Используем parallel processing
cp batch_parallel.sh batch_quick.sh

# Edit batch_quick.sh:
PARALLEL_JOBS=4
CONFIG="config/batch_quick.yaml"

# config/batch_quick.yaml:
logging:
  level: "WARNING"

extended:
  skip_duplicate_detection: true

quality:
  enabled: false

# Run:
./batch_quick.sh
```

**Время:** ~45-60 минут для 20 книг

---

### Пример 2: Production processing (первая обработка)

```bash
# Используем текущий sequential script
./batch_reprocess_lm.sh

# С полными настройками качества
```

**Время:** ~3-4 часа для 20 книг
**Результат:** Максимальное качество + полные логи

---

## Мониторинг производительности

### Проверка текущего использования ресурсов:

```powershell
# CPU usage
Get-Process python | Select-Object CPU,ProcessName

# RAM usage
Get-Process python | Select-Object WS,ProcessName

# Ollama status
curl http://localhost:11434/api/tags
```

### Real-time monitoring:

```bash
# В отдельном терминале:
watch -n 5 'ps aux | grep python | grep -v grep'

# Или через monitor script:
./monitor_batch.sh
```

---

## Benchmarks (Ваша система)

### Sequential (Current)
- **1 книга:** 9 минут (DORA report, 120 pages)
- **20 книг:** ~180 минут (оценка)
- **CPU:** 5-10% usage
- **RAM:** ~2 GB

### Parallel (x3 jobs)
- **3 книги:** ~12-15 минут (concurrent)
- **20 книг:** ~60-80 минут (оценка)
- **CPU:** 30-40% usage
- **RAM:** ~6 GB

### GPU-accelerated (теоретически)
- **1 книга:** ~3-4 минуты
- **20 книг:** ~60 минут (sequential)
- **GPU:** 80-90% usage
- **VRAM:** ~6 GB

---

## Troubleshooting

### Проблема: Ollama becomes bottleneck

**Симптомы:**
- Multiple processes waiting for Ollama
- API timeouts
- High Ollama CPU usage

**Решение:**
```bash
# Увеличить concurrent requests в Ollama:
export OLLAMA_NUM_PARALLEL=4
export OLLAMA_MAX_LOADED_MODELS=2

# Restart Ollama:
ollama serve
```

---

### Проблема: Out of memory

**Симптомы:**
- Python crashes
- System slowdown

**Решение:**
```bash
# Reduce parallel jobs:
PARALLEL_JOBS=2  # Вместо 3-4

# Или увеличить swap:
# (Windows: Settings → System → About → Advanced system settings → Performance → Virtual memory)
```

---

### Проблема: Disk I/O bottleneck

**Симптомы:**
- Slow FAISS writes
- Log files growing slowly

**Решение:**
```bash
# Use SSD for processing (if available)
# Reduce logging:
logging:
  level: "ERROR"

# Disable quality JSON writes:
quality:
  enabled: false
```

---

## Future improvements

### Short term (1-2 weeks)
1. ✅ Implement batch_parallel.sh
2. 🔲 Add async LM requests (asyncio)
3. 🔲 Add progress bar (tqdm)
4. 🔲 Add time estimates per book

### Medium term (1 month)
1. 🔲 GPU support for Ollama
2. 🔲 Distributed processing (multiple machines)
3. 🔲 Cache LM results (avoid reprocessing)
4. 🔲 Incremental updates (process only changed pages)

### Long term (3+ months)
1. 🔲 Cloud processing (AWS Lambda, Azure Functions)
2. 🔲 Real-time dashboard (web UI)
3. 🔲 Auto-scaling based on load
4. 🔲 ML model optimization (quantization, pruning)

---

## Заключение

**Текущий режим (sequential):**
- ✅ Стабильный и надежный
- ✅ Полные логи и качество
- ⏱️ ~3-4 часа для 20 книг

**Рекомендация для будущего:**
- Использовать `batch_parallel.sh` с `PARALLEL_JOBS=3`
- Ожидаемое ускорение: 2-3x
- Время: ~1-1.5 часа для 20 книг

**Если есть GPU:**
- Настроить Ollama с GPU support
- Ожидаемое ускорение: 5-10x
- Время: ~30-60 минут для 20 книг

---

**Конец документа**

*Версия 1.0*
*Дата: 2025-11-05*
*Автор: Claude Code*
