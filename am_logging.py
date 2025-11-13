#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
am_logging.py - Archivist Magika Logging Configuration (v2.0)
==============================================================
Enhanced centralized logging for the entire pipeline.

Features:
- Colored console output (optional)
- Log file rotation
- Structured logging (JSON format)
- Performance tracking with decorators
- Context managers for operations
- Progress bar integration (tqdm)
- Error aggregation and reporting
- Pipeline stage tracking

Version: 2.0.0
Python: 3.9+
Dependencies: colorama (optional), tqdm (optional)
"""

from __future__ import annotations
import logging
import sys
import json
import time
import functools
from contextlib import contextmanager
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any, Callable, Generator
from datetime import datetime, timezone
from collections import defaultdict

try:
    from colorama import Fore, Style, init as colorama_init
    colorama_init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

try:
    from tqdm import tqdm
    TQDM_AVAILABLE = True
except ImportError:
    TQDM_AVAILABLE = False


# ============================================
# CONSTANTS
# ============================================

VERSION = "2.0.0"

# Default format strings
DEFAULT_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DETAILED_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
JSON_FORMAT = '%(message)s'  # For structured logging


# ============================================
# STRUCTURED LOGGING
# ============================================

class StructuredMessage:
    """
    Structured log message with metadata.
    Automatically serialized to JSON.
    """
    
    def __init__(self, message: str, **kwargs):
        self.message = message
        self.metadata = kwargs
    
    def __str__(self):
        data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'message': self.message,
            **self.metadata
        }
        return json.dumps(data, ensure_ascii=False, default=str)


class StructuredLogger:
    """Wrapper for structured logging."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
    
    def debug(self, message: str, **kwargs):
        self.logger.debug(StructuredMessage(message, level='DEBUG', **kwargs))
    
    def info(self, message: str, **kwargs):
        self.logger.info(StructuredMessage(message, level='INFO', **kwargs))
    
    def warning(self, message: str, **kwargs):
        self.logger.warning(StructuredMessage(message, level='WARNING', **kwargs))
    
    def error(self, message: str, **kwargs):
        self.logger.error(StructuredMessage(message, level='ERROR', **kwargs))
    
    def critical(self, message: str, **kwargs):
        self.logger.critical(StructuredMessage(message, level='CRITICAL', **kwargs))


# ============================================
# COLORED FORMATTER
# ============================================

class ColoredFormatter(logging.Formatter):
    """Formatter with colors for console output."""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT,
    }
    
    COMPONENT_COLORS = {
        'am_structural': Fore.BLUE,
        'am_structure_detect': Fore.MAGENTA,
        'am_summarize': Fore.CYAN,
        'am_extended': Fore.YELLOW,
        'am_finalize': Fore.GREEN,
        'am_chunk': Fore.BLUE,
        'am_embed': Fore.MAGENTA,
        'search': Fore.CYAN,
    }
    
    def format(self, record):
        if COLORAMA_AVAILABLE:
            # Color level name
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{Style.RESET_ALL}"
            
            # Color component name
            name = record.name
            for component, color in self.COMPONENT_COLORS.items():
                if component in name:
                    record.name = f"{color}{name}{Style.RESET_ALL}"
                    break
        
        return super().format(record)


# ============================================
# JSON FORMATTER
# ============================================

class JSONFormatter(logging.Formatter):
    """Formatter for structured JSON logs."""
    
    def format(self, record):
        # If already structured message, use as-is
        if isinstance(record.msg, StructuredMessage):
            return str(record.msg)
        
        # Otherwise, create structured format
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


# ============================================
# PERFORMANCE TRACKING
# ============================================

