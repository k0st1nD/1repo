# 🚀 Archivist Magika - Quick Start Guide (Windows/PowerShell)

## Пошаговая инструкция запуска

### ✅ Шаг 0: Проверка готовности

```powershell
# Проверь что у тебя есть:
Get-ChildItem data\sources\  # Твои PDF/книги
Get-ChildItem config\        # Конфигурационные файлы
Get-ChildItem *.py           # Python модули

# Проверь Python
python --version  # Должно быть Python 3.8+

# Проверь Ollama (если используешь LM)
ollama list
```

---

## 📁 Шаг 1: Структура директорий

```powershell
# Создай структуру одной командой
$dirs = @(
    'data\sources',
    'data\datasets\structural',
    'data\datasets\structured',
    'data\datasets\summarized',
    'data\datasets\extended',
    'data\datasets\final',
    'data\datasets\chunks',
    'data\indexes\faiss',
    'data\indexes\metadata',
    'data\quality',
    'data\cache',
    'logs',
    'config'
)

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}

Write-Host "✅ Directories created!" -ForegroundColor Green
```

**Или создавай по одной:**
```powershell
New-Item -ItemType Directory -Force -Path data\sources
New-Item -ItemType Directory -Force -Path data\datasets\structural
# ... и т.д.
```

---

## 📚 Шаг 2: Положи книги в sources

```powershell
# Скопируй PDF файлы
Copy-Item C:\Users\YourName\Downloads\*.pdf data\sources\

# Или перетащи файлы в проводнике в папку data\sources\

# Проверь что файлы на месте
Get-ChildItem data\sources\ | Format-Table Name, @{Label="Size MB";Expression={[math]::Round($_.Length/1MB, 2)}}
```

**Пример вывода:**
```
Name                     Size MB
----                     -------
python_cookbook.pdf         12.5
docker_deep_dive.pdf         8.3
kubernetes_in_action.pdf    15.7
```

---

## ⚙️ Шаг 3: Выбери конфиг

### Вариант A: Быстрый запуск (для начала) 🚀

```powershell
# Используй fast режим для первой попытки
python run_mvp.py -i data\sources\python_cookbook.pdf -c config\mvp_fast.yaml
```

**Преимущества:**
- ⚡ Быстро (~1-2 минуты)
- 💾 Мало памяти (~2-4 GB)
- ✅ Проверишь что всё работает

**Минусы:**
- ⚠️ Нет OCR (только native PDF)
- ⚠️ Минимум метаданных

---

### Вариант B: Сбалансированный (рекомендуется) ⭐

```powershell
# Используй основной конфиг
python run_mvp.py -i data\sources\python_cookbook.pdf

# Или явно укажи конфиг
python run_mvp.py -i data\sources\python_cookbook.pdf -c config\mvp.yaml
```

**Преимущества:**
- ✅ OCR включён (для сканов)
- ✅ Метаданные извлекаются (LM 7b)
- ⚖️ Баланс скорость/качество

**Требования:**
- 💾 ~6-8 GB RAM
- 🐋 Ollama с qwen2.5:7b
- ⏱️ ~5-10 минут

---

### Вариант C: Максимальное качество 🎯

```powershell
# Для важных документов
python run_mvp.py -i data\sources\important_book.pdf -c config\mvp_quality.yaml
```

**Преимущества:**
- ⭐ Лучшее качество
- 📊 Все метаданные
- 🔍 Hybrid search

**Требования:**
- 💾 ~12-16 GB RAM
- 🐋 Ollama с qwen2.5:14b
- ⏱️ ~15-30 минут

---

## 🚀 Шаг 4: ЗАПУСК!

### Вариант 1: Одна книга

```powershell
# Самый простой запуск (использует mvp.yaml по умолчанию)
python run_mvp.py -i data\sources\your_book.pdf
```

### Вариант 2: Batch - все книги сразу

```powershell
# Обработать все PDF в директории
python run_mvp.py -i data\sources\ --batch
```

### Вариант 3: С выбором конфига

```powershell
# Fast mode для всех книг
python run_mvp.py -i data\sources\ --batch -c config\mvp_fast.yaml

# Quality mode для всех книг
python run_mvp.py -i data\sources\ --batch -c config\mvp_quality.yaml
```

### Вариант 4: Dry run (проверка без выполнения)

```powershell
# Проверь что будет выполнено (без реального запуска)
python run_mvp.py -i data\sources\book.pdf --dry-run
```

---

## 📊 Шаг 5: Мониторинг процесса

Во время работы ты увидишь:

