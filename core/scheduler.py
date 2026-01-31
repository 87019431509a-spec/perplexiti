# -*- coding: utf-8 -*-
"""
Планировщик задач
Управление asyncio.Task, graceful shutdown
"""

import asyncio
from typing import Dict, List, Optional, Set
from datetime import datetime

from core.logger import logger


class Scheduler:
    """Планировщик asyncio задач."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Задачи по сервисам
        self._tasks: Dict[str, List[asyncio.Task]] = {}
        
        # Активные сервисы
        self._running: Set[str] = set()
        
        # Время старта сервисов
        self._start_times: Dict[str, datetime] = {}
        
        self._lock = asyncio.Lock()
        self._initialized = True
    
    def register_task(self, service_name: str, task: asyncio.Task) -> None:
        """
        Зарегистрировать задачу сервиса.
        
        Args:
            service_name: Имя сервиса
            task: asyncio.Task
        """
        if service_name not in self._tasks:
            self._tasks[service_name] = []
            self._start_times[service_name] = datetime.now()
        
        self._tasks[service_name].append(task)
        self._running.add(service_name)
        
        logger.debug(f"[SCHEDULER] Задача зарегистрирована: {service_name}")
    
    def unregister_tasks(self, service_name: str) -> None:
        """Удалить все задачи сервиса."""
        if service_name in self._tasks:
            del self._tasks[service_name]
        
        if service_name in self._start_times:
            del self._start_times[service_name]
        
        self._running.discard(service_name)
        
        logger.debug(f"[SCHEDULER] Задачи удалены: {service_name}")
    
    def get_uptime(self, service_name: str) -> int:
        """Получить время работы сервиса в секундах."""
        if service_name not in self._start_times:
            return 0
        
        if not self.is_running(service_name):
            return 0
        
        delta = datetime.now() - self._start_times[service_name]
        return int(delta.total_seconds())
    
    def is_running(self, service_name: str) -> bool:
        """Проверить работает ли сервис."""
        if service_name not in self._tasks:
            return False
        
        # Проверяем что хотя бы одна задача активна
        tasks = self._tasks[service_name]
        active = [t for t in tasks if not t.done()]
        
        return len(active) > 0
    
    async def stop_service(self, service_name: str) -> None:
        """Остановить все задачи сервиса."""
        if service_name not in self._tasks:
            return
        
        logger.info(f"[SCHEDULER] Остановка сервиса: {service_name}")
        
        tasks = self._tasks[service_name]
        
        for task in tasks:
            if not task.done():
                task.cancel()
        
        # Ждём завершения
        for task in tasks:
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.CancelledError:
                pass
            except asyncio.TimeoutError:
                logger.warning(f"[SCHEDULER] Таймаут остановки задачи {service_name}")
            except Exception as e:
                logger.warning(f"[SCHEDULER] Ошибка остановки {service_name}: {e}")
        
        self.unregister_tasks(service_name)
        logger.info(f"[SCHEDULER] Сервис остановлен: {service_name}")
    
    async def stop_all(self) -> None:
        """Остановить все сервисы (graceful shutdown)."""
        logger.info("[SCHEDULER] Остановка всех сервисов...")
        
        services = list(self._tasks.keys())
        
        for service_name in services:
            await self.stop_service(service_name)
        
        logger.info("[SCHEDULER] Все сервисы остановлены")
    
    def get_status(self) -> Dict[str, Dict]:
        """Получить статус всех сервисов."""
        status = {}
        
        for service_name, tasks in self._tasks.items():
            active = [t for t in tasks if not t.done()]
            
            status[service_name] = {
                'running': len(active) > 0,
                'tasks_total': len(tasks),
                'tasks_active': len(active)
            }
        
        return status
    
    def cleanup_finished(self) -> None:
        """Удалить завершённые задачи."""
        for service_name in list(self._tasks.keys()):
            tasks = self._tasks[service_name]
            self._tasks[service_name] = [t for t in tasks if not t.done()]
            
            if not self._tasks[service_name]:
                del self._tasks[service_name]
                self._running.discard(service_name)


# Singleton
scheduler = Scheduler()
