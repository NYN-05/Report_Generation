"""
Logger Module
=============
Centralized logging with structured output and file rotation.
"""

import logging
import logging.handlers
import datetime
import json
import threading
from pathlib import Path
from typing import Optional, Any, Dict


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs structured JSON-like logs."""

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
        self._threadlocal = threading.local()

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if self.include_extra and hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        return json.dumps(log_data, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter."""

    def __init__(self):
        super().__init__()
        self.fmt = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
        self.datefmt = "%H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        return super().format(record)


class RotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Custom rotating file handler with structured output."""

    def __init__(self, filename, maxBytes=10485760, backupCount=5, encoding="utf-8"):
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount, encoding=encoding)
        self.setFormatter(StructuredFormatter())


class Logger:
    """Centralized logger with file and console output."""

    _instances: Dict[str, "Logger"] = {}
    _lock = threading.Lock()

    def __init__(self, name: str, level: int = logging.INFO):
        self.name = name
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False

        if not self.logger.handlers:
            self._setup_handlers()

    def _setup_handlers(self):
        """Setup console and file handlers."""
        console = logging.StreamHandler()
        console.setLevel(logging.INFO)
        console.setFormatter(ConsoleFormatter())
        self.logger.addHandler(console)

        log_dir = Path("logs")
        log_dir.mkdir(exist_ok=True)

        log_file = log_dir / f"{self.name}_{datetime.date.today()}.log"
        file_handler = RotatingFileHandler(
            str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        self.logger.addHandler(file_handler)

    @classmethod
    def get_logger(cls, name: str) -> "Logger":
        """Get or create logger instance."""
        if name not in cls._instances:
            with cls._lock:
                if name not in cls._instances:
                    cls._instances[name] = cls(name)
        return cls._instances[name]

    def debug(self, msg: str, **kwargs):
        self.logger.debug(msg, extra={"extra_data": kwargs} if kwargs else {})

    def info(self, msg: str, **kwargs):
        self.logger.info(msg, extra={"extra_data": kwargs} if kwargs else {})

    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg, extra={"extra_data": kwargs} if kwargs else {})

    def error(self, msg: str, **kwargs):
        self.logger.error(msg, extra={"extra_data": kwargs} if kwargs else {})

    def critical(self, msg: str, **kwargs):
        self.logger.critical(msg, extra={"extra_data": kwargs} if kwargs else {})

    def exception(self, msg: str, **kwargs):
        self.logger.exception(msg, extra={"extra_data": kwargs} if kwargs else {})

    def log_execution(self, operation: str, **metadata):
        """Log execution with structured metadata."""
        self.info(f"[EXEC] {operation}", operation=operation, **metadata)


def get_logger(name: str) -> Logger:
    """Convenience function to get logger."""
    return Logger.get_logger(name)


def configure_root_logger(level: int = logging.INFO):
    """Configure the root logger."""
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%H:%M:%S"
    )