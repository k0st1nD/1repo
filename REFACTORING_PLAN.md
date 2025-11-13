# План рефакторинга Archivist Magika v2.0
# Критические исправления и улучшения

**Дата создания:** 2025-11-05
**Версия:** 1.0
**Приоритет:** ВЫСОКИЙ

---

## Исполнительное резюме

На основе анализа батч-процессинга 20 книг выявлено 3 критических проблемы и несколько важных улучшений.

**Критичность:**
- 🔴 **CRITICAL** - блокирует качество данных, требует немедленного исправления
- 🟡 **HIGH** - существенно влияет на работу, желательно исправить скоро
- 🟢 **MEDIUM** - улучшение UX, можно отложить

---

## 1. Критические проблемы

### 🔴 CRITICAL-1: LM Extraction не работает (hardcoded model fallback)

**Приоритет:** P0 - Блокирует качество metadata
**Статус:** NOT FIXED
**Impact:** 4,763 API errors, отсутствуют LM-extracted поля у всех 20 книг

#### Проблема

**Файл:** `am_extended.py:142`

```python
# ТЕКУЩИЙ КОД (НЕПРАВИЛЬНО):
def __init__(self, config: dict):
    self.model = config.get('model', 'llama3.2:3b')  # ❌ Неправильный ключ конфига
```

**Конфиг указывает:**
```yaml
extended:
  lm_model: "qwen2.5:7b"  # ✓ Правильный ключ
```

**Результат:**
- Код ищет ключ `model` (не существует)
- Получает fallback `llama3.2:3b` (модель не установлена)
- Все LM API запросы получают 404
- Extended fields падают на LM extraction
- Используются только heuristic fallbacks

#### Решение

**Файл:** `am_extended.py`

```python
# ИСПРАВЛЕННЫЙ КОД:
def __init__(self, config: dict):
    # Используем правильный ключ из конфига
    self.model = config.get('lm_model', 'qwen2.5:7b')  # ✓ Исправлено
    self.provider = config.get('lm_provider', 'ollama')

    # Добавим валидацию
    logger.info(f"LM configured: provider={self.provider}, model={self.model}")
```

#### Места изменения

1. **`am_extended.py:142`** - основная проблема
2. **`am_extended.py:150-200`** - проверить все обращения к конфигу LM
3. **`am_common.py`** - добавить валидацию конфига при загрузке

#### План действий

1. ✅ Исправить код в `am_extended.py`
2. ✅ Добавить logging конфигурации LM при инициализации
3. ✅ Добавить валидацию: проверить доступность модели через Ollama API
4. ✅ Тесты: unit test для config loading
5. ⏳ Переобработать все 20 книг с исправленным кодом
6. ⏳ Сравнить качество metadata до/после

#### Expected outcome

```
# После исправления в логах:
2025-11-05 - am_extended - INFO - LM configured: provider=ollama, model=qwen2.5:7b
2025-11-05 - am_extended - INFO - LM model check: OK (qwen2.5:7b responding)
2025-11-05 - am_extended - INFO - Extracted fields: content_type=technical, domain=management, complexity=advanced
```

**Метрики успеха:**
- 0 Ollama 404 errors
- content_type, domain, complexity присутствуют у всех книг
- key_concepts извлечены

---

### 🔴 CRITICAL-2: Длинные имена файлов с кириллицей

**Приоритет:** P0 - Блокирует обработку некоторых файлов
**Статус:** PARTIALLY FIXED (вручную для PMBOK)
**Impact:** PMBOK был пропущен, требовалась ручная обработка

#### Проблема

**Симптомы:**
1. Bash wildcard `*.pdf` пропускает файлы с длинными именами
2. FAISS не может записать index с кириллицей в имени (147+ символов)
3. Windows PATH_MAX ограничения