```
============================================================
  🚀 archivist magika 2.0.0
============================================================
Quality check: enabled
Validation: enabled

Processing: python_cookbook.pdf
Pipeline: structural → embed
Stages: structural → structure_detect → summarize → extended → finalize → chunk → embed

============================================================
  📄 Starting: STRUCTURAL
============================================================
Processing pages: 100%|████████████| 257/257 [00:45<00:00, 5.71it/s]
✓ Quality check passed
============================================================
  📄 Completed: STRUCTURAL
============================================================

[... остальные стадии ...]

============================================================
  📊 FINAL REPORTS
============================================================

Performance Summary:
  structural: 45.2s
  chunk: 12.3s
  embed: 23.1s

Quality Report:
  Pass rate: 100.0%

============================================================
  ✅ PIPELINE COMPLETED SUCCESSFULLY
============================================================
```

---

## 🔍 Шаг 6: Проверка результатов

```powershell
# Проверь что создалось
Get-ChildItem data\datasets\final\*.jsonl
Get-ChildItem data\indexes\faiss\*.faiss
Get-ChildItem data\indexes\metadata\*.json

# Посмотри логи
Get-Content logs\pipeline.log -Tail 50

# Качество
Get-Content data\quality\quality_report_latest.json | ConvertFrom-Json | ConvertTo-Json -Depth 10
```

**Ожидаемые файлы:**
```
data\
├── datasets\
│   ├── structural\
│   │   └── python_cookbook.dataset.jsonl
│   ├── final\
│   │   └── python_cookbook.dataset.jsonl
│   └── chunks\
│       └── python_cookbook.chunks.jsonl
├── indexes\
│   ├── faiss\
│   │   └── python_cookbook.faiss
│   └── metadata\
│       └── python_cookbook.json
└── quality\
    └── quality_report_latest.json
```

---

## 🔍 Шаг 7: Поиск (Search)

После обработки можно искать:

```powershell
# Semantic search
python rag\search.py -q "how to use decorators in python" -i python_cookbook

# С фильтрами
python rag\search.py -q "docker networking" -i docker_deep_dive --chapter "Chapter 5"

# Top-K results
python rag\search.py -q "kubernetes deployment" -i kubernetes_in_action -k 20
```

---

## 🛠️ Troubleshooting

### Проблема 1: Ollama не запущен

**Ошибка:**
```
ConnectionError: Failed to connect to Ollama at http://localhost:11434
```

**Решение:**
```powershell
# Запусти Ollama (в отдельном окне PowerShell)
ollama serve

# В другом окне, загрузи модель
ollama pull qwen2.5:7b

# Проверь
ollama list
```

---

### Проблема 2: Не хватает памяти

**Ошибка:**
```
MemoryError: Cannot allocate memory
```

**Решение:**
```powershell
# Используй fast режим
python run_mvp.py -i book.pdf -c config\mvp_fast.yaml

# Или отключи LM в конфиге
# В config\mvp.yaml измени:
# extended:
#   lm_extraction:
#     enabled: false
#     heuristics_only: true
```

---

### Проблема 3: OCR не работает (Tesseract)

**Ошибка:**
```
TesseractNotFoundError: tesseract is not installed
```

**Решение Windows:**
```powershell
# 1. Скачай Tesseract installer:
# https://github.com/UB-Mannheim/tesseract/wiki

# 2. Установи (например в C:\Program Files\Tesseract-OCR)

# 3. Добавь в PATH
$env:PATH += ";C:\Program Files\Tesseract-OCR"

# Или добавь постоянно через System Properties > Environment Variables

# 4. Проверь
tesseract --version
```

**Альтернатива: Отключить OCR**
```powershell
# Используй fast режим (OCR выключен)
python run_mvp.py -i book.pdf -c config\mvp_fast.yaml
```

---

### Проблема 4: Модули не найдены

**Ошибка:**
```
ModuleNotFoundError: No module named 'am_common'
```

**Решение:**
```powershell
# Убедись что все файлы в одной директории
Get-ChildItem *.py | Select-Object Name

# Должны быть:
# am_common.py
# am_logging.py
# am_structural_robust.py
# ... и т.д.

# Запускай из корня проекта
Set-Location C:\path\to\archivist_magika
python run_mvp.py -i data\sources\book.pdf
```

---

### Проблема 5: Python packages отсутствуют

**Ошибка:**
```
ModuleNotFoundError: No module named 'pdfminer'
```

**Решение:**
```powershell
# Установи зависимости
pip install pdfminer.six
pip install pdfplumber
pip install pypdf2
pip install pytesseract
pip install faiss-cpu
pip install sentence-transformers
pip install tqdm
pip install pyyaml
pip install colorama

# Или все сразу (если есть requirements.txt)
pip install -r requirements.txt
```

---

## 📋 Полный пример запуска (PowerShell)

