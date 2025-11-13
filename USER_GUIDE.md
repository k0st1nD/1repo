# Archivist Magika v2.0 - User Guide

## QUICK START - Самое главное

### 1. Обработать ВСЮ библиотеку:
```bash
python run_mvp.py -i data/sources -c config/batch_full.yaml --start structural
```

### 2. Обработать одну книгу:
```bash
python run_mvp.py -i "data/sources/название_книги.pdf" -c config/batch_full.yaml --start structural
```

### 3. Проверить результаты:
```bash
python validate.py -d data/datasets/extended --stage extended
```

### 4. Создать единый индекс:
```bash
python create_unified_index.py
```

**Всё. Больше ничего не нужно.**

---

## Полное руководство пользователя

**Версия:** 2.0.1
**Дата:** 2025-11-05
**Автор:** Claude Code + User

---

## Оглавление

1. [Введение](#введение)
2. [Быстрый старт](#быстрый-старт)
3. [Архитектура системы](#архитектура-системы)
4. [Установка и настройка](#установка-и-настройка)
5. [Обработка одной книги](#обработка-одной-книги)
6. [Batch Processing (пакетная обработка)](#batch-processing)
7. [Валидация источников](#валидация-источников)
8. [Real-time мониторинг](#real-time-мониторинг)
9. [Работа с индексами](#работа-с-индексами)
10. [Troubleshooting](#troubleshooting)
11. [Advanced Usage](#advanced-usage)
12. [API Reference](#api-reference)

---

## Введение

**Archivist Magika v2.0** - это полнофункциональный RAG (Retrieval-Augmented Generation) pipeline для обработки технических книг и создания семантических индексов для поиска.

### Что умеет система?

1. **Извлечение текста** из PDF (включая таблицы, изображения, формулы)
2. **Структурный анализ** документов (оглавление, разделы, иерархия)
3. **Суммаризация** разделов с помощью LLM
4. **Extended metadata extraction** через LLM (content_type, domain, complexity, key_concepts)
5. **Chunking** с сохранением семантической целостности
6. **Embedding** векторов через BGE-M3
7. **FAISS индексация** для быстрого поиска
8. **Unified multi-book indexes** для поиска по всей библиотеке

### Ключевые особенности

- **7-этапный pipeline**: structural → structure_detect → summarize → extended → finalize → chunk → embed
- **LM-powered metadata**: Ollama с qwen2.5:7b для извлечения метаданных
- **Quality tracking**: Автоматическая валидация качества на каждом этапе
- **Batch processing**: Параллельная обработка до 4-6 книг одновременно
- **Real-time monitoring**: Живой дашборд прогресса обработки
- **Source validation**: Проверка PDF файлов перед обработкой
- **UTF-8 support**: Полная поддержка Unicode и кириллицы

---

## Быстрый старт

### Prerequisites

1. **Python 3.10+**
2. **Ollama** с установленными моделями:
   - `qwen2.5:7b` (для LM extraction)
   - `bge-m3` (для embeddings)
3. **Git Bash** (для Windows)

### Проверка готовности

```bash
# 1. Проверить Python
python --version  # Должно быть >= 3.10

# 2. Проверить Ollama
ollama list  # Должны быть qwen2.5:7b и bge-m3

# 3. Установить зависимости
pip install -r requirements.txt

# 4. Проверить структуру папок
ls data/sources  # Папка для PDF файлов
```

### Обработка первой книги (за 5 минут)

```bash
# Шаг 1: Положить PDF в data/sources/
cp /path/to/your/book.pdf data/sources/

# Шаг 2: Запустить обработку
python run_mvp.py \
  -i "data/sources/book.pdf" \
  -c config/batch_full.yaml \
  --start structural

# Шаг 3: Проверить результаты
ls data/indexes/faiss/  # FAISS index
ls data/datasets/chunks/  # Chunks JSONL
```

**Готово!** Книга обработана и проиндексирована.

---

## Архитектура системы

### Pipeline Overview

```
PDF Source
    ↓
[1] STRUCTURAL - Извлечение текста и структуры
    ↓
[2] STRUCTURE_DETECT - Определение TOC и разделов
    ↓
[3] SUMMARIZE - LLM суммаризация разделов
    ↓
[4] EXTENDED - LM extraction метаданных (content_type, domain, complexity)
    ↓
[5] FINALIZE - Объединение всех данных
    ↓
[6] CHUNK - Semantic chunking
    ↓
[7] EMBED - Векторизация и FAISS индексация
    ↓
FAISS Index + Chunks JSONL
```

### Папки и файлы

```
c:/scripts/1repo/
├── run_mvp.py                 # Основной entry point
├── am_*.py                    # Pipeline stages (am_structural.py, am_embed.py, и т.д.)
├── config/
│   ├── batch_full.yaml        # Полная конфигурация (максимум качества)
│   └── batch_quick.yaml       # Быстрая конфигурация (для тестов)
├── data/
│   ├── sources/               # [INPUT] PDF файлы
│   ├── datasets/
│   │   ├── structural/        # Stage 1 output
│   │   ├── structured/        # Stage 2 output
│   │   ├── summarized/        # Stage 3 output
│   │   ├── extended/          # Stage 4 output (с LM metadata)
│   │   ├── final/             # Stage 5 output
│   │   └── chunks/            # Stage 6 output (JSONL с чанками)
│   └── indexes/
│       ├── faiss/             # [OUTPUT] FAISS индексы (.faiss)
│       └── metadata/          # Metadata для индексов (.pkl)
├── logs/                      # Логи обработки
├── tools/
│   ├── validate_sources.py    # Валидатор PDF файлов
│   └── monitor_realtime.py    # Real-time monitor
├── batch_reprocess_lm.sh      # Sequential batch processing
└── batch_parallel.sh          # Parallel batch processing (2-4 книги одновременно)
```

### Конфигурация (config/batch_full.yaml)

```yaml
# LM Extraction (критично!)
extended:
  lm_provider: "ollama"
  lm_model: "qwen2.5:7b"  # Используется для metadata extraction

# Embedding
embedding:
  provider: "ollama"
  model: "bge-m3"
  dimensions: 384

# Chunking
chunk:
  max_tokens: 512
  overlap: 50

# Quality tracking
quality:
  enabled: true

# Logging
logging:
  level: "INFO"  # Варианты: DEBUG, INFO, WARNING, ERROR
  console: true
```

---

## Установка и настройка

### Шаг 1: Установка Ollama

```bash
# Windows
# Скачать с https://ollama.ai/download
# Установить и запустить

# Проверка
ollama --version
```

### Шаг 2: Установка моделей

```bash
# LM model для metadata extraction
ollama pull qwen2.5:7b

# Embedding model
ollama pull bge-m3

# Проверка
ollama list
# Должны быть:
# qwen2.5:7b    4.7 GB
# bge-m3        2.2 GB
```

### Шаг 3: Установка Python зависимостей

```bash
# Создать virtual environment (рекомендуется)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate  # Windows

# Установить зависимости
pip install -r requirements.txt

# Основные пакеты:
# - faiss-cpu (vector search)
# - pdfminer.six (PDF extraction)
# - sentence-transformers (embeddings)
# - PyYAML (config)
# - requests (Ollama API)
```

### Шаг 4: Настройка папок

```bash
# Создать структуру папок (если не существует)
mkdir -p data/sources
mkdir -p data/datasets/{structural,structured,summarized,extended,final,chunks}
mkdir -p data/indexes/{faiss,metadata}
mkdir -p logs
```

### Шаг 5: Проверка установки

```bash
# Тестовый запуск (без файла - покажет help)
python run_mvp.py --help

# Должен показать:
# Usage: run_mvp.py -i INPUT_PATH -c CONFIG_PATH [--start STAGE]
```

---

## Обработка одной книги

### Полная обработка (все 7 этапов)

```bash
python run_mvp.py \
  -i "data/sources/my_book.pdf" \
  -c config/batch_full.yaml \
  --start structural
```

**Время обработки:**
- Маленькая книга (100-200 страниц): 5-10 минут
- Средняя (300-500 страниц): 15-25 минут
- Большая (600+ страниц): 30-60 минут

### Запуск с конкретного этапа

```bash
# Если у вас уже есть chunks, только создать FAISS index
python run_mvp.py \
  -i "data/datasets/chunks/my_book.dataset.chunks.jsonl" \
  -c config/batch_full.yaml \
  --start embed

# Если нужно переделать только LM extraction
python run_mvp.py \
  -i "data/datasets/summarized/my_book.dataset.jsonl" \
  -c config/batch_full.yaml \
  --start extended
```

### Проверка результатов

```bash
# 1. Проверить chunks
head -5 data/datasets/chunks/my_book.dataset.chunks.jsonl

# 2. Проверить FAISS index
ls -lh data/indexes/faiss/my_book.dataset.faiss

# 3. Проверить LM metadata (extended fields)
python -c "
import json
with open('data/datasets/extended/my_book.dataset.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i == 0: continue  # Skip header
        data = json.loads(line)
        if 'extended_fields' in data:
            print(f'Page {i}: {data[\"extended_fields\"]}')
            break
"
```

### Логи

Логи сохраняются в консоль и в файл:

```bash
# Просмотр последних 50 строк лога
tail -50 logs/processing.log

# Поиск ошибок
grep -i "error" logs/processing.log

# Проверка LM extraction
grep "LM EXTRACTION" logs/processing.log
```

---

## Batch Processing

### Sequential Processing (последовательная обработка)

**Используется для:** Максимальное качество, полные логи

```bash
./batch_reprocess_lm.sh
```

**Что происходит:**
1. Валидация всех PDF файлов в data/sources/
2. Обработка каждой книги последовательно (1 за раз)
3. Логи в logs/batch_lm_v3/{book_name}.log
4. Прогресс и ETA в консоли

**Время:** ~9-15 минут на книгу × количество книг

**Логи:**
```bash
# Главный лог
cat logs/batch_lm_v3.log

# Лог конкретной книги
cat logs/batch_lm_v3/my_book.log

# Живой мониторинг
tail -f logs/batch_lm_v3.log
```

### Parallel Processing (параллельная обработка)

**Используется для:** Ускорение обработки (2-3x быстрее)

```bash
# Редактировать batch_parallel.sh
# Установить PARALLEL_JOBS=3 (для 16-core CPU)

./batch_parallel.sh
```

**Что происходит:**
1. Валидация источников
2. Обработка 3 книг одновременно
3. Автоматический запуск следующей книги при завершении

**Время:** ~1-1.5 часа для 20 книг (вместо 3-4 часов)

**Рекомендации:**
- 16 cores / 32 GB RAM: `PARALLEL_JOBS=3-4`
- 8 cores / 16 GB RAM: `PARALLEL_JOBS=2`
- 4 cores / 8 GB RAM: `PARALLEL_JOBS=1` (sequential)

### Исключение файлов из batch

Отредактируйте переменную `EXCLUDE` в скрипте:

```bash
# В batch_reprocess_lm.sh или batch_parallel.sh
EXCLUDE="Ядро 2025-08-29.pdf"

# Или несколько файлов (через цикл)
EXCLUDE_LIST=(
    "Ядро 2025-08-29.pdf"
    "temp_book.pdf"
)
```

---

## Валидация источников

### Зачем нужна валидация?

Проверяет PDF файлы **перед** обработкой на:
1. **Специальные символы** (®, ©, ™) - FAISS не может создать файлы с ними
2. **Длинные имена** (>100 символов) - Windows path limit (260 chars)
3. **Множественные пробелы** - Bash escaping проблемы
4. **Кириллицу** - Может вызывать проблемы в некоторых системах
5. **Повреждённые PDF** - Нечитаемые файлы
6. **Дубликаты имён** - Перезапись данных

### Быстрая проверка

```bash
python tools/validate_sources.py
```

**Вывод:**
```
============================================================
  SOURCE FILES VALIDATION
============================================================
Source directory: data\sources

Found 21 PDF files

[OK] All files passed validation!
```

### Если найдены проблемы

```
[WARNING] ISSUES FOUND:

FILE: baza-znanij-safe®-russia.pdf
   [!] UNSAFE_CHARS: Found: '®'
   --> Suggested: baza_znanij_safer_russia.pdf

FILE: data-driven-organization-design-sustaining...pdf
   [!] LONG_FILENAME: 113 characters (max: 100)
   --> Suggested: data_driven_organization_design_c906b8.pdf
```

### Автоматическое переименование

```bash
python tools/validate_sources.py --auto-rename
```

**Что произойдёт:**
1. Создаст безопасные имена (ASCII, без спецсимволов)
2. Переименует файлы
3. Покажет отчёт

### Интеграция в batch

Валидатор **уже интегрирован** в batch скрипты:

```bash
# В batch_reprocess_lm.sh и batch_parallel.sh
# Автоматически запускается перед обработкой
python tools/validate_sources.py -d "$SOURCE_DIR" --non-interactive
```

Если найдены проблемы - скрипт остановится и попросит исправить.

---

## Real-time мониторинг

### Запуск монитора

```bash
# В отдельном терминале (пока идёт batch processing)
python tools/monitor_realtime.py
```

**Экран монитора:**
```
================================================================================
  ARCHIVIST MAGIKA v2.0 - REAL-TIME PIPELINE MONITOR
  2025-11-05 14:30:15
================================================================================

SUMMARY:
  Total books: 20
  Completed:   12 (60.0%)
  Failed:      1
  Processing:  2
  Pending:     5

  Elapsed: 1h 45m
  ETA:     55m

  Overall: [=========================-------------------------] 60%

--------------------------------------------------------------------------------

CURRENTLY PROCESSING:
  [LM]  lean_analytics.pdf
        Stage: extended              [===========---------] 55%

  [LM]  norton_kaplan_balanced_scorecard.pdf
        Stage: chunk                 [===============-----] 75%

COMPLETED (12):
  [LM] [OK] 2024_final_dora_report.pdf
  [LM] [OK] agile_conversations.pdf
  ...

FAILED (1):
  [FAIL] baza-znanij-safe®-russia.pdf

================================================================================
  Refreshing every 5s... (Press Ctrl+C to exit)
================================================================================
```

### Опции монитора

```bash
# Мониторить другую директорию
python tools/monitor_realtime.py --log-dir logs/batch_parallel

# Изменить интервал обновления (по умолчанию 5s)
python tools/monitor_realtime.py --refresh 10
```

### Что показывает монитор?

1. **Общая статистика:** Total, Completed, Failed, Processing, Pending
2. **Прогресс:** Процент завершения + progress bar
3. **Время:** Elapsed time + ETA (estimated time to completion)
4. **Текущие книги:** Какие книги обрабатываются прямо сейчас
5. **Текущий stage:** На каком этапе pipeline находится книга
6. **LM extraction status:** [LM] маркер если LM extraction работал
7. **Завершённые книги:** Последние 10 успешно обработанных
8. **Упавшие книги:** Список failed books

---

## Работа с индексами

### Индивидуальные FAISS индексы

После обработки каждой книги создаётся отдельный FAISS index:

```bash
ls data/indexes/faiss/

# Пример:
# 2024_final_dora_report.dataset.faiss
# agile_metrics_in_action.dataset.faiss
# pmbok_7ed_2021.dataset.faiss
```

**Использование:**
```python
import faiss
import pickle

# Загрузить FAISS index
index = faiss.read_index('data/indexes/faiss/pmbok_7ed_2021.dataset.faiss')

# Загрузить metadata
with open('data/indexes/metadata/pmbok_7ed_2021.dataset.pkl', 'rb') as f:
    metadata = pickle.load(f)

# Поиск
query_vector = ...  # Ваш query embedding (384 dim)
D, I = index.search(query_vector.reshape(1, -1), k=10)

# Получить результаты
for idx in I[0]:
    chunk = metadata['chunks'][idx]
    print(f"Book: {chunk['book_name']}")
    print(f"Text: {chunk['text'][:200]}...")
```

### Unified Multi-Book Index

Создание единого индекса для всех книг:

```bash
# Создать unified index
python create_unified_index.py --output library_unified
```

**Результат:**
```
Books: 22
Total chunks: 10,690
Files:
  - data/indexes/faiss/library_unified.faiss (4.1 MB)
  - data/indexes/metadata/library_unified.dataset.pkl (12.3 MB)
  - data/indexes/metadata/library_unified.info.json (3 KB)
```

**Использование:**
```python
import faiss
import pickle

# Загрузить unified index
index = faiss.read_index('data/indexes/faiss/library_unified.faiss')
with open('data/indexes/metadata/library_unified.dataset.pkl', 'rb') as f:
    metadata = pickle.load(f)

# Metadata содержит:
# - chunks: List[Dict] - все чанки всех книг
# - books: List[str] - список книг
# - book_to_chunks: Dict[str, List[int]] - mapping book → chunk indices

# Поиск по всей библиотеке
query_vector = get_embedding("How to measure DevOps metrics?")
D, I = index.search(query_vector.reshape(1, -1), k=20)

# Группировка по книгам
results_by_book = {}
for distance, idx in zip(D[0], I[0]):
    chunk = metadata['chunks'][idx]
    book = chunk['book_name']
    if book not in results_by_book:
        results_by_book[book] = []
    results_by_book[book].append({
        'distance': distance,
        'text': chunk['text'],
        'page': chunk.get('page_num')
    })

# Топ-5 книг по релевантности
for book, chunks in sorted(results_by_book.items(),
                           key=lambda x: min(c['distance'] for c in x[1]))[:5]:
    print(f"\n{book}:")
    for chunk in chunks[:3]:
        print(f"  - Page {chunk['page']}: {chunk['text'][:100]}...")
```

### Chunks JSONL файлы

Каждая книга также имеет JSONL файл с чанками:

```bash
data/datasets/chunks/pmbok_7ed_2021.dataset.chunks.jsonl
```

**Формат:**
```jsonl
{"type": "header", "version": "2.0", "book_name": "pmbok_7ed_2021", "total_chunks": 767}
{"chunk_id": "pmbok_7ed_2021_000", "book_name": "pmbok_7ed_2021", "text": "...", "page_num": 1, "extended_fields": {...}}
{"chunk_id": "pmbok_7ed_2021_001", "book_name": "pmbok_7ed_2021", "text": "...", "page_num": 1, "extended_fields": {...}}
```

**Использование:**
```python
import json

chunks = []
with open('data/datasets/chunks/pmbok_7ed_2021.dataset.chunks.jsonl', 'r', encoding='utf-8') as f:
    for i, line in enumerate(f):
        if i == 0:  # Skip header
            header = json.loads(line)
            print(f"Book: {header['book_name']}, Total: {header['total_chunks']}")
            continue
        chunk = json.loads(line)
        chunks.append(chunk)

# Фильтр по extended metadata
advanced_chunks = [c for c in chunks
                  if c.get('extended_fields', {}).get('complexity') == 'advanced']

print(f"Found {len(advanced_chunks)} advanced chunks")
```

---

## Troubleshooting

### Проблема 1: "Ollama API not responding"

**Симптом:**
```
[LM EXTRACTION] Ollama API not responding (status: 404)
```

**Решение:**
```bash
# 1. Проверить, запущен ли Ollama
curl http://localhost:11434/api/tags

# 2. Если не запущен - запустить
ollama serve

# 3. Проверить модели
ollama list

# 4. Если модели нет - скачать
ollama pull qwen2.5:7b
```

### Проблема 2: "Model 'qwen2.5:7b' not found"

**Решение:**
```bash
# Скачать модель
ollama pull qwen2.5:7b

# Проверить установку
ollama list | grep qwen2.5
```

### Проблема 3: FAISS "File not found" с символом ® в пути

**Симптом:**
```
FileNotFoundError: 'data\indexes\faiss\baza-znanij-safe®-russia.dataset.faiss'
```

**Решение:**
```bash
# 1. Использовать валидатор
python tools/validate_sources.py --auto-rename

# 2. Или переименовать вручную
mv "data/sources/file®.pdf" "data/sources/file_r.pdf"
```

### Проблема 4: Unicode ошибки в Windows консоли

**Симптом:**
```
UnicodeEncodeError: 'charmap' codec can't encode character
```

**Решение:**
```bash
# В PowerShell
chcp 65001

# Или использовать Git Bash (UTF-8 by default)
```

### Проблема 5: "Out of memory" при batch processing

**Решение:**
```bash
# 1. Уменьшить PARALLEL_JOBS
# В batch_parallel.sh:
PARALLEL_JOBS=2  # Вместо 3-4

# 2. Увеличить swap (Windows: System → Advanced → Performance → Virtual Memory)

# 3. Или использовать sequential processing
./batch_reprocess_lm.sh
```

### Проблема 6: Batch processing застрял

**Диагностика:**
```bash
# 1. Проверить логи
tail -50 logs/batch_lm_v3.log

# 2. Проверить последний обрабатываемый файл
ls -lt logs/batch_lm_v3/*.log | head -1

# 3. Проверить процессы Python
ps aux | grep python

# 4. Если застрял - убить процесс
pkill -f "run_mvp.py"
```

### Проблема 7: Chunks file пуст или повреждён

**Проверка:**
```bash
# Проверить размер
ls -lh data/datasets/chunks/my_book.dataset.chunks.jsonl

# Проверить формат
head -2 data/datasets/chunks/my_book.dataset.chunks.jsonl
```

**Решение:**
```bash
# Переобработать с этапа chunk
python run_mvp.py \
  -i "data/datasets/final/my_book.dataset.jsonl" \
  -c config/batch_full.yaml \
  --start chunk
```

---

## Advanced Usage

### Кастомная конфигурация

Создайте свой config YAML:

```yaml
# config/my_config.yaml

extended:
  lm_provider: "ollama"
  lm_model: "qwen2.5:7b"
  skip_duplicate_detection: false  # Включить проверку дубликатов

embedding:
  provider: "ollama"
  model: "bge-m3"
  dimensions: 384

chunk:
  max_tokens: 1024  # Больше chunks
  overlap: 100      # Больше overlap

quality:
  enabled: true
  min_score: 0.7  # Строже валидация

logging:
  level: "DEBUG"  # Подробные логи
  console: true
```

### Запуск с кастомной конфигурацией

```bash
python run_mvp.py \
  -i "data/sources/my_book.pdf" \
  -c config/my_config.yaml \
  --start structural
```

### API для поиска (Python)

```python
# search_library.py
import faiss
import pickle
import numpy as np
from sentence_transformers import SentenceTransformer

class LibrarySearch:
    def __init__(self, index_path: str, metadata_path: str):
        self.index = faiss.read_index(index_path)
        with open(metadata_path, 'rb') as f:
            self.metadata = pickle.load(f)
        self.model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')

    def search(self, query: str, k: int = 10):
        """Search library by query."""
        # Get query embedding
        query_emb = self.model.encode([query])[0]

        # Search FAISS
        D, I = self.index.search(query_emb.reshape(1, -1), k)

        # Format results
        results = []
        for distance, idx in zip(D[0], I[0]):
            chunk = self.metadata['chunks'][idx]
            results.append({
                'book': chunk['book_name'],
                'text': chunk['text'],
                'page': chunk.get('page_num'),
                'score': float(1 / (1 + distance)),  # Convert distance to score
                'metadata': chunk.get('extended_fields', {})
            })

        return results

# Usage
searcher = LibrarySearch(
    'data/indexes/faiss/library_unified.faiss',
    'data/indexes/metadata/library_unified.dataset.pkl'
)

results = searcher.search("How to implement OKRs?", k=10)
for r in results[:5]:
    print(f"\n{r['book']} (Page {r['page']}) - Score: {r['score']:.3f}")
    print(f"{r['text'][:200]}...")
```

### Batch processing с фильтрацией

```bash
# Обработать только книги по Agile
for pdf in data/sources/*agile*.pdf; do
    python run_mvp.py -i "$pdf" -c config/batch_full.yaml --start structural
done

# Или по дате модификации (последние 7 дней)
find data/sources -name "*.pdf" -mtime -7 | while read pdf; do
    python run_mvp.py -i "$pdf" -c config/batch_full.yaml --start structural
done
```

### Экспорт результатов

```python
# export_results.py
import json

# Load all chunks from all books
all_chunks = []
for chunks_file in Path('data/datasets/chunks').glob('*.jsonl'):
    with open(chunks_file, 'r', encoding='utf-8') as f:
        for i, line in enumerate(f):
            if i == 0: continue  # Skip header
            chunk = json.loads(line)
            all_chunks.append(chunk)

# Export to CSV
import csv
with open('library_export.csv', 'w', newline='', encoding='utf-8') as f:
    writer = csv.DictWriter(f, fieldnames=['book', 'page', 'text', 'content_type', 'domain', 'complexity'])
    writer.writeheader()
    for chunk in all_chunks:
        ext = chunk.get('extended_fields', {})
        writer.writerow({
            'book': chunk['book_name'],
            'page': chunk.get('page_num'),
            'text': chunk['text'][:500],  # Первые 500 символов
            'content_type': ext.get('content_type'),
            'domain': ext.get('domain'),
            'complexity': ext.get('complexity')
        })
```

---

## API Reference

### run_mvp.py

```bash
python run_mvp.py -i INPUT -c CONFIG [--start STAGE]

Options:
  -i, --input PATH       Input file (PDF or JSONL)
  -c, --config PATH      Config YAML file
  --start STAGE         Start from stage (default: structural)
                        Stages: structural, structure_detect, summarize,
                               extended, finalize, chunk, embed

Examples:
  # Full pipeline
  python run_mvp.py -i book.pdf -c config/batch_full.yaml

  # From specific stage
  python run_mvp.py -i book.pdf -c config/batch_full.yaml --start extended
```

### validate_sources.py

```bash
python tools/validate_sources.py [OPTIONS]

Options:
  -d, --dir PATH           Source directory (default: data/sources)
  -l, --max-length NUM     Max filename length (default: 100)
  --auto-rename            Automatically rename problematic files
  --non-interactive        Run without user prompts

Examples:
  # Check sources
  python tools/validate_sources.py

  # Auto-fix
  python tools/validate_sources.py --auto-rename

  # Batch mode
  python tools/validate_sources.py --non-interactive
```

### monitor_realtime.py

```bash
python tools/monitor_realtime.py [OPTIONS]

Options:
  --log-dir PATH       Log directory to monitor (default: logs/batch_lm_v3)
  --refresh SECONDS    Refresh interval (default: 5)

Examples:
  # Monitor batch processing
  python tools/monitor_realtime.py

  # Custom log dir
  python tools/monitor_realtime.py --log-dir logs/batch_parallel

  # Slower refresh (10s)
  python tools/monitor_realtime.py --refresh 10
```

### create_unified_index.py

```bash
python create_unified_index.py [OPTIONS]

Options:
  --output NAME           Output index name (default: library_unified)
  --exclude PATTERNS      Comma-separated patterns to exclude

Examples:
  # Create unified index
  python create_unified_index.py

  # Exclude yadro
  python create_unified_index.py --exclude "yadro_"

  # Custom name
  python create_unified_index.py --output my_library_v2
```

---

## Заключение

Теперь у вас есть полное руководство по использованию **Archivist Magika v2.0** без необходимости в постоянной помощи.

### Типичный workflow

1. **Положить PDF в data/sources/**
2. **Запустить валидацию:** `python tools/validate_sources.py --auto-rename`
3. **Запустить batch:** `./batch_reprocess_lm.sh` (или `./batch_parallel.sh` для speed)
4. **Мониторить прогресс:** `python tools/monitor_realtime.py` (в другом терминале)
5. **Дождаться завершения** (или прервать Ctrl+C если нужно)
6. **Создать unified index:** `python create_unified_index.py`
7. **Использовать для поиска**

### Где получить помощь?

- **Документация:** Этот файл (USER_GUIDE.md)
- **Технические детали:**
  - BATCH_PROCESSING_DETAILED_REPORT.md
  - PERFORMANCE_OPTIMIZATION.md
  - SOURCE_VALIDATION_GUIDE.md
- **Code:** Все модули am_*.py подробно документированы

### Версии и changelog

**v2.0.1 (2025-11-05):**
- Исправлен LM extraction (qwen2.5:7b)
- Добавлен UTF-8 support для Windows
- Добавлен source validator
- Добавлен real-time monitor
- Integrated validator в batch scripts

**v2.0.0:**
- Первая полная версия 7-stage pipeline

---

**Конец руководства**

*Версия: 2.0.1*
*Последнее обновление: 2025-11-05*
*Авторы: Claude Code + User*