**Пример:**
```
# Оригинальное имя (147 символов):
Project Management Institute - Руководство к своду знаний по управлению проектами (Руководство PMBOK) и Стандарт управления проектом. Седьмое издание - 2021.pdf

# Ошибка FAISS:
RuntimeError: could not open c:\scripts\1repo\data\indexes\faiss\project_management_institute_-_руководство_к_своду_знаний_по_управлению_проектами_(руководство_pmbok)_и_стандарт_управления_проектом._седьмое_издание_-_2021.dataset.faiss for writing: Invalid argument
```

#### Решение

**Подход 1: Автоматическое сокращение имен (РЕКОМЕНДУЕТСЯ)**

**Файл:** `am_common.py` - новая функция

```python
import hashlib
from pathlib import Path

def sanitize_filename(filename: str, max_length: int = 50) -> str:
    """
    Создает безопасное короткое имя файла.

    Args:
        filename: Оригинальное имя файла
        max_length: Максимальная длина результата

    Returns:
        Безопасное короткое имя (ASCII, без спецсимволов)

    Example:
        >>> sanitize_filename("Project Management Institute - Руководство...pdf")
        'project_management_institute_pmbok_a3f8b2.pdf'
    """
    # 1. Убрать расширение
    stem = Path(filename).stem
    ext = Path(filename).suffix

    # 2. Транслитерация кириллицы
    transliterate_map = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e',
        'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k',
        'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r',
        'с': 's', 'т': 't', 'у': 'u', 'ф': 'f', 'х': 'h', 'ц': 'ts',
        'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y', 'ь': '',
        'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    stem_lower = stem.lower()
    transliterated = ''
    for char in stem_lower:
        if char in transliterate_map:
            transliterated += transliterate_map[char]
        elif char.isalnum() or char in ['-', '_']:
            transliterated += char
        else:
            transliterated += '_'

    # 3. Убрать множественные underscores
    while '__' in transliterated:
        transliterated = transliterated.replace('__', '_')

    # 4. Укоротить до max_length
    if len(transliterated) > max_length:
        # Добавим hash для уникальности
        file_hash = hashlib.md5(stem.encode()).hexdigest()[:6]
        transliterated = transliterated[:max_length-7] + '_' + file_hash

    # 5. Убрать trailing underscores
    transliterated = transliterated.strip('_')

    return transliterated + ext


# Использование в пайплайне:
def get_safe_book_name(pdf_path: Path) -> str:
    """Получить безопасное имя книги для dataset файлов."""
    return sanitize_filename(pdf_path.name, max_length=50)
```

**Где применить:**

1. **`run_mvp.py`** - при создании output paths
2. **`am_structural_robust.py`** - при сохранении datasets
3. **`am_embed.py`** - при создании FAISS index
4. **`batch_process_library.py`** - при обработке списка файлов

#### План действий

1. ✅ Добавить `sanitize_filename()` в `am_common.py`
2. ✅ Интегрировать во все этапы пайплайна
3. ✅ Добавить mapping файл: `original_name → safe_name`
4. ✅ Unit tests для различных edge cases
5. ✅ Документация: какие символы допустимы

**Подход 2: Fix bash скрипта**

**Файл:** `batch_simple.sh`

```bash
# ТЕКУЩИЙ КОД:
for pdf in "$SOURCE_DIR"/*.pdf; do
    filename=$(basename "$pdf")
    # ...
done

# ИСПРАВЛЕННЫЙ КОД:
# Используем find вместо wildcard для длинных имен
find "$SOURCE_DIR" -maxdepth 1 -name "*.pdf" -type f | while IFS= read -r pdf; do
    filename=$(basename "$pdf")

    # Проверка длины имени
    if [ ${#filename} -gt 100 ]; then
        echo "[WARN] Long filename detected: ${filename:0:50}..."
    fi

    # ...
done
```

#### Expected outcome

```
# Автоматическое сокращение:
PMBOK 2021.pdf → pmbok_2021.dataset.faiss

# Mapping сохранен:
data/filename_mappings.json:
{
  "project_management_institute_pmbok_a3f8b2": {
    "original": "Project Management Institute - Руководство...",
    "safe": "pmbok_2021",
    "created_at": "2025-11-05"
  }
}
```

