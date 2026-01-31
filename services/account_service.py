# -*- coding: utf-8 -*-
"""
Сервис управления аккаунтами - ИСПРАВЛЕННЫЙ
Два пула: комментирование и прогрев
Конвертация tdata
"""

import os
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from telethon import TelegramClient
from telethon.sessions import StringSession

from core.logger import logger
from core.state import app_state
from core.database import Database


@dataclass
class AccountInfo:
    """Информация об аккаунте."""
    id: int
    phone: str
    session_file: str
    
    # Статус
    status: str = 'active'  # active, paused, banned
    
    # Лимиты
    comments_hour: int = 0
    comments_day: int = 0
    last_comment_time: Optional[datetime] = None
    
    # Прогрев
    warmup_level: int = 0
    
    # Ошибки
    error_count: int = 0
    last_error: Optional[str] = None


class AccountPool:
    """Пул аккаунтов для конкретной задачи."""
    
    def __init__(self, name: str, sessions_folder: str, tdata_folder: str):
        self._name = name
        self._sessions_folder = sessions_folder
        self._tdata_folder = tdata_folder
        
        self._accounts: Dict[int, AccountInfo] = {}
        self._clients: Dict[int, TelegramClient] = {}
        
        self._lock = asyncio.Lock()
        self._next_id = 1
    
    async def load_accounts(self) -> int:
        """Загрузка аккаунтов из папки sessions."""
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        sessions_path = os.path.join(project_root, self._sessions_folder)
        tdata_path = os.path.join(project_root, self._tdata_folder)
        
        loaded = 0
        
        # Создаём папки если нет
        os.makedirs(sessions_path, exist_ok=True)
        os.makedirs(tdata_path, exist_ok=True)
        
        # Конвертируем tdata если есть
        await self._convert_tdata(tdata_path, sessions_path)
        
        # Загружаем sessions
        if os.path.exists(sessions_path):
            for filename in os.listdir(sessions_path):
                if filename.endswith('.session'):
                    session_file = os.path.join(sessions_path, filename)
                    
                    try:
                        account = await self._load_session(session_file)
                        if account:
                            async with self._lock:
                                self._accounts[account.id] = account
                            loaded += 1
                            logger.info(f"[{self._name}] Загружен аккаунт: {account.phone}")
                    except Exception as e:
                        logger.warning(f"[{self._name}] Ошибка загрузки {filename}: {e}")
        
        logger.info(f"[{self._name}] Загружено аккаунтов: {loaded}")
        return loaded
    
    async def _load_session(self, session_file: str) -> Optional[AccountInfo]:
        """Загрузка одной сессии."""
        try:
            api_id = app_state.config.get('telegram', {}).get('api_id')
            api_hash = app_state.config.get('telegram', {}).get('api_hash')
            
            if not api_id or not api_hash:
                logger.error("Не заданы api_id и api_hash в config.yaml")
                return None
            
            # Создаём клиент
            client = TelegramClient(
                session_file.replace('.session', ''),
                api_id,
                api_hash
            )
            
            # Подключаемся
            await client.connect()
            
            if not await client.is_user_authorized():
                logger.warning(f"Сессия не авторизована: {session_file}")
                await client.disconnect()
                return None
            
            # Получаем информацию
            me = await client.get_me()
            
            account_id = self._next_id
            self._next_id += 1
            
            account = AccountInfo(
                id=account_id,
                phone=me.phone or str(me.id),
                session_file=session_file
            )
            
            async with self._lock:
                self._clients[account_id] = client
            
            return account
            
        except Exception as e:
            logger.warning(f"Ошибка загрузки сессии {session_file}: {e}", exc_info=True)
            return None
    
    async def _convert_tdata(self, tdata_path: str, sessions_path: str) -> int:
        """Конвертация tdata в session."""
        converted = 0
        
        if not os.path.exists(tdata_path):
            return 0
        
        try:
            from core.tdata_converter import TDataConverter
            converter = TDataConverter()
            
            for folder in os.listdir(tdata_path):
                folder_path = os.path.join(tdata_path, folder)
                
                if not os.path.isdir(folder_path):
                    continue
                
                # Проверяем что это tdata
                if not os.path.exists(os.path.join(folder_path, 'key_data')):
                    # Может быть вложенная папка tdata
                    nested = os.path.join(folder_path, 'tdata')
                    if os.path.exists(os.path.join(nested, 'key_data')):
                        folder_path = nested
                    else:
                        continue
                
                # Конвертируем
                session_file = os.path.join(sessions_path, f"{folder}.session")
                
                if os.path.exists(session_file):
                    logger.debug(f"Сессия уже существует: {folder}")
                    continue
                
                logger.info(f"[{self._name}] Конвертация tdata: {folder}")
                
                result = await converter.convert(folder_path, session_file)
                
                if result:
                    converted += 1
                    logger.info(f"[{self._name}] Успешно конвертирован: {folder}")
                else:
                    logger.warning(f"[{self._name}] Ошибка конвертации: {folder}")
                    
        except ImportError:
            logger.warning(f"[{self._name}] opentele не установлен, конвертация tdata невозможна")
        except Exception as e:
            logger.warning(f"[{self._name}] Ошибка конвертации tdata: {e}", exc_info=True)
        
        if converted > 0:
            logger.info(f"[{self._name}] Конвертировано tdata: {converted}")
        
        return converted
    
    def get_client(self, account_id: int) -> Optional[TelegramClient]:
        """Получить клиент по ID."""
        return self._clients.get(account_id)
    
    def get_all_clients(self) -> Dict[int, TelegramClient]:
        """Получить все клиенты."""
        return dict(self._clients)
    
    def get_active_accounts(self) -> List[AccountInfo]:
        """Получить активные аккаунты."""
        return [a for a in self._accounts.values() if a.status == 'active']
    
    async def disconnect_all(self) -> None:
        """Отключить все клиенты."""
        async with self._lock:
            for account_id, client in list(self._clients.items()):
                try:
                    if client.is_connected():
                        await client.disconnect()
                except Exception as e:
                    logger.warning(f"[{self._name}] Ошибка отключения {account_id}: {e}", exc_info=True)
            
            self._clients.clear()
        
        logger.info(f"[{self._name}] Все клиенты отключены")
    
    def get_stats(self) -> Dict[str, int]:
        """Статистика пула."""
        return {
            'total': len(self._accounts),
            'active': len([a for a in self._accounts.values() if a.status == 'active']),
            'paused': len([a for a in self._accounts.values() if a.status == 'paused']),
            'banned': len([a for a in self._accounts.values() if a.status == 'banned']),
            'connected': len(self._clients)
        }


