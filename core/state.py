# -*- coding: utf-8 -*-
"""
Глобальное состояние приложения
"""

import os
import random
import asyncio
from typing import Any, Dict, Optional
from dataclasses import dataclass, field

import yaml


@dataclass
class AppState:
    """Глобальное состояние приложения."""
    
    # Режим работы
    mode: str = 'SAFE'  # SAFE или NORMAL
    
    # Конфигурация
    config: Dict[str, Any] = field(default_factory=dict)
    
    # Пути
    project_root: str = ''
    config_path: str = ''
    
    _initialized: bool = False
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    
    def __post_init__(self):
        self.project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.config_path = os.path.join(self.project_root, 'config.yaml')
    
    def load_config(self) -> None:
        """Загрузка конфигурации (синхронная)."""
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Файл конфигурации не найден: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            self.config = yaml.safe_load(f) or {}
        
        # Загружаем режим
        self.mode = self.config.get('mode', 'SAFE')
        
        self._initialized = True
    
    def save_config(self) -> None:
        """Сохранение конфигурации (синхронная)."""
        # Обновляем режим
        self.config['mode'] = self.mode
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                self.config,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False
            )
    
    def get_mode(self) -> str:
        """Получить текущий режим."""
        return self.mode
    
    def set_mode(self, mode: str) -> None:
        """Установить режим."""
        self.mode = mode
        self.config['mode'] = mode
    
    def get_delay(self, delay_type: str, default_min: int = 30, default_max: int = 120) -> int:
        """
        Получить задержку с учётом режима SAFE.
        
        Args:
            delay_type: Тип задержки
            default_min: Минимальная задержка по умолчанию
            default_max: Максимальная задержка по умолчанию
        
        Returns:
            Случайная задержка в секундах
        """
        delays = self.config.get('delays', {})
        
        min_delay = delays.get('min', default_min)
        max_delay = delays.get('max', default_max)
        
        # SAFE режим удваивает задержки
        if self.mode == 'SAFE':
            min_delay *= 2
            max_delay *= 2
        
        return random.randint(min_delay, max_delay)
    
    def get_limit(self, limit_name: str, default: int = 10) -> int:
        """
        Получить лимит с учётом режима SAFE.
        
        Args:
            limit_name: Название лимита
            default: Значение по умолчанию
        
        Returns:
            Значение лимита
        """
        limits = self.config.get('limits', {})
        limit = limits.get(limit_name, default)
        
        # SAFE режим уменьшает лимиты вдвое
        if self.mode == 'SAFE':
            limit = max(1, limit // 2)
        
        return limit
    
    def is_safe_mode(self) -> bool:
        """Проверка режима SAFE."""
        return self.mode == 'SAFE'
    
    def toggle_mode(self) -> str:
        """Переключение режима."""
        self.mode = 'NORMAL' if self.mode == 'SAFE' else 'SAFE'
        self.config['mode'] = self.mode
        return self.mode


# Singleton - два имени для совместимости
app_state = AppState()
state = app_state  # Алиас для импорта как 'state'