---

### 🔴 CRITICAL-3: Unicode Encoding в Windows логах

**Приоритет:** P1 - Мешает debugging, но не блокирует обработку
**Статус:** PARTIALLY FIXED (есть workaround, но не полностью)
**Impact:** Логи засорены UnicodeEncodeError, но обработка продолжается

#### Проблема

**Симптом:**
```python
UnicodeEncodeError: 'charmap' codec can't encode character '\U0001f680' in position 5: character maps to <undefined>
```

**Root cause:**
- Windows Console по умолчанию использует CP1251
- Python logging пытается записать emoji и Unicode стрелки
- Colorama не полностью решает проблему

**Места:**
- `am_logging.py` - использует emoji в log_section, log_stage
- `run_mvp.py` - Unicode стрелки в Pipeline описаниях

#### Решение

**Вариант A: Убрать emoji полностью (ПРОСТОЕ)**

**Файл:** `am_logging.py`

```python
# Добавить флаг конфигурации
USE_EMOJI = False  # Установить в False для Windows

STAGE_EMOJI = {
    'structural': '📄' if USE_EMOJI else '[PDF]',
    'structure_detect': '📖' if USE_EMOJI else '[STRUCT]',
    'summarize': '📝' if USE_EMOJI else '[SUMMARY]',
    'extended': '🤖' if USE_EMOJI else '[EXTEND]',
    'finalize': '✅' if USE_EMOJI else '[FINAL]',
    'chunk': '🧩' if USE_EMOJI else '[CHUNK]',
    'embed': '🔢' if USE_EMOJI else '[EMBED]'
}

# Unicode стрелки заменить на ASCII
# Было: "Pipeline: structural → embed"
# Стало: "Pipeline: structural -> embed"
```

**Вариант B: Правильная UTF-8 обработка (ПРАВИЛЬНОЕ)**

**Файл:** `run_mvp.py` (в самом начале)

```python
import sys
import os

# Установить UTF-8 для Windows консоли
if sys.platform == 'win32':
    # Для stdout/stderr
    import io
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer,
        encoding='utf-8',
        errors='replace',
        line_buffering=True
    )
    sys.stderr = io.TextIOWrapper(
        sys.stderr.buffer,
        encoding='utf-8',
        errors='replace',
        line_buffering=True
    )

    # Для Windows Console API
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)  # UTF-8
    except Exception:
        pass
```

**Файл:** `am_logging.py`

```python
def setup_logging(config: dict):
    """Setup logging with proper UTF-8 encoding."""
    log_config = config.get('logging', {})
    level = log_config.get('level', 'INFO')
    format_str = log_config.get('format', '%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # UTF-8 для file handler
    file_handler = logging.FileHandler(
        log_file,
        encoding='utf-8',  # ✓ Добавить encoding
        errors='replace'
    )
    file_handler.setFormatter(logging.Formatter(format_str))

    # Stream handler с безопасным fallback
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(logging.Formatter(format_str))

    # ...
```

#### План действий

1. ✅ Добавить USE_EMOJI config flag
2. ✅ Заменить Unicode стрелки на ASCII
3. ✅ Установить UTF-8 в начале run_mvp.py
4. ✅ Добавить encoding='utf-8' ко всем file handlers
5. ✅ CLI флаг `--no-emoji` для отключения

#### Expected outcome

```
# С emoji (Linux/Mac):
📄 Starting: STRUCTURAL
Pipeline: structural → embed

# Без emoji (Windows):
[PDF] Starting: STRUCTURAL
Pipeline: structural -> embed

# Логи без ошибок:
2025-11-05 12:10:14 - am_structural - INFO - Processing PMBOK
```

---

## 2. Важные улучшения

### 🟡 HIGH-1: WindowsPath subscriptable error

