# Source Files Validation Guide
## Archivist Magika v2.0

**Дата:** 2025-11-05
**Версия:** 1.0

---

## Проблемы с исходными файлами

### 1. Спецсимволы (Special Characters) ⚠️ КРИТИЧНО

**Проблема:** Windows/FAISS не может создать файлы с некоторыми символами в путях.

**Опасные символы:**
- `®` - Registered trademark (найдено в: `baza-znanij-safe®-russia.pdf`)
- `©` - Copyright
- `™` - Trademark
- `<>:"/\|?*` - Зарезервированы в Windows
- `°±×÷` - Математические символы
- `€£¥` - Валюты

**Симптомы:**
```
FileNotFoundError: 'data\\indexes\\faiss\\baza-znanij-safe®-russia.dataset.faiss'
```

**Решение:**
- Заменить символы на безопасные: `®` → `r`, `©` → `c`, `™` → `tm`
- Использовать `validate_sources.py` для автоматического переименования

---

### 2. Длинные имена файлов ⚠️ ВАЖНО

**Проблема:** Windows имеет ограничение на длину полного пути (260 символов).

**Примеры проблемных файлов:**
```
data-driven-organization-design-sustaining-the-competitive-edge... (113 chars)
Team_Topologies_Organizing_Business_and_Technology_Teams... (105 chars)
```

**Путь к файлу может быть:**
```
c:\scripts\1repo\data\indexes\faiss\data-driven-organization-design...dataset.faiss
```

**Симптомы:**
- Файлы пропускаются bash скриптом
- FAISS не может создать индекс
- OSError: [WinError 206] The filename or extension is too long

**Решение:**
- Сократить имя до 50-100 символов
- Добавить MD5 hash для уникальности
- Пример: `data_driven_organization_design_c906b8.pdf`

---

### 3. Множественные пробелы

**Проблема:** Bash escaping и читаемость.

**Пример:**
```
"Good  Strategy  Bad  Strategy.pdf"  # 2+ пробела подряд
```

**Решение:**
- Заменить множественные пробелы одним: `  ` → ` `
- Или заменить все пробелы на `_`

---

### 4. Кириллица в именах файлов

**Проблема:** Не критична для pipeline, но может вызывать проблемы в некоторых системах.

**Примеры:**
```
Каган Марти - Вдохновленные - 2020.pdf
Ядро 2025-08-29.pdf
```

**Когда проблемно:**
- Git на Windows с неправильной кодировкой
- Некоторые CI/CD системы
- FTP серверы

**Решение:**
- Транслитерация: `Каган` → `kagan`
- Или оставить как есть (pipeline поддерживает)

---

### 5. Повреждённые PDF файлы

**Проблема:** PDF не читается или содержит ошибки.

**Симптомы:**
```
pypdf.errors.PdfReadError: EOF marker not found
```

**Проверка:**
```python
import PyPDF2
with open('file.pdf', 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    print(f"Pages: {len(reader.pages)}")
```

**Решение:**
- Переконвертировать PDF
- Использовать PDF repair tools
- Заменить файл

---

### 6. Дубликаты имён файлов

**Проблема:** Два разных PDF с одинаковым именем (в разных папках или после переименования).

**Симптомы:**
- Перезапись данных
- Потеря одного из файлов

**Решение:**
- Проверять на дубликаты перед обработкой
- Добавлять suffix: `_v2`, `_2021`, `_ru`, и т.д.

---

### 7. Недоступность файлов (Permissions)

**Проблема:** Файл открыт в другой программе или нет прав.

**Симптомы:**
```
PermissionError: [WinError 32] The process cannot access the file...
```

**Решение:**
- Закрыть PDF reader (Adobe, Foxit, и т.д.)
- Проверить права доступа
- Использовать `with open()` для автоматического закрытия

---

## Использование валидатора

### Быстрая проверка:

```bash
python tools/validate_sources.py
```

### С автоматическим переименованием:

```bash
python tools/validate_sources.py --auto-rename
```

### Неинтерактивный режим:

```bash
python tools/validate_sources.py --non-interactive
```

### Кастомная директория:

```bash
python tools/validate_sources.py -d /path/to/pdfs
```

---

## Примеры вывода

### Нет проблем:

```
============================================================
  SOURCE FILES VALIDATION
============================================================
Source directory: data\sources

Found 21 PDF files

[OK] All files passed validation!
```

### Найдены проблемы:

```
============================================================
  SOURCE FILES VALIDATION
============================================================
Source directory: data\sources

Found 21 PDF files

[WARNING] ISSUES FOUND:

FILE: baza-znanij-safe®-russia.pdf
   [!] UNSAFE_CHARS: Found: '®'
   --> Suggested: baza_znanij_safer_russia.pdf

FILE: data-driven-organization-design-sustaining...pdf
   [!] LONG_FILENAME: 113 characters (max: 100)
   --> Suggested: data_driven_organization_design_sustaining_c906b8.pdf

============================================================
  RENAME SUGGESTIONS
============================================================

Found 2 files that should be renamed:

1. baza-znanij-safe®-russia.pdf
   → baza_znanij_safer_russia.pdf

2. data-driven-organization-design-sustaining...pdf
   → data_driven_organization_design_sustaining_c906b8.pdf

Options:
  [1] Rename all automatically
  [2] Show detailed plan (no changes)
  [3] Skip and continue anyway (may cause errors)
  [4] Abort processing

Your choice [1-4]:
```

---

## Интеграция в pipeline

### В начале batch скрипта:

```bash
#!/usr/bin/bash

# Validate sources before processing
echo "Validating source files..."
python tools/validate_sources.py

if [ $? -ne 0 ]; then
    echo "Validation failed. Please fix issues or use --auto-rename"
    exit 1
fi

# Continue with batch processing
# ...
```

### В Python коде:

```python
from tools.validate_sources import SourceValidator

# Before processing
validator = SourceValidator(source_dir='data/sources')
result = validator.validate_all()

if result['status'] != 'ok':
    print("Source validation failed!")
    if result.get('renames'):
        # Handle renames
        validator._execute_renames(result['renames'])
```

---

## Чек-лист перед batch processing

- [ ] Все PDF файлы доступны (не открыты в других программах)
- [ ] Имена файлов < 100 символов
- [ ] Нет спецсимволов (®©™ и т.д.)
- [ ] Нет множественных пробелов
- [ ] Нет дубликатов имён
- [ ] Все PDF читаемые (не повреждены)
- [ ] Запущена валидация: `python tools/validate_sources.py`

---

## Рекомендации по именованию

### ✅ Хорошие имена:

```
2024_final_dora_report.pdf
agile_metrics_in_action.pdf
data_science_for_business.pdf
pmbok_7ed_2021.pdf
```

### ❌ Проблемные имена:

```
baza-znanij-safe®-russia.pdf                    # Спецсимвол ®
Project Management Institute - Руководство...   # Слишком длинное (147 chars)
Good  Strategy  Bad  Strategy.pdf               # Множественные пробелы
<Report>_2024.pdf                               # < и > зарезервированы
```

### Шаблон безопасного имени:

```
<topic>_<author>_<year>.pdf
<topic>_<edition>_<year>.pdf
<abbreviated_title>_<hash>.pdf
```

**Примеры:**
```
balanced_scorecard_norton_kaplan.pdf
pmbok_7ed_2021.pdf
team_topologies_skelton_2019.pdf
data_driven_org_design_c906b8.pdf  # С хешем для уникальности
```

---

## Troubleshooting

### Валидатор не находит проблему

**Причина:** Файл уже был переименован вручную.

**Проверка:**
```bash
ls -la data/sources/*.pdf
```

### Валидатор падает с UnicodeEncodeError

**Причина:** Windows Console использует CP1251 вместо UTF-8.

**Решение:**
```bash
# В PowerShell:
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Или используйте UTF-8 версию скрипта
chcp 65001
python tools/validate_sources.py
```

### Переименование не помогло

**Причина:** Dataset файлы уже созданы со старым именем.

**Решение:**
```bash
# Удалить старые datasets
rm data/datasets/**/*old_name*

# Переобработать с новым именем
python run_mvp.py -i "data/sources/new_name.pdf" -c config/batch_full.yaml
```

---

## Статистика по текущей библиотеке

**Проанализировано:** 21 PDF файл

**Проблемы найдены:**
- Спецсимволы: 1 файл (`baza-znanij-safe®-russia.pdf` - ИСПРАВЛЕНО)
- Длинные имена: 2 файла (>100 chars)
- Кириллица: 3 файла (не критично)

**Статус:** ✅ Все критические проблемы исправлены

---

**Конец руководства**

*Версия 1.0*
*Дата: 2025-11-05*
*Автор: Claude Code*
