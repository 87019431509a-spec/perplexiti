# -*- coding: utf-8 -*-
"""
Сервис управления прокси - ИСПРАВЛЕННЫЙ
Два пула: комментирование и прогрев
Привязка прокси к аккаунтам
"""

import os
import re
import asyncio
import aiohttp
from typing import Optional, Dict, Any, List, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from core.logger import logger
from core.state import app_state


@dataclass
class ProxyInfo:
    """Информация о прокси."""
    proxy_type: str  # socks5, http, https
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    
    # Статус
    is_working: bool = False
    last_check: Optional[datetime] = None
    fail_count: int = 0
    response_time: float = 0.0
    
    # Привязка к аккаунту
    bound_account_id: Optional[int] = None
    
    def to_telethon(self) -> tuple:
        """Формат для Telethon."""
        import socks
        
        proxy_types = {
            'socks5': socks.SOCKS5,
            'socks4': socks.SOCKS4,
            'http': socks.HTTP,
            'https': socks.HTTP,
        }
        
        return (
            proxy_types.get(self.proxy_type.lower(), socks.SOCKS5),
            self.host,
            self.port,
            True,  # rdns
            self.username,
            self.password
        )
    
    def to_aiohttp(self) -> str:
        """Формат для aiohttp."""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        return f"{self.proxy_type}://{auth}{self.host}:{self.port}"
    
    @property
    def address(self) -> str:
        """Адрес прокси."""
        return f"{self.host}:{self.port}"