**Приоритет:** P1
**Файл:** `batch_process_library.py`
**Impact:** Весь первый батч упал из-за этой ошибки

#### Проблема

```python
# ТЕКУЩИЙ КОД (предположительно):
pdf_path = Path("some/file.pdf")
something = pdf_path[0]  # ❌ Path объект не subscriptable
```

#### Решение

Нужно найти точное место ошибки. Запросить у пользователя:
- Точную строку кода из batch_process_library.py
- Stack trace ошибки

**Временное решение:** Используется batch_simple.sh

---

### 🟡 HIGH-2: Metadata files не создаются автоматически

**Приоритет:** P2
**Impact:** Требуется ручной fix_missing_metadata.py

#### Проблема

После embedding создаются FAISS индексы, но `.pkl` metadata files отсутствуют.

#### Решение

**Файл:** `am_embed.py:420-430`

```python
# После сохранения FAISS index:
faiss.write_index(index, str(index_path))
logger.info(f"Saved FAISS index: {index_path.name}")

# ✓ Добавить сохранение metadata:
metadata = {
    "chunks": chunks,  # Все чанки
    "book_name": book_name,
    "total_chunks": len(chunks),
    "embedding_dim": vectors.shape[1],
    "created_at": datetime.now().isoformat(),
    "model": self.model_name
}

metadata_path = index_path.with_suffix('.pkl')
with open(metadata_path, 'wb') as f:
    pickle.dump(metadata, f)
logger.info(f"Saved metadata: {metadata_path.name}")
```

---

## 3. Опциональные улучшения

### 🟢 MEDIUM-1: Progress bar для длительных операций

**Приоритет:** P3
**Library:** `tqdm`

```python
from tqdm import tqdm

# В structural extraction:
for page_num in tqdm(range(total_pages), desc="Extracting pages"):
    # ...
```

### 🟢 MEDIUM-2: Config validation при загрузке

**Файл:** `am_common.py`

```python
def validate_config(config: dict) -> List[str]:
    """Валидировать конфигурацию перед запуском."""
    errors = []

    # Проверить LM настройки
    if config.get('extended', {}).get('use_lm'):
        if 'lm_model' not in config['extended']:
            errors.append("extended.lm_model not specified")
        if 'lm_provider' not in config['extended']:
            errors.append("extended.lm_provider not specified")

    # Проверить embedding настройки
    if 'embedding' in config:
        if 'model' not in config['embedding']:
            errors.append("embedding.model not specified")

    return errors
```

### 🟢 MEDIUM-3: Batch processing resume capability

**Файл:** `batch_simple.sh` или новый `batch_process_library_v2.py`

```python
# Сохранять state после каждой книги:
state_file = Path("data/.batch_state.json")

state = {
    "completed": ["book1.pdf", "book2.pdf"],
    "failed": ["book3.pdf"],
    "last_processed": "book2.pdf",
    "timestamp": "2025-11-05T12:00:00"
}

# При запуске - пропустить уже обработанные
```

---

## 4. Тестирование

### Unit Tests (необходимо добавить)

```python
# tests/test_common.py
def test_sanitize_filename_cyrillic():
    assert sanitize_filename("Каган Марти.pdf") == "kagan_marti.pdf"

def test_sanitize_filename_long():
    long_name = "a" * 200 + ".pdf"
    result = sanitize_filename(long_name)
    assert len(result) <= 57  # 50 + 7 for hash + .pdf

def test_sanitize_filename_special_chars():
    assert sanitize_filename("Test®Book™.pdf") == "test_book.pdf"

# tests/test_extended.py
def test_lm_config_loading():
    config = {"extended": {"lm_model": "qwen2.5:7b"}}
    extractor = ExtendedFieldsExtractor(config)
    assert extractor.model == "qwen2.5:7b"
```

### Integration Tests