class AccountService:
    """Сервис управления аккаунтами."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        # Два отдельных пула
        self._comments_pool = AccountPool(
            name='АККАУНТЫ-КОММЕНТЫ',
            sessions_folder='sessions_комменты',
            tdata_folder='tdata_комменты'
        )
        
        self._warmup_pool = AccountPool(
            name='АККАУНТЫ-ПРОГРЕВ',
            sessions_folder='sessions_прогрев',
            tdata_folder='tdata_прогрев'
        )
        
        self._db = Database()
        self._initialized = True
    
    async def load_accounts(self, pool_type: str = 'comments') -> int:
        """
        Загрузка аккаунтов.
        
        Args:
            pool_type: 'comments' или 'warmup'
        """
        if pool_type == 'comments':
            return await self._comments_pool.load_accounts()
        else:
            return await self._warmup_pool.load_accounts()
    
    def get_client(self, account_id: int, pool_type: str = 'comments') -> Optional[TelegramClient]:
        """Получить клиент по ID из указанного пула."""
        if pool_type == 'comments':
            return self._comments_pool.get_client(account_id)
        else:
            return self._warmup_pool.get_client(account_id)
    
    def get_comments_clients(self) -> Dict[int, TelegramClient]:
        """Получить все клиенты для комментирования."""
        return self._comments_pool.get_all_clients()
    
    def get_warmup_clients(self) -> Dict[int, TelegramClient]:
        """Получить все клиенты для прогрева."""
        return self._warmup_pool.get_all_clients()
    
    def get_active_accounts(self, pool_type: str = 'comments') -> List[AccountInfo]:
        """Получить активные аккаунты."""
        if pool_type == 'comments':
            return self._comments_pool.get_active_accounts()
        else:
            return self._warmup_pool.get_active_accounts()
    
    async def pause_account(self, account_id: int, pool_type: str = 'comments', reason: str = '') -> None:
        """Поставить аккаунт на паузу."""
        pool = self._comments_pool if pool_type == 'comments' else self._warmup_pool
        
        if account_id in pool._accounts:
            pool._accounts[account_id].status = 'paused'
            pool._accounts[account_id].last_error = reason
            logger.warning(f"Аккаунт {account_id} приостановлен: {reason}")
            
            try:
                await self._db.update_account(account_id, {
                    'status': 'paused',
                    'last_error': reason
                })
            except Exception as e:
                logger.warning(f"Ошибка сохранения статуса: {e}", exc_info=True)
    
    async def ban_account(self, account_id: int, pool_type: str = 'comments', reason: str = '') -> None:
        """Заблокировать аккаунт."""
        pool = self._comments_pool if pool_type == 'comments' else self._warmup_pool
        
        if account_id in pool._accounts:
            pool._accounts[account_id].status = 'banned'
            pool._accounts[account_id].last_error = reason
            logger.error(f"Аккаунт {account_id} заблокирован: {reason}")
            
            # Отключаем клиент
            if account_id in pool._clients:
                try:
                    await pool._clients[account_id].disconnect()
                except Exception as e:
                    logger.warning(f"Ошибка отключения забаненного аккаунта: {e}", exc_info=True)
                del pool._clients[account_id]
            
            try:
                await self._db.update_account(account_id, {
                    'status': 'banned',
                    'last_error': reason
                })
            except Exception as e:
                logger.warning(f"Ошибка сохранения статуса: {e}", exc_info=True)
    
    async def check_limits(self, account_id: int, pool_type: str = 'comments') -> bool:
        """Проверка лимитов аккаунта."""
        pool = self._comments_pool if pool_type == 'comments' else self._warmup_pool
        
        if account_id not in pool._accounts:
            return False
        
        account = pool._accounts[account_id]
        
        if account.status != 'active':
            return False
        
        # Получаем лимиты
        limits = app_state.config.get('limits', {})
        hour_limit = limits.get('comments_per_hour', 10)
        day_limit = limits.get('comments_per_day', 50)
        
        # SAFE режим уменьшает лимиты
        if app_state.mode == 'SAFE':
            hour_limit = hour_limit // 2
            day_limit = day_limit // 2
        
        # Проверяем
        if account.comments_hour >= hour_limit:
            logger.debug(f"Аккаунт {account_id}: лимит в час исчерпан ({hour_limit})")
            return False
        
        if account.comments_day >= day_limit:
            logger.debug(f"Аккаунт {account_id}: лимит в день исчерпан ({day_limit})")
            return False
        
        return True
    
    async def increment_comment_count(self, account_id: int, pool_type: str = 'comments') -> None:
        """Увеличить счётчик комментариев."""
        pool = self._comments_pool if pool_type == 'comments' else self._warmup_pool
        
        if account_id in pool._accounts:
            pool._accounts[account_id].comments_hour += 1
            pool._accounts[account_id].comments_day += 1
            pool._accounts[account_id].last_comment_time = datetime.now()
    
    async def disconnect_all(self) -> None:
        """Отключить все клиенты."""
        await self._comments_pool.disconnect_all()
        await self._warmup_pool.disconnect_all()
    
    def get_stats(self, pool_type: str = 'comments') -> Dict[str, int]:
        """Получить статистику."""
        if pool_type == 'comments':
            return self._comments_pool.get_stats()
        else:
            return self._warmup_pool.get_stats()


# Singleton
account_service = AccountService()