class ProxyPool:
    """Пул прокси с привязкой к аккаунтам."""
    
    def __init__(self, name: str):
        self._name = name
        self._proxies: List[ProxyInfo] = []
        self._working: List[ProxyInfo] = []
        self._failed: List[ProxyInfo] = []
        
        # Привязка: account_id -> proxy
        self._bindings: Dict[int, ProxyInfo] = {}
        
        # Индекс для ротации
        self._rotation_index = 0
        
        self._lock = asyncio.Lock()
    
    async def load_from_file(self, filepath: str) -> int:
        """Загрузка прокси из файла."""
        if not os.path.exists(filepath):
            logger.warning(f"[{self._name}] Файл прокси не найден: {filepath}")
            return 0
        
        loaded = 0
        
        async with self._lock:
            self._proxies.clear()
            self._working.clear()
            self._failed.clear()
            self._bindings.clear()
            
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    proxy = self._parse_proxy(line)
                    if proxy:
                        self._proxies.append(proxy)
                        loaded += 1
        
        logger.info(f"[{self._name}] Загружено прокси: {loaded}")
        return loaded
    
    def _parse_proxy(self, line: str) -> Optional[ProxyInfo]:
        """Парсинг строки прокси."""
        # Форматы:
        # type://user:pass@host:port
        # type://host:port
        # host:port:user:pass
        # host:port
        
        try:
            # Формат с протоколом
            match = re.match(
                r'^(socks5|socks4|http|https)://(?:([^:]+):([^@]+)@)?([^:]+):(\d+)$',
                line, re.IGNORECASE
            )
            
            if match:
                return ProxyInfo(
                    proxy_type=match.group(1).lower(),
                    username=match.group(2),
                    password=match.group(3),
                    host=match.group(4),
                    port=int(match.group(5))
                )
            
            # Формат host:port:user:pass
            parts = line.split(':')
            if len(parts) == 4:
                return ProxyInfo(
                    proxy_type='socks5',
                    host=parts[0],
                    port=int(parts[1]),
                    username=parts[2],
                    password=parts[3]
                )
            
            # Формат host:port
            if len(parts) == 2:
                return ProxyInfo(
                    proxy_type='socks5',
                    host=parts[0],
                    port=int(parts[1])
                )
            
            logger.warning(f"[{self._name}] Неверный формат прокси: {line}")
            return None
            
        except Exception as e:
            logger.warning(f"[{self._name}] Ошибка парсинга прокси '{line}': {e}")
            return None
    
    async def check_proxy(self, proxy: ProxyInfo, timeout: float = 10.0) -> bool:
        """Проверка одного прокси."""
        try:
            start_time = asyncio.get_event_loop().time()
            
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    'https://api.telegram.org',
                    proxy=proxy.to_aiohttp(),
                    timeout=aiohttp.ClientTimeout(total=timeout),
                    ssl=False
                ) as response:
                    if response.status in (200, 403, 404):  # Любой ответ = прокси работает
                        proxy.is_working = True
                        proxy.fail_count = 0
                        proxy.response_time = asyncio.get_event_loop().time() - start_time
                        proxy.last_check = datetime.now()
                        return True
            
        except asyncio.TimeoutError:
            logger.debug(f"[{self._name}] Прокси {proxy.address} - таймаут")
        except aiohttp.ClientProxyConnectionError:
            logger.debug(f"[{self._name}] Прокси {proxy.address} - ошибка подключения")
        except Exception as e:
            logger.debug(f"[{self._name}] Прокси {proxy.address} - ошибка: {e}")
        
        proxy.is_working = False
        proxy.fail_count += 1
        proxy.last_check = datetime.now()
        return False
    
    async def check_all(self) -> Dict[str, int]:
        """Проверка всех прокси."""
        if not self._proxies:
            return {'total': 0, 'working': 0, 'failed': 0}
        
        logger.info(f"[{self._name}] Проверка {len(self._proxies)} прокси...")
        
        # Параллельная проверка
        tasks = [self.check_proxy(p) for p in self._proxies]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        async with self._lock:
            self._working = [p for p in self._proxies if p.is_working]
            self._failed = [p for p in self._proxies if not p.is_working]
        
        stats = {
            'total': len(self._proxies),
            'working': len(self._working),
            'failed': len(self._failed)
        }
        
        logger.info(f"[{self._name}] Результат: {stats['working']}/{stats['total']} рабочих")
        
        return stats
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику."""
        return {
            'total': len(self._proxies),
            'working': len(self._working),
            'failed': len(self._failed),
            'bound': len(self._bindings)
        }
    
    async def get_proxy_for_account(self, account_id: int) -> Optional[ProxyInfo]:
        """
        Получить прокси для аккаунта.
        Если уже привязан - вернуть привязанный.
        Если нет - привязать свободный рабочий.
        """
        async with self._lock:
            # Уже есть привязка?
            if account_id in self._bindings:
                proxy = self._bindings[account_id]
                # Проверяем что прокси ещё рабочий
                if proxy.is_working:
                    return proxy
                else:
                    # Прокси сломался - отвязываем
                    del self._bindings[account_id]
                    proxy.bound_account_id = None
            
            # Ищем свободный рабочий прокси
            for proxy in self._working:
                if proxy.bound_account_id is None:
                    # Привязываем
                    proxy.bound_account_id = account_id
                    self._bindings[account_id] = proxy
                    logger.debug(f"[{self._name}] Прокси {proxy.address} привязан к аккаунту {account_id}")
                    return proxy
            
            # Нет свободных - используем ротацию
            if self._working:
                self._rotation_index = (self._rotation_index + 1) % len(self._working)
                proxy = self._working[self._rotation_index]
                logger.debug(f"[{self._name}] Ротация прокси {proxy.address} для аккаунта {account_id}")
                return proxy
            
            # Нет рабочих прокси - пробуем непроверенные
            if self._proxies:
                logger.warning(f"[{self._name}] Нет проверенных прокси, используем непроверенный")
                return self._proxies[0]
            
            return None
    
    async def release_proxy(self, account_id: int) -> None:
        """Отвязать прокси от аккаунта."""
        async with self._lock:
            if account_id in self._bindings:
                proxy = self._bindings[account_id]
                proxy.bound_account_id = None
                del self._bindings[account_id]
                logger.debug(f"[{self._name}] Прокси {proxy.address} отвязан от аккаунта {account_id}")
    
    async def mark_proxy_failed(self, account_id: int) -> None:
        """Пометить прокси аккаунта как нерабочий."""
        async with self._lock:
            if account_id in self._bindings:
                proxy = self._bindings[account_id]
                proxy.is_working = False
                proxy.fail_count += 1
                
                # Убираем из рабочих
                if proxy in self._working:
                    self._working.remove(proxy)
                if proxy not in self._failed:
                    self._failed.append(proxy)
                
                # Отвязываем
                del self._bindings[account_id]
                proxy.bound_account_id = None
                
                logger.warning(f"[{self._name}] Прокси {proxy.address} помечен как нерабочий")
    
    def get_next_proxy(self) -> Optional[ProxyInfo]:
        """Получить следующий прокси по ротации (без привязки)."""
        if self._working:
            self._rotation_index = (self._rotation_index + 1) % len(self._working)
            return self._working[self._rotation_index]
        
        if self._proxies:
            return self._proxies[0]
        
        return None


class ProxyService:
    """Сервис управления прокси."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._comments_pool = ProxyPool('ПРОКСИ-КОММЕНТЫ')
        self._warmup_pool = ProxyPool('ПРОКСИ-ПРОГРЕВ')
        
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self._initialized = True
    
    async def load_proxies(self, pool_type: str = 'comments') -> int:
        """
        Загрузка прокси из папки.
        
        Args:
            pool_type: 'comments' или 'warmup'
        """
        if pool_type == 'comments':
            folder = 'прокси_комменты'
            pool = self._comments_pool
        else:
            folder = 'прокси_прогрев'
            pool = self._warmup_pool
        
        folder_path = os.path.join(self._project_root, folder)
        
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logger.warning(f"Создана папка для прокси: {folder}")
            return 0
        
        total_loaded = 0
        
        # Загружаем из всех .txt файлов
        for filename in os.listdir(folder_path):
            if filename.endswith('.txt'):
                filepath = os.path.join(folder_path, filename)
                loaded = await pool.load_from_file(filepath)
                total_loaded += loaded
        
        return total_loaded
    
    async def check_all_proxies(self, pool_type: str = 'comments') -> Dict[str, int]:
        """Проверка всех прокси в пуле."""
        if pool_type == 'comments':
            return await self._comments_pool.check_all()
        else:
            return await self._warmup_pool.check_all()
    
    async def get_proxy_for_account(
        self,
        account_id: int,
        pool_type: str = 'comments'
    ) -> Optional[ProxyInfo]:
        """Получить прокси для аккаунта с привязкой."""
        if pool_type == 'comments':
            return await self._comments_pool.get_proxy_for_account(account_id)
        else:
            return await self._warmup_pool.get_proxy_for_account(account_id)
    
    async def release_proxy(self, account_id: int, pool_type: str = 'comments') -> None:
        """Отвязать прокси от аккаунта."""
        if pool_type == 'comments':
            await self._comments_pool.release_proxy(account_id)
        else:
            await self._warmup_pool.release_proxy(account_id)
    
    async def mark_proxy_failed(self, account_id: int, pool_type: str = 'comments') -> None:
        """Пометить прокси аккаунта как нерабочий."""
        if pool_type == 'comments':
            await self._comments_pool.mark_proxy_failed(account_id)
        else:
            await self._warmup_pool.mark_proxy_failed(account_id)
    
    def get_stats(self, pool_type: str = 'comments') -> Dict[str, int]:
        """Получить статистику пула."""
        if pool_type == 'comments':
            return self._comments_pool.get_stats()
        else:
            return self._warmup_pool.get_stats()
    
    # Обратная совместимость
    def get_next_proxy(self, pool_type: str = 'comments') -> Optional[Dict[str, Any]]:
        """Получить следующий прокси (устаревший метод)."""
        if pool_type == 'comments':
            proxy = self._comments_pool.get_next_proxy()
        else:
            proxy = self._warmup_pool.get_next_proxy()
        
        if proxy:
            return {
                'type': proxy.proxy_type,
                'host': proxy.host,
                'port': proxy.port,
                'username': proxy.username,
                'password': proxy.password
            }
        return None
    
    async def check_all_comments_proxies(self) -> List[Dict[str, Any]]:
        """Проверка всех прокси комментирования с результатами."""
        await self.load_proxies('comments')
        results = []
        
        for proxy in self._comments_pool._proxies:
            start = asyncio.get_event_loop().time()
            ok = await self._comments_pool.check_proxy(proxy)
            elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
            
            results.append({
                'proxy': proxy.address,
                'status': 'ok' if ok else 'fail',
                'ping': elapsed if ok else 0,
                'error': '' if ok else 'connection failed'
            })
        
        return results
    
    async def check_all_warmup_proxies(self) -> List[Dict[str, Any]]:
        """Проверка всех прокси прогрева с результатами."""
        await self.load_proxies('warmup')
        results = []
        
        for proxy in self._warmup_pool._proxies:
            start = asyncio.get_event_loop().time()
            ok = await self._warmup_pool.check_proxy(proxy)
            elapsed = int((asyncio.get_event_loop().time() - start) * 1000)
            
            results.append({
                'proxy': proxy.address,
                'status': 'ok' if ok else 'fail',
                'ping': elapsed if ok else 0,
                'error': '' if ok else 'connection failed'
            })
        
        return results
    
    def get_comments_stats(self) -> Dict[str, int]:
        """Получить статистику пула комментирования."""
        return self._comments_pool.get_stats()
    
    def get_warmup_stats(self) -> Dict[str, int]:
        """Получить статистику пула прогрева."""
        return self._warmup_pool.get_stats()


# Singleton
proxy_service = ProxyService()