```bash
# Тест полного пайплайна на маленьком PDF (1-2 страницы):
python run_mvp.py -i tests/fixtures/test_mini.pdf -c config/test.yaml

# Ожидаемый результат:
# - Все 7 этапов выполнены
# - FAISS index создан
# - Metadata .pkl создан
# - 0 Ollama 404 errors
# - Логи без UnicodeEncodeError
```

---

## 5. Приоритизация задач

### Sprint 1: Критические исправления (1-2 дня)

1. ✅ **LM extraction fix** (2-3 часа)
   - Изменить код в am_extended.py
   - Добавить валидацию конфига
   - Unit tests

2. ✅ **Filename sanitization** (3-4 часа)
   - Добавить sanitize_filename()
   - Интегрировать в pipeline
   - Тесты на edge cases

3. ✅ **Unicode encoding fix** (1-2 часа)
   - UTF-8 setup в run_mvp.py
   - USE_EMOJI flag
   - Заменить Unicode стрелки

### Sprint 2: Переобработка данных (6-8 часов)

4. ⏳ **Reprocess все 20 книг**
   - С исправленным LM extraction
   - С короткими именами файлов
   - Проверить quality metrics

5. ⏳ **Пересоздать unified index**
   - С LM-extracted metadata
   - Сравнить качество поиска

### Sprint 3: Улучшения (2-3 дня)

6. ⏳ Metadata auto-save
7. ⏳ Config validation
8. ⏳ Progress bars
9. ⏳ Batch resume capability

---

## 6. Чеклист перед деплоем

### Обязательно:
- [ ] LM extraction работает (0 Ollama 404 errors)
- [ ] Длинные имена обрабатываются автоматически
- [ ] Unicode в логах не вызывает ошибок
- [ ] Metadata files создаются автоматически
- [ ] Unit tests проходят

### Желательно:
- [ ] Config validation добавлена
- [ ] Progress bars добавлены
- [ ] Batch resume работает
- [ ] Документация обновлена

---

## 7. Риски и митигация

| Риск | Вероятность | Воздействие | Митигация |
|------|-------------|-------------|-----------|
| Переобработка займет > 8 часов | Средняя | Средняя | Запускать overnight |
| LM модель qwen2.5:7b медленная | Средняя | Низкая | Можно использовать lighter model |
| Новые баги после рефакторинга | Низкая | Высокая | Extensive testing на test.pdf |
| Sanitized имена конфликтуют | Низкая | Средняя | Hash в конце имени |

---

## 8. Метрики успеха

**После рефакторинга должно быть:**

| Метрика | Текущее | Целевое |
|---------|---------|---------|
| Ollama 404 errors | 4,763 | 0 |
| LM-extracted fields | 0% | 100% |
| Files skipped by batch | 1 (PMBOK) | 0 |
| UnicodeEncodeError в логах | ~50 | 0 |
| Manual interventions | 3 (rename, fix, reindex) | 0 |
| Books successfully processed | 20/21 (95%) | 21/21 (100%) |

---

## 9. Команды для выполнения

### Шаг 1: Backup
```bash
# Сохранить текущие данные
cp -r data data_backup_20251105
git add -A
git commit -m "Snapshot before refactoring"
```

### Шаг 2: Применить исправления
```bash
# Редактировать файлы согласно плану
# am_extended.py, am_common.py, run_mvp.py, am_logging.py
```

### Шаг 3: Тестирование
```bash
# Unit tests
python -m pytest tests/ -v

# Integration test
python run_mvp.py -i tests/fixtures/test_mini.pdf -c config/test.yaml
```

### Шаг 4: Переобработка
```bash
# Удалить старые датасеты (опционально)
rm -rf data/datasets/*
rm -rf data/indexes/faiss/*

# Запустить batch
./batch_simple.sh

# Или с новым скриптом:
python batch_process_library_v2.py --config config/batch_full.yaml
```

---

**Конец плана**

*Готов к выполнению: 2025-11-05*
*Ожидаемое время: 3-5 дней*
*Ответственный: Developer*
