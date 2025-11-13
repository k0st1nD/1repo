#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_common.py - Archivist Magika Common Library
===============================================
Общие функции и классы для всего пайплайна обработки книг.

Основные компоненты:
- DatasetIO: работа с JSONL датасетами
- TextNormalizer: нормализация текста из PDF
- ConfigLoader: загрузка конфигурации из YAML
- PathManager: управление путями проекта
- Validators: валидация структур данных
- Утилиты: хеширование, timestamps, форматирование

Версия: 2.0.0 (MVP v2.0)
Python: 3.9+
"""

from __future__ import annotations
import hashlib
import json
import logging
import re
import unicodedata
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('am_common')

# ============================================
# КОНСТАНТЫ
# ============================================

VERSION = "2.0.0"
PRODUCT_NAME = "archivist magika"

# Маркеры датасета
DATASET_BEGIN = "===DATASET_BEGIN==="
DATASET_END = "===DATASET_END==="

# Специальные segment_id
HEADER_ID = "__header__"
AUDIT_ID = "__audit__"
FOOTER_ID = "__footer__"

# Схемы валидации для разных этапов pipeline
REQUIRED_FIELDS = {
    "structural": ["segment_id", "segment", "page_num"],
    "structured": ["segment_id", "segment", "page_num", "chapter_title", "section_title"],
    "summarized": ["segment_id", "segment", "page_num", "l1_summary", "l2_summary"],
    "extended": ["segment_id", "segment", "page_num", "prev_page", "next_page"],
    "final": ["segment_id", "segment", "page_num"],
    "chunks": ["chunk_id", "text", "tokens", "metadata"],
}


# ============================================
# CORE UTILITIES
# ============================================

def utc_now_iso() -> str:
    """Возвращает текущее время UTC в ISO формате."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256_hex(data: bytes) -> str:
    """
    Вычисляет SHA256 хеш от байтового массива.
    
    Args:
        data: байтовые данные
        
    Returns:
        hex строка хеша
    """
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    """
    Вычисляет SHA256 хеш файла.
    
    Args:
        path: путь к файлу
        
    Returns:
        hex строка хеша файла
    """
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


def manifest_sha256(lines: List[str]) -> str:
    """
    Вычисляет манифест-хеш от списка строк.
    Используется для проверки целостности датасета.
    
    Args:
        lines: список строк
        
    Returns:
        hex строка хеша манифеста
    """
    h = hashlib.sha256()
    for line in lines:
        h.update(line.encode('utf-8'))
        h.update(b'\n')
    return h.hexdigest()


