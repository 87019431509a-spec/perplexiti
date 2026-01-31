# -*- coding: utf-8 -*-
"""
Система логирования - ИСПРАВЛЕННАЯ
UTF-8 везде, цветные логи, ротация файлов
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from typing import Optional


# Цвета для консоли
class LogColors:
    """ANSI цвета для логов."""
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    
    # Уровни логов
    DEBUG = '\033[36m'      # Cyan
    INFO = '\033[32m'       # Green
    WARNING = '\033[33m'    # Yellow
    ERROR = '\033[91m'      # Red
    CRITICAL = '\033[41m'   # Red background
    
    # Дополнительные
    TIME = '\033[90m'       # Gray
    NAME = '\033[94m'       # Blue


class ColoredFormatter(logging.Formatter):
    """Форматтер с цветами для консоли."""
    
    COLORS = {
        logging.DEBUG: LogColors.DEBUG,
        logging.INFO: LogColors.INFO,
        logging.WARNING: LogColors.WARNING,
        logging.ERROR: LogColors.ERROR,
        logging.CRITICAL: LogColors.CRITICAL,
    }
    
    def format(self, record: logging.LogRecord) -> str:
        # Цвет уровня
        color = self.COLORS.get(record.levelno, LogColors.RESET)
        
        # Форматируем время
        time_str = datetime.fromtimestamp(record.created).strftime('%H:%M:%S')
        
        # Короткое имя уровня
        level_names = {
            logging.DEBUG: 'DBG',
            logging.INFO: 'INF',
            logging.WARNING: 'WRN',
            logging.ERROR: 'ERR',
            logging.CRITICAL: 'CRT',
        }
        level = level_names.get(record.levelno, record.levelname[:3])
        
        # Формируем строку
        message = record.getMessage()
        
        # Добавляем исключение если есть
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            message += f"\n{record.exc_text}"
        
        return (
            f"{LogColors.TIME}{time_str}{LogColors.RESET} "
            f"{color}{LogColors.BOLD}[{level}]{LogColors.RESET} "
            f"{color}{message}{LogColors.RESET}"
        )


class FileFormatter(logging.Formatter):
    """Форматтер для файлов (без цветов)."""
    
    def format(self, record: logging.LogRecord) -> str:
        time_str = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        
        level = record.levelname[:3]
        message = record.getMessage()
        
        if record.exc_info:
            if not record.exc_text:
                record.exc_text = self.formatException(record.exc_info)
            message += f"\n{record.exc_text}"
        
        return f"{time_str} [{level}] {message}"


class ServiceLogger:
    """Логгер для конкретного сервиса."""
    
    def __init__(self, name: str, log_file: str):
        self._logger = logging.getLogger(f"neuro.{name}")
        self._logger.setLevel(logging.DEBUG)
        self._logger.handlers.clear()
        
        # Файловый handler
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        logs_dir = os.path.join(project_root, 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        
        log_path = os.path.join(logs_dir, log_file)
        
        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(FileFormatter())
        
        self._logger.addHandler(file_handler)
    
    def debug(self, msg: str, *args, **kwargs) -> None:
        self._logger.debug(msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs) -> None:
        self._logger.info(msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs) -> None:
        self._logger.warning(msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs) -> None:
        self._logger.error(msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs) -> None:
        self._logger.critical(msg, *args, **kwargs)


def setup_logging(level: int = logging.DEBUG) -> None:
    """Настройка системы логирования."""
    
    # Корневой логгер
    root = logging.getLogger()
    root.setLevel(level)
    
    # Очищаем существующие handlers
    root.handlers.clear()
    
    # Консольный handler с цветами и UTF-8
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(ColoredFormatter())
    
    # Устанавливаем кодировку для handler
    try:
        console_handler.stream.reconfigure(encoding='utf-8', errors='replace')
    except (AttributeError, Exception):
        pass
    
    root.addHandler(console_handler)
    
    # Файловый handler для основного лога
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    logs_dir = os.path.join(project_root, 'logs')
    os.makedirs(logs_dir, exist_ok=True)
    
    main_log = os.path.join(logs_dir, 'main.log')
    
    file_handler = RotatingFileHandler(
        main_log,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FileFormatter())
    
    root.addHandler(file_handler)
    
    # Отключаем спам от библиотек
    logging.getLogger('telethon').setLevel(logging.WARNING)
    logging.getLogger('asyncio').setLevel(logging.WARNING)
    logging.getLogger('aiohttp').setLevel(logging.WARNING)


# Основной логгер
logger = logging.getLogger('neuro')

# Специализированные логгеры для отдельных файлов
comments_logger = ServiceLogger('comments', 'comments.log')
warmup_logger = ServiceLogger('warmup', 'warmup.log')