```powershell
# 1. Перейди в директорию проекта
Set-Location C:\projects\archivist_magika

# 2. Создай структуру
$dirs = @('data\sources', 'data\datasets\structural', 'data\datasets\final', 
          'data\datasets\chunks', 'data\indexes\faiss', 'data\indexes\metadata',
          'data\quality', 'logs', 'config')
$dirs | ForEach-Object { New-Item -ItemType Directory -Force -Path $_ | Out-Null }

# 3. Копируй книги
Copy-Item "$env:USERPROFILE\Downloads\*.pdf" data\sources\

# 4. Проверь книги
Get-ChildItem data\sources\

# 5. ТЕСТОВЫЙ запуск с fast режимом
python run_mvp.py -i data\sources\test_book.pdf -c config\mvp_fast.yaml

# 6. Если всё ОК, запусти batch с основным конфигом
python run_mvp.py -i data\sources\ --batch

# 7. Поиск
python rag\search.py -q "your question" -i test_book
```

---

## 🎯 Рекомендуемая последовательность

### День 1: Первый тест

```powershell
# 1. Один PDF в fast режиме (1-2 минуты)
python run_mvp.py -i data\sources\small_book.pdf -c config\mvp_fast.yaml

# 2. Проверь результат
Get-ChildItem data\indexes\faiss\

# 3. Попробуй поиск
python rag\search.py -q "test query" -i small_book
```

### День 2: Полный запуск

```powershell
# 1. Batch обработка в balanced режиме
python run_mvp.py -i data\sources\ --batch

# 2. Проверь качество
Get-Content data\quality\quality_report_latest.json | ConvertFrom-Json
```

### День 3: Оптимизация

```powershell
# Если нужно больше качества
python run_mvp.py -i data\sources\important.pdf -c config\mvp_quality.yaml

# Если нужна скорость
python run_mvp.py -i data\sources\ --batch -c config\mvp_fast.yaml
```

---

## 🚦 Статусы выполнения

### ✅ Успешное выполнение

```
✅ PIPELINE COMPLETED SUCCESSFULLY
```

Файлы созданы:
- ✅ data\datasets\final\book.dataset.jsonl
- ✅ data\indexes\faiss\book.faiss
- ✅ data\indexes\metadata\book.json

### ⚠️ Частичное выполнение

```
⚠️ PIPELINE PARTIALLY COMPLETED
Some stages failed but others succeeded
```

Проверь логи:
```powershell
Get-Content logs\pipeline.log -Tail 100
```

### ❌ Ошибка

```
❌ Pipeline failed: <error message>
```

Действия:
1. Проверь логи
2. Проверь что Ollama запущен (если нужен LM)
3. Попробуй fast режим
4. Смотри раздел Troubleshooting

---

## 📊 Мониторинг ресурсов

### Проверка памяти

```powershell
# Доступная память
Get-WmiObject -Class Win32_OperatingSystem | 
    Select-Object @{Name="Free RAM (GB)";Expression={[math]::Round($_.FreePhysicalMemory/1MB, 2)}}

# Использование процессом Python
Get-Process python | Select-Object Name, @{Name="Memory (MB)";Expression={[math]::Round($_.WorkingSet/1MB, 2)}}
```

### Логи в реальном времени

```powershell
# Следи за логами (Ctrl+C для остановки)
Get-Content logs\pipeline.log -Wait -Tail 20
```

---

## 🎨 PowerShell Aliases (опционально)

Создай для удобства:

```powershell
# Добавь в $PROFILE
notepad $PROFILE

# Вставь:
function Run-Archivist {
    param(
        [string]$Input,
        [string]$Config = "config\mvp.yaml"
    )
    python run_mvp.py -i $Input -c $Config
}

function Search-Archivist {
    param(
        [string]$Query,
        [string]$Index
    )
    python rag\search.py -q $Query -i $Index
}

# Использование:
# Run-Archivist -Input "data\sources\book.pdf"
# Search-Archivist -Query "test" -Index "book"
```

---

## 📝 Финальный Checklist

Перед запуском проверь:

- [ ] Python 3.8+ установлен
- [ ] Все .py файлы в директории проекта
- [ ] Конфиги в config\ директории
- [ ] PDF файлы в data\sources\
- [ ] Структура директорий создана
- [ ] Ollama запущен (если нужен LM)
- [ ] qwen2.5:7b загружен (если нужен LM)
- [ ] Tesseract установлен (если нужен OCR)
- [ ] Python packages установлены

---

## 🚀 Готов к запуску!

```powershell
# ПОЕХАЛИ! 🎉
python run_mvp.py -i data\sources\your_first_book.pdf

# Или batch:
python run_mvp.py -i data\sources\ --batch
```

---

## 📞 Поддержка

Если что-то не работает:

1. Проверь логи: `Get-Content logs\pipeline.log`
2. Проверь Troubleshooting выше
3. Попробуй --dry-run для диагностики
4. Используй fast режим для проверки базовой работы

**Удачи с Archivist Magika! 📚✨**

---

**Version:** 2.0.0  
**Platform:** Windows 10/11, PowerShell 5.1+  
**Date:** 2025-10-30