class PerformanceTracker:
    """Track performance metrics for operations."""
    
    def __init__(self):
        self.metrics: Dict[str, list] = defaultdict(list)
    
    def record(self, operation: str, duration: float, **metadata):
        """Record operation duration."""
        self.metrics[operation].append({
            'duration': duration,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **metadata
        })
    
    def get_stats(self, operation: str) -> Dict[str, Any]:
        """Get statistics for operation."""
        if operation not in self.metrics or not self.metrics[operation]:
            return {}
        
        durations = [m['duration'] for m in self.metrics[operation]]
        return {
            'count': len(durations),
            'total': sum(durations),
            'avg': sum(durations) / len(durations),
            'min': min(durations),
            'max': max(durations),
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all operations."""
        return {
            op: self.get_stats(op)
            for op in self.metrics.keys()
        }
    
    def reset(self):
        """Reset all metrics."""
        self.metrics.clear()


# Global performance tracker
_performance_tracker = PerformanceTracker()


def log_performance(operation: str = None):
    """
    Decorator to log function execution time.
    
    Args:
        operation: Operation name (default: function name)
    
    Example:
        @log_performance('process_page')
        def process_page(page_num):
            ...
    """
    def decorator(func: Callable) -> Callable:
        op_name = operation or func.__name__
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = logging.getLogger(func.__module__)
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Record metrics
                _performance_tracker.record(op_name, duration, status='success')
                
                # Log
                logger.debug(f"{op_name} completed in {duration:.2f}s")
                
                return result
            
            except Exception as e:
                duration = time.time() - start_time
                _performance_tracker.record(op_name, duration, status='failed', error=str(e))
                logger.error(f"{op_name} failed after {duration:.2f}s: {e}")
                raise
        
        return wrapper
    return decorator


@contextmanager
def log_operation(logger: logging.Logger, operation: str, **metadata) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager for logging operations with timing.
    
    Args:
        logger: Logger instance
        operation: Operation name
        **metadata: Additional metadata to log
    
    Example:
        with log_operation(logger, 'process_dataset', dataset='test.jsonl'):
            # do work
            pass
    """
    context = {'operation': operation, **metadata}
    start_time = time.time()
    
    logger.info(f"Starting: {operation}", extra={'metadata': metadata})
    
    try:
        yield context
        
        duration = time.time() - start_time
        _performance_tracker.record(operation, duration, status='success', **metadata)
        
        logger.info(f"Completed: {operation} ({duration:.2f}s)", 
                   extra={'metadata': {**metadata, 'duration': duration}})
    
    except Exception as e:
        duration = time.time() - start_time
        _performance_tracker.record(operation, duration, status='failed', error=str(e), **metadata)
        
        logger.error(f"Failed: {operation} ({duration:.2f}s) - {e}",
                    extra={'metadata': {**metadata, 'duration': duration, 'error': str(e)}})
        raise


# ============================================
# ERROR AGGREGATION
# ============================================

class ErrorAggregator:
    """Aggregate errors by type and stage."""
    
    def __init__(self):
        self.errors: Dict[str, list] = defaultdict(list)
        self.warnings: Dict[str, list] = defaultdict(list)
    
    def add_error(self, stage: str, error: str, **metadata):
        """Add error for stage."""
        self.errors[stage].append({
            'error': error,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **metadata
        })
    
    def add_warning(self, stage: str, warning: str, **metadata):
        """Add warning for stage."""
        self.warnings[stage].append({
            'warning': warning,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            **metadata
        })
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error summary."""
        return {
            'total_errors': sum(len(errs) for errs in self.errors.values()),
            'total_warnings': sum(len(warns) for warns in self.warnings.values()),
            'errors_by_stage': {
                stage: len(errs) 
                for stage, errs in self.errors.items()
            },
            'warnings_by_stage': {
                stage: len(warns)
                for stage, warns in self.warnings.items()
            }
        }
    
    def get_errors(self, stage: str = None) -> list:
        """Get errors for stage (or all if stage=None)."""
        if stage:
            return self.errors.get(stage, [])
        return [err for errs in self.errors.values() for err in errs]
    
    def get_warnings(self, stage: str = None) -> list:
        """Get warnings for stage (or all if stage=None)."""
        if stage:
            return self.warnings.get(stage, [])
        return [warn for warns in self.warnings.values() for warn in warns]
    
    def reset(self):
        """Reset all errors and warnings."""
        self.errors.clear()
        self.warnings.clear()


# Global error aggregator
_error_aggregator = ErrorAggregator()


# ============================================
# TQDM INTEGRATION
# ============================================

class TqdmLoggingHandler(logging.Handler):
    """Logging handler that works with tqdm progress bars."""
    
    def emit(self, record):
        try:
            msg = self.format(record)
            if TQDM_AVAILABLE:
                tqdm.write(msg)
            else:
                print(msg)
        except Exception:
            self.handleError(record)


# ============================================
# SETUP FUNCTIONS
# ============================================

def setup_logging(
    level: str = "INFO",
    log_file: Optional[Path] = None,
    console: bool = True,
    colored: bool = True,
    structured_file: Optional[Path] = None,
    format_string: Optional[str] = None,
    detailed: bool = False,
    max_bytes: int = 10485760,  # 10MB
    backup_count: int = 5,
    use_tqdm_handler: bool = False
) -> logging.Logger:
    """
    Setup logging for the project.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (if None - console only)
        console: Whether to output to console
        colored: Use colors in console
        structured_file: Path to structured JSON log file (optional)
        format_string: Custom format string
        detailed: Use detailed format (includes filename:lineno)
        max_bytes: Max file size before rotation
        backup_count: Number of backup files
        use_tqdm_handler: Use tqdm-compatible handler
        
    Returns:
        Configured root logger
    """
    # Convert level
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    
    # Format
    if format_string is None:
        format_string = DETAILED_FORMAT if detailed else DEFAULT_FORMAT
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    if console:
        if use_tqdm_handler:
            console_handler = TqdmLoggingHandler()
        else:
            console_handler = logging.StreamHandler(sys.stdout)
        
        console_handler.setLevel(numeric_level)
        
        if colored and COLORAMA_AVAILABLE:
            console_formatter = ColoredFormatter(format_string)
        else:
            console_formatter = logging.Formatter(format_string)
        
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # File handler (with rotation)
    if log_file is not None:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        file_handler.setLevel(numeric_level)
        file_formatter = logging.Formatter(format_string)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Structured JSON file handler
    if structured_file is not None:
        structured_file = Path(structured_file)
        structured_file.parent.mkdir(parents=True, exist_ok=True)
        
        json_handler = RotatingFileHandler(
            structured_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8'
        )
        json_handler.setLevel(numeric_level)
        json_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(json_handler)
    
    return root_logger


def setup_logging_from_config(config: dict) -> logging.Logger:
    """
    Setup logging from config dict (usually config['logging']).
    
    Args:
        config: Configuration dictionary
        
    Returns:
        Configured root logger
    """
    logging_config = config.get('logging', {})
    
    level = logging_config.get('level', 'INFO')
    format_string = logging_config.get('format')
    detailed = logging_config.get('detailed', False)
    
    # File settings
    file_config = logging_config.get('file', {})
    log_file = None
    if file_config.get('enabled', False):
        log_file = Path(file_config.get('path', 'logs/pipeline.log'))
    
    max_bytes = file_config.get('max_bytes', 10485760)
    backup_count = file_config.get('backup_count', 5)
    
    # Structured logging
    structured_config = logging_config.get('structured', {})
    structured_file = None
    if structured_config.get('enabled', False):
        structured_file = Path(structured_config.get('path', 'logs/pipeline.json'))
    
    # Console settings
    console_config = logging_config.get('console', {})
    console = console_config.get('enabled', True)
    colored = console_config.get('colored', True)
    
    # Progress bar integration
    use_tqdm = logging_config.get('use_tqdm_handler', False)
    
    return setup_logging(
        level=level,
        log_file=log_file,
        console=console,
        colored=colored,
        structured_file=structured_file,
        format_string=format_string,
        detailed=detailed,
        max_bytes=max_bytes,
        backup_count=backup_count,
        use_tqdm_handler=use_tqdm
    )


def get_logger(name: str, structured: bool = False) -> logging.Logger:
    """
    Get logger for a specific module.
    
    Args:
        name: Module name (usually __name__)
        structured: Return StructuredLogger wrapper
        
    Returns:
        Logger for this module
    """
    logger = logging.getLogger(name)
    
    if structured:
        return StructuredLogger(logger)
    
    return logger


def get_performance_tracker() -> PerformanceTracker:
    """Get global performance tracker."""
    return _performance_tracker


def get_error_aggregator() -> ErrorAggregator:
    """Get global error aggregator."""
    return _error_aggregator


# ============================================
# UTILITY FUNCTIONS
# ============================================

def log_section(logger: logging.Logger, title: str, level: str = "INFO", char: str = "=") -> None:
    """
    Log a pretty section header.
    
    Args:
        logger: Logger instance
        title: Section title
        level: Log level
        char: Character for separator
    """
    separator = char * 60
    log_func = getattr(logger, level.lower())
    log_func(separator)
    log_func(f"  {title}")
    log_func(separator)


def log_stage(logger: logging.Logger, stage: str, action: str = "Starting") -> None:
    """
    Log pipeline stage with emoji and formatting.
    
    Args:
        logger: Logger instance
        stage: Stage name
        action: Action (Starting/Completed/Failed)
    """
    stage_emojis = {
        'structural': '📄',
        'structure_detect': '📖',
        'summarize': '📝',
        'extended': '🤖',
        'finalize': '✅',
        'chunk': '🧩',
        'embed': '🔢',
        'search': '🔍',
    }
    
    emoji = stage_emojis.get(stage, '⚙️')
    log_section(logger, f"{emoji} {action}: {stage.upper()}", "INFO")


def log_config(logger: logging.Logger, config: dict, title: str = "Configuration") -> None:
    """
    Log configuration in readable format.
    
    Args:
        logger: Logger instance
        config: Configuration dictionary
        title: Title
    """
    logger.info(f"{title}:")
    logger.info(json.dumps(config, indent=2, ensure_ascii=False))


def log_metrics(logger: logging.Logger, metrics: Dict[str, Any], title: str = "Metrics") -> None:
    """
    Log metrics in formatted way.
    
    Args:
        logger: Logger instance
        metrics: Metrics dictionary
        title: Title
    """
    logger.info(f"{title}:")
    for key, value in metrics.items():
        if isinstance(value, float):
            logger.info(f"  {key}: {value:.4f}")
        else:
            logger.info(f"  {key}: {value}")


def log_performance_summary(logger: logging.Logger) -> None:
    """Log summary of all performance metrics."""
    tracker = get_performance_tracker()
    stats = tracker.get_all_stats()
    
    if not stats:
        logger.info("No performance data recorded")
        return
    
    log_section(logger, "Performance Summary", "INFO")
    
    for operation, metrics in sorted(stats.items()):
        logger.info(f"\n{operation}:")
        logger.info(f"  Count: {metrics['count']}")
        logger.info(f"  Total: {metrics['total']:.2f}s")
        logger.info(f"  Avg: {metrics['avg']:.2f}s")
        logger.info(f"  Min: {metrics['min']:.2f}s")
        logger.info(f"  Max: {metrics['max']:.2f}s")


def log_error_summary(logger: logging.Logger) -> None:
    """Log summary of all errors and warnings."""
    aggregator = get_error_aggregator()
    summary = aggregator.get_summary()
    
    if summary['total_errors'] == 0 and summary['total_warnings'] == 0:
        logger.info("No errors or warnings recorded")
        return
    
    log_section(logger, "Error Summary", "WARNING" if summary['total_errors'] > 0 else "INFO")
    
    logger.warning(f"Total Errors: {summary['total_errors']}")
    logger.warning(f"Total Warnings: {summary['total_warnings']}")
    
    if summary['errors_by_stage']:
        logger.warning("\nErrors by stage:")
        for stage, count in summary['errors_by_stage'].items():
            logger.warning(f"  {stage}: {count}")
    
    if summary['warnings_by_stage']:
        logger.info("\nWarnings by stage:")
        for stage, count in summary['warnings_by_stage'].items():
            logger.info(f"  {stage}: {count}")


def reset_tracking() -> None:
    """Reset all tracking (performance + errors)."""
    _performance_tracker.reset()
    _error_aggregator.reset()


# ============================================
# PROGRESS BAR HELPERS
# ============================================

def create_progress_bar(iterable, desc: str = "", total: int = None, **kwargs):
    """
    Create tqdm progress bar with logging compatibility.
    
    Args:
        iterable: Iterable to wrap
        desc: Description
        total: Total items (if not inferable)
        **kwargs: Additional tqdm arguments
        
    Returns:
        tqdm progress bar or plain iterable if tqdm not available
    """
    if TQDM_AVAILABLE:
        return tqdm(iterable, desc=desc, total=total, **kwargs)
    return iterable


# ============================================
# EXAMPLE USAGE
# ============================================

if __name__ == "__main__":
    # Example 1: Basic setup
    logger = setup_logging(
        level="DEBUG",
        log_file=Path("logs/test.log"),
        structured_file=Path("logs/test.json"),
        console=True,
        colored=True,
        detailed=True
    )
    
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning")
    logger.error("This is an error")
    logger.critical("This is critical!")
    
    # Example 2: Structured logging
    structured_logger = get_logger(__name__, structured=True)
    structured_logger.info("Processing started", 
                          dataset="test.jsonl", 
                          pages=100)
    
    # Example 3: Stage logging
    log_stage(logger, "structural", "Starting")
    
    # Example 4: Performance tracking
    @log_performance('process_page')
    def process_page(page_num):
        time.sleep(0.1)
        return f"Page {page_num} processed"
    
    for i in range(5):
        process_page(i)
    
    log_performance_summary(logger)
    
    # Example 5: Context manager
    with log_operation(logger, "process_dataset", dataset="test.jsonl"):
        time.sleep(0.5)
    
    # Example 6: Error aggregation
    aggregator = get_error_aggregator()
    aggregator.add_error("structural", "Failed to extract page 42", page=42)
    aggregator.add_warning("extended", "Low OCR confidence", page=15, confidence=0.65)
    
    log_error_summary(logger)
    
    # Example 7: Progress bars
    items = range(10)
    for item in create_progress_bar(items, desc="Processing"):
        time.sleep(0.1)
    
    print("\n" + "="*60)
    print("All examples completed!")