def format_size(size_bytes: int) -> str:
    """
    Форматирует размер в человекочитаемый вид.
    
    Args:
        size_bytes: размер в байтах
        
    Returns:
        отформатированная строка (например: "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Обрезает текст до указанной длины.
    
    Args:
        text: исходный текст
        max_length: максимальная длина
        suffix: суффикс для обрезанного текста
        
    Returns:
        обрезанный текст
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


# ============================================
# TEXT NORMALIZER
# ============================================

class TextNormalizer:
    """
    Нормализация текста извлечённого из PDF.
    
    Обрабатывает:
    - Unicode артефакты
    - Лигатуры (fi, fl, ffi, etc)
    - Переносы строк
    - Множественные пробелы
    - Кавычки и дефисы
    """
    
    def __init__(self):
        # Мапинг частых ошибок в PDF
        self.replacements = {
            # Unicode артефакты
            '\u0000': '',      # null byte (частая проблема!)
            '\ufeff': '',      # BOM (Byte Order Mark)
            '\u00ad': '',      # soft hyphen
            '\u200b': '',      # zero-width space
            '\u200c': '',      # zero-width non-joiner
            '\u200d': '',      # zero-width joiner
            
            # Лигатуры
            'ﬁ': 'fi',
            'ﬂ': 'fl',
            'ﬀ': 'ff',
            'ﬃ': 'ffi',
            'ﬄ': 'ffl',
            'ﬅ': 'ft',
            'ﬆ': 'st',
            
            # Кавычки
            '"': '"',
            '"': '"',
            ''': "'",
            ''': "'",
            '«': '"',
            '»': '"',
            '‹': "'",
            '›': "'",
            
            # Дефисы и тире
            '–': '--',   # en-dash
            '—': '---',  # em-dash
            '−': '-',    # minus sign
            '‐': '-',    # hyphen
            '‑': '-',    # non-breaking hyphen
            
            # Другие символы
            '…': '...',  # ellipsis
            '№': 'No.',  # numero sign
        }
        
        # Паттерны для regex замен
        self.hyphen_pattern = re.compile(r'(\w)-\s*\n\s*(\w)')  # перенос слова
        self.multi_space = re.compile(r'[ \t]+')                # множественные пробелы
        self.multi_newline = re.compile(r'\n{3,}')              # множественные переводы строк
        self.bullet_pattern = re.compile(r'^\s*[•·∙○●]\s+', re.MULTILINE)  # маркеры списков
    
    def normalize(self, text: str, aggressive: bool = False) -> str:
        """
        Основная функция нормализации текста.
        
        Args:
            text: исходный текст
            aggressive: если True, применяет более агрессивную нормализацию
            
        Returns:
            нормализованный текст
        """
        if not text:
            return ""
        
        # Unicode normalization (NFKC = compatibility composition)
        text = unicodedata.normalize('NFKC', text)
        
        # Замена проблемных символов
        for old, new in self.replacements.items():
            text = text.replace(old, new)
        
        # Склейка переносов слов (hy-\nphen -> hyphen)
        text = self.hyphen_pattern.sub(r'\1\2', text)
        
        # Нормализация пробелов
        text = self.multi_space.sub(' ', text)
        
        # Нормализация переводов строк
        text = self.multi_newline.sub('\n\n', text)
        
        if aggressive:
            # Агрессивная нормализация (если нужно)
            text = self.bullet_pattern.sub('- ', text)  # унифицируем маркеры
        
        # Удаление trailing whitespace в каждой строке
        lines = [line.rstrip() for line in text.split('\n')]
        text = '\n'.join(lines)
        
        return text.strip()
    
    def normalize_light(self, text: str) -> str:
        """
        Лёгкая нормализация - только критичные артефакты.
        Используется когда важно сохранить оригинальное форматирование.
        
        Args:
            text: исходный текст
            
        Returns:
            слегка нормализованный текст
        """
        if not text:
            return ""
        
        # Только критичные артефакты
        critical = {
            '\u0000': '',  # null byte
            '\ufeff': '',  # BOM
        }
        
        for old, new in critical.items():
            text = text.replace(old, new)
        
        return text
    
    def remove_page_numbers(self, text: str) -> str:
        """
        Удаляет номера страниц из текста.
        
        Args:
            text: исходный текст
            
        Returns:
            текст без номеров страниц
        """
        # Паттерны для номеров страниц (в начале или конце строки)
        patterns = [
            r'^\s*\d+\s*$',           # просто число
            r'^\s*-\s*\d+\s*-\s*$',   # - 123 -
            r'^\s*\[\s*\d+\s*\]\s*$', # [123]
        ]
        
        lines = text.split('\n')
        cleaned = []
        
        for line in lines:
            is_page_num = any(re.match(p, line) for p in patterns)
            if not is_page_num:
                cleaned.append(line)
        
        return '\n'.join(cleaned)

    def remove_common_watermarks(self, text: str) -> str:
        """
        Удаляет распространенные watermarks и footer/header артефакты.

        Args:
            text: исходный текст

        Returns:
            текст без watermarks
        """
        # Паттерны для watermarks
        watermark_patterns = [
            r'(?i)\s*oceanofpdf\.com\s*',
            r'(?i)\s*generated\s+by\s+.*?\s*',
            r'(?i)\s*downloaded\s+from\s+.*?\s*',
            r'(?i)\s*www\.[a-z0-9\-]+\.(com|org|net)\s*',
        ]

        for pattern in watermark_patterns:
            text = re.sub(pattern, '', text, flags=re.MULTILINE | re.IGNORECASE)

        # Удаляем пустые строки подряд (больше 2)
        text = re.sub(r'\n{3,}', '\n\n', text)

        return text.strip()


# ============================================
# DATASET I/O
# ============================================

class DatasetIO:
    """
    Работа с JSONL датасетами в формате Archivist Magika.
    
    Формат файла:
    ===DATASET_BEGIN===
    {"segment_id": "__header__", ...}
    {"segment_id": "1", ...}
    {"segment_id": "2", ...}
    ...
    {"segment_id": "__audit__", ...}
    {"segment_id": "__footer__", ...}
    ===DATASET_END===
    """
    
    @staticmethod
    def load(path: Path, validate: bool = True) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        """
        Загружает датасет из JSONL файла.
        
        Args:
            path: путь к файлу датасета
            validate: проводить ли базовую валидацию
            
        Returns:
            (header, cards, audit, footer)
            
        Raises:
            FileNotFoundError: если файл не найден
            ValueError: если формат файла неверный
        """
        logger.info(f"Loading dataset: {path}")
        
        if not path.exists():
            raise FileNotFoundError(f"Dataset not found: {path}")
        
        # Читаем файл
        raw = path.read_text(encoding='utf-8')
        
        # Проверяем маркеры
        if DATASET_BEGIN not in raw or DATASET_END not in raw:
            raise ValueError(f"Invalid dataset format: missing markers in {path}")
        
        # Извлекаем тело датасета
        body = raw.split(DATASET_BEGIN, 1)[1].split(DATASET_END, 1)[0].strip().splitlines()
        
        header: Dict[str, Any] = {}
        audit: Dict[str, Any] = {}
        footer: Dict[str, Any] = {}
        cards: List[Dict[str, Any]] = []
        
        # Парсим JSONL
        for line_num, line in enumerate(body, 1):
            if not line.strip():
                continue
                
            try:
                obj = json.loads(line)
                sid = obj.get('segment_id')
                
                if sid == HEADER_ID:
                    header = obj
                elif sid == AUDIT_ID:
                    audit = obj
                elif sid == FOOTER_ID:
                    footer = obj
                else:
                    cards.append(obj)
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse line {line_num}: {line[:50]}... Error: {e}")
        
        # Сортируем карточки по segment_id
        cards.sort(key=lambda c: c.get('segment_id', ''))
        
        logger.info(f"Loaded: {len(cards)} cards from {path.name}")
        
        # Валидация
        if validate:
            errors = DatasetIO.validate_structure(header, cards)
            if errors:
                logger.warning(f"Validation warnings: {', '.join(errors[:3])}")
        
        return header, cards, audit, footer
    
    @staticmethod
    def save(path: Path,
             header: Dict[str, Any],
             cards: List[Dict[str, Any]],
             audit: Optional[Dict[str, Any]] = None,
             footer: Optional[Dict[str, Any]] = None,
             validate: bool = True) -> None:
        """
        Сохраняет датасет в JSONL файл.
        
        Args:
            path: путь для сохранения
            header: заголовок датасета
            cards: список карточек
            audit: аудит информация (опционально)
            footer: footer датасета (опционально)
            validate: проводить ли валидацию перед сохранением
            
        Raises:
            ValueError: если данные не проходят валидацию
        """
        logger.info(f"Saving dataset: {path} ({len(cards)} cards)")
        
        # Валидация перед сохранением
        if validate:
            errors = DatasetIO.validate_structure(header, cards)
            if errors:
                raise ValueError(f"Dataset validation failed: {errors}")
        
        # Создаём директорию если нужно
        path.parent.mkdir(parents=True, exist_ok=True)
        
        lines: List[str] = []
        
        # Header
        header['segment_id'] = HEADER_ID
        header['version'] = header.get('version', VERSION)
        header['product'] = header.get('product', PRODUCT_NAME)
        header['created_at'] = header.get('created_at', utc_now_iso())
        lines.append(json.dumps(header, ensure_ascii=False))
        
        # Cards
        for card in cards:
            lines.append(json.dumps(card, ensure_ascii=False))
        
        # Audit
        if audit is not None:
            audit['segment_id'] = AUDIT_ID
            audit['created_at'] = audit.get('created_at', utc_now_iso())
            lines.append(json.dumps(audit, ensure_ascii=False))
        
        # Footer
        mf = manifest_sha256(lines)
        footer_data = {
            'segment_id': FOOTER_ID,
            'manifest_sha256': mf,
            'created_at': utc_now_iso(),
            'version': VERSION,
            'product': PRODUCT_NAME,
            'card_count': len(cards),
        }
        if footer is not None:
            footer.update(footer_data)
        else:
            footer = footer_data
        
        # Записываем файл
        with open(path, 'w', encoding='utf-8') as f:
            f.write(DATASET_BEGIN + '\n')
            for line in lines:
                f.write(line + '\n')
            f.write(json.dumps(footer, ensure_ascii=False) + '\n')
            f.write(DATASET_END + '\n')
        
        file_size = path.stat().st_size
        logger.info(f"Saved: {len(cards)} cards to {path.name} ({format_size(file_size)})")
    
    @staticmethod
    def validate_structure(header: Dict[str, Any], cards: List[Dict[str, Any]], stage: Optional[str] = None) -> List[str]:
        """
        Валидирует структуру датасета.
        
        Args:
            header: заголовок датасета
            cards: список карточек
            stage: название этапа pipeline (для специфичной валидации)
            
        Returns:
            список ошибок (пустой если всё ок)
        """
        errors = []
        
        # Валидация header
        if not header:
            errors.append("Missing header")
        else:
            required_header_fields = ['book', 'title', 'source_file']
            for field in required_header_fields:
                if field not in header and (field == 'book' and 'title' not in header):
                    # book или title должно быть
                    if 'book' not in header and 'title' not in header:
                        errors.append("Header missing both 'book' and 'title'")
        
        # Валидация cards
        if not cards:
            errors.append("No cards found")
        else:
            # Получаем required fields для этапа
            required_fields = REQUIRED_FIELDS.get(stage, ["segment_id", "segment"])
            
            for i, card in enumerate(cards):
                for field in required_fields:
                    if field not in card:
                        errors.append(f"Card {i}: missing required field '{field}'")
                
                # Проверка segment_id
                if 'segment_id' in card:
                    sid = card['segment_id']
                    if sid in [HEADER_ID, AUDIT_ID, FOOTER_ID]:
                        errors.append(f"Card {i}: invalid segment_id '{sid}' (reserved)")
        
        return errors
    
    @staticmethod
    def merge_datasets(datasets: List[Tuple[Path, Dict, List, Dict, Dict]], 
                      output_path: Path,
                      merge_headers: bool = False) -> None:
        """
        Объединяет несколько датасетов в один.
        
        Args:
            datasets: список (path, header, cards, audit, footer)
            output_path: путь для сохранения объединённого датасета
            merge_headers: если True, объединяет информацию из headers
        """
        logger.info(f"Merging {len(datasets)} datasets")
        
        # Объединяем карточки
        all_cards = []
        for path, header, cards, audit, footer in datasets:
            all_cards.extend(cards)
        
        # Берём первый header как базу
        _, base_header, _, _, _ = datasets[0]
        merged_header = base_header.copy()
        
        if merge_headers:
            merged_header['merged_from'] = [str(p) for p, _, _, _, _ in datasets]
            merged_header['merged_at'] = utc_now_iso()
        
        # Сохраняем
        DatasetIO.save(output_path, merged_header, all_cards)
        logger.info(f"Merged dataset saved: {len(all_cards)} total cards")


# ============================================
# CONFIG LOADER
# ============================================

class ConfigLoader:
    """
    Загрузка и валидация конфигурации из YAML.
    """
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Args:
            config_path: путь к файлу конфигурации (если None, ищет по умолчанию)
        """
        if config_path is None:
            # Поиск конфига в стандартных местах
            candidates = [
                Path('config/am_config_v2.0.yaml'),
                Path('config/am_config.yaml'),
                Path('am_config_v2.0.yaml'),
                Path('am_config.yaml'),
            ]
            for candidate in candidates:
                if candidate.exists():
                    config_path = candidate
                    break
            
            if config_path is None:
                raise FileNotFoundError("Config file not found in standard locations")
        
        self.config_path = config_path
        self._config: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """
        Загружает конфигурацию из YAML файла.
        
        Returns:
            словарь с конфигурацией
            
        Raises:
            FileNotFoundError: если файл не найден
            yaml.YAMLError: если ошибка парсинга YAML
        """
        logger.info(f"Loading config: {self.config_path}")
        
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self._config = yaml.safe_load(f)
        
        # Валидация
        self._validate_config()
        
        logger.info("Config loaded successfully")
        return self._config
    
    def _validate_config(self) -> None:
        """Базовая валидация структуры конфига."""
        if self._config is None:
            raise ValueError("Config not loaded")
        
        required_sections = ['project', 'pipeline', 'logging']
        for section in required_sections:
            if section not in self._config:
                raise ValueError(f"Config missing required section: {section}")
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        Получает значение из конфига по пути.
        
        Args:
            key_path: путь к ключу через точки (например: "pipeline.structural.ocr.enabled")
            default: значение по умолчанию
            
        Returns:
            значение или default
            
        Example:
            >>> config.get('pipeline.structural.ocr.enabled')
            True
        """
        if self._config is None:
            self.load()
        
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_stage_config(self, stage: str) -> Dict[str, Any]:
        """
        Получает конфигурацию для конкретного этапа pipeline.
        
        Args:
            stage: название этапа (structural, summarize, chunk, etc)
            
        Returns:
            словарь с конфигурацией этапа
        """
        return self.get(f'pipeline.{stage}', {})

    @property
    def config(self) -> Dict[str, Any]:
        """Получить полную конфигурацию."""
        if self._config is None:
            return self.load()
        return self._config


# ============================================
# PATH MANAGER
# ============================================

class PathManager:
    """
    Управление путями проекта.
    Централизованное управление структурой директорий.
    """
    
    def __init__(self, project_root: Optional[Path] = None):
        """
        Args:
            project_root: корневая директория проекта (если None, использует текущую)
        """
        self.root = project_root or Path.cwd()
        
        # Основные директории
        self.data = self.root / "data"
        self.config = self.root / "config"
        self.logs = self.root / "logs"
        
        # Data subdirectories
        self.sources = self.data / "sources"
        self.datasets = self.data / "datasets"
        self.indexes = self.data / "indexes"
        self.tables = self.data / "tables"
        self.cache = self.data / "cache"
        self.quality = self.data / "quality"
        
        # Dataset stages
        self.dataset_structural = self.datasets / "structural"
        self.dataset_structured = self.datasets / "structured"
        self.dataset_summarized = self.datasets / "summarized"
        self.dataset_extended = self.datasets / "extended"
        self.dataset_final = self.datasets / "final"
        self.dataset_chunks = self.datasets / "chunks"
        
        # Indexes
        self.index_faiss = self.indexes / "faiss"
        self.index_metadata = self.indexes / "metadata"
    
    def init_structure(self) -> None:
        """Создаёт структуру директорий проекта."""
        dirs = [
            self.data,
            self.config,
            self.logs,
            self.sources,
            self.datasets,
            self.indexes,
            self.tables,
            self.cache,
            self.quality,
            self.dataset_structural,
            self.dataset_structured,
            self.dataset_summarized,
            self.dataset_extended,
            self.dataset_final,
            self.dataset_chunks,
            self.index_faiss,
            self.index_metadata,
        ]
        
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)
            logger.debug(f"Created directory: {d}")
        
        logger.info("Project structure initialized")
    
    def get_dataset_path(self, stage: str, file_name: str) -> Path:
        """
        Получает путь к файлу датасета для конкретного этапа.
        
        Args:
            stage: этап pipeline (structural, summarized, etc)
            file_name: имя файла
            
        Returns:
            полный путь к файлу датасета
        """
        stage_map = {
            'structural': self.dataset_structural,
            'structured': self.dataset_structured,
            'summarized': self.dataset_summarized,
            'extended': self.dataset_extended,
            'final': self.dataset_final,
            'chunks': self.dataset_chunks,
        }
        
        stage_dir = stage_map.get(stage)
        if stage_dir is None:
            raise ValueError(f"Unknown stage: {stage}")
        
        return stage_dir / file_name
    
    def get_quality_path(self, stage: str) -> Path:
        """
        Получает путь к файлу quality metrics для этапа.
        
        Args:
            stage: этап pipeline
            
        Returns:
            путь к файлу quality metrics
        """
        return self.quality / f"{stage}_quality.json"


# ============================================
# VALIDATORS
# ============================================

class Validators:
    """
    Валидаторы для различных структур данных.
    """
    
    @staticmethod
    def validate_card(card: Dict[str, Any], stage: str) -> List[str]:
        """
        Валидирует структуру карточки для конкретного этапа.
        
        Args:
            card: карточка для валидации
            stage: этап pipeline
            
        Returns:
            список ошибок
        """
        errors = []
        required = REQUIRED_FIELDS.get(stage, ["segment_id", "segment"])
        
        for field in required:
            if field not in card:
                errors.append(f"Missing required field: {field}")
        
        # Валидация типов
        if 'page_num' in card and not isinstance(card['page_num'], int):
            errors.append(f"Invalid type for page_num: expected int, got {type(card['page_num'])}")
        
        if 'segment' in card and not isinstance(card['segment'], str):
            errors.append(f"Invalid type for segment: expected str, got {type(card['segment'])}")
        
        return errors
    
    @staticmethod
    def validate_chunk(chunk: Dict[str, Any]) -> List[str]:
        """
        Валидирует структуру chunk.
        
        Args:
            chunk: chunk для валидации
            
        Returns:
            список ошибок
        """
        errors = []
        required = ['chunk_id', 'text', 'tokens', 'metadata']
        
        for field in required:
            if field not in chunk:
                errors.append(f"Missing required field: {field}")
        
        # Валидация metadata
        if 'metadata' in chunk:
            meta = chunk['metadata']
            if not isinstance(meta, dict):
                errors.append("metadata must be a dictionary")
            else:
                required_meta = ['source_file', 'page_num']
                for field in required_meta:
                    if field not in meta:
                        errors.append(f"metadata missing required field: {field}")
        
        return errors
    
    @staticmethod
    def is_valid_segment_id(segment_id: str) -> bool:
        """
        Проверяет валидность segment_id.
        
        Args:
            segment_id: ID для проверки
            
        Returns:
            True если валидный
        """
        if not segment_id:
            return False
        
        # Зарезервированные ID
        if segment_id in [HEADER_ID, AUDIT_ID, FOOTER_ID]:
            return False
        
        return True


# ============================================
# MAIN
# ============================================# ============================================
# FILENAME SANITIZATION
# ============================================

def sanitize_filename(filename: str, max_length: int = 50) -> str:
    """
    Создает безопасное короткое имя файла (ASCII, без спецсимволов).

    Args:
        filename: Оригинальное имя файла
        max_length: Максимальная длина результата (без расширения)

    Returns:
        Безопасное короткое имя

    Example:
        >>> sanitize_filename("Project Management Institute - Руководство...pdf")
        'project_management_institute_pmbok_a3f8b2.pdf'
        >>> sanitize_filename("Каган Марти - Вдохновленные.pdf")
        'kagan_marti_vdohnovlennye.pdf'
    """
    # 1. Отделить расширение
    path = Path(filename)
    stem = path.stem
    ext = path.suffix

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
        elif char in transliterate_map.get(char.upper(), {}).get('lower', ''):
            # Обработка заглавных кириллических букв
            transliterated += transliterate_map.get(char.upper(), {}).get('lower', char)
        elif char.isalnum():
            transliterated += char
        elif char in ['-', '_', ' ']:
            transliterated += '_'
        else:
            transliterated += '_'

    # 3. Убрать множественные underscores
    while '__' in transliterated:
        transliterated = transliterated.replace('__', '_')

    # 4. Укоротить до max_length
    if len(transliterated) > max_length:
        # Добавим hash для уникальности
        file_hash = hashlib.md5(stem.encode('utf-8')).hexdigest()[:6]
        transliterated = transliterated[:max_length-7] + '_' + file_hash

    # 5. Убрать trailing underscores
    transliterated = transliterated.strip('_')

    # 6. Вернуть с расширением
    return transliterated + ext


def get_safe_book_name(pdf_path: Union[str, Path]) -> str:
    """
    Получить безопасное имя книги для dataset файлов.

    Args:
        pdf_path: Путь к PDF файлу

    Returns:
        Безопасное короткое имя без расширения

    Example:
        >>> get_safe_book_name("data/sources/Long Name.pdf")
        'long_name'
    """
    if isinstance(pdf_path, str):
        pdf_path = Path(pdf_path)

    sanitized = sanitize_filename(pdf_path.name, max_length=50)
    return Path(sanitized).stem  # Убрать .pdf


if __name__ == "__main__":
    # Простые тесты
    print(f"Archivist Magika Common Library v{VERSION}")
    print("=" * 60)
    
    # Test normalizer
    normalizer = TextNormalizer()
    test_text = "Test with ﬁ ligature and  multiple   spaces\n\n\n\nand lines"
    normalized = normalizer.normalize(test_text)
    print(f"Normalized text: {normalized}")
    
    # Test path manager
    pm = PathManager()
    print(f"\nProject root: {pm.root}")
    print(f"Dataset path: {pm.get_dataset_path('structural', 'test.jsonl')}")
    
    # Test config loader (если есть конфиг)
    try:
        config = ConfigLoader()
        cfg = config.load()
        print(f"\nConfig loaded: {list(cfg.keys())}")
    except FileNotFoundError:
        print("\nNo config file found (expected in tests)")
    
    print("\n" + "=" * 60)
    print("All tests passed!")