# -*- coding: utf-8 -*-
"""
Сервис управления каналами
Загрузка из папок, проверка доступности, discussion groups
"""

import os
import asyncio
from typing import Optional, Dict, Any, List, Set
from datetime import datetime, timedelta
from dataclasses import dataclass, field

from telethon import TelegramClient, functions
from telethon.errors import (
    ChannelPrivateError, ChannelInvalidError, 
    FloodWaitError, RPCError
)

from core.logger import logger
from core.state import app_state
from core.database import Database


@dataclass
class ChannelInfo:
    """Информация о канале."""
    channel_id: int
    username: str
    title: str = ''
    
    # Discussion group
    discussion_id: Optional[int] = None
    has_comments: bool = False
    
    # Статус
    status: str = 'active'  # active, sleep, disabled
    
    # Санкции
    deletion_count: int = 0
    sleep_until: Optional[datetime] = None
    
    # Время
    last_post_at: Optional[datetime] = None
    last_comment_at: Optional[datetime] = None


class ChannelService:
    """Сервис управления каналами."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._channels: Dict[int, ChannelInfo] = {}
        self._username_to_id: Dict[str, int] = {}
        
        self._db = Database()
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self._lock = asyncio.Lock()
        self._initialized = True
    
    async def load_channels(self) -> int:
        """Загрузка каналов из папки."""
        channels_folder = os.path.join(self._project_root, 'каналы')
        
        if not os.path.exists(channels_folder):
            os.makedirs(channels_folder)
            logger.warning("Создана папка для каналов: каналы/")
            return 0
        
        loaded = 0
        
        # Читаем все .txt файлы
        for filename in os.listdir(channels_folder):
            if not filename.endswith('.txt'):
                continue
            
            filepath = os.path.join(channels_folder, filename)
            
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        
                        username = self._parse_channel(line)
                        if username:
                            # Создаём временную запись
                            # Полная информация будет получена при первом использовании
                            channel = ChannelInfo(
                                channel_id=0,  # Будет заполнено позже
                                username=username
                            )
                            
                            async with self._lock:
                                # Используем username как временный ключ
                                self._username_to_id[username] = 0
                            
                            loaded += 1
                            
            except Exception as e:
                logger.warning(f"Ошибка чтения файла каналов {filename}: {e}")
        
        logger.info(f"Загружено каналов из файлов: {loaded}")
        return loaded
    
    def _parse_channel(self, line: str) -> Optional[str]:
        """Парсинг строки с каналом."""
        # Удаляем лишнее
        line = line.strip()
        
        # Формат: https://t.me/channel_name
        if 't.me/' in line:
            line = line.split('t.me/')[-1].split('/')[0].split('?')[0]
        
        # Формат: @channel_name
        if line.startswith('@'):
            line = line[1:]
        
        # Проверяем валидность
        if line and len(line) >= 3:
            return line.lower()
        
        return None
    
    async def resolve_channel(
        self, 
        username: str, 
        client: TelegramClient
    ) -> Optional[ChannelInfo]:
        """Получить полную информацию о канале."""
        try:
            # Получаем entity
            entity = await client.get_entity(username)
            
            if not hasattr(entity, 'id'):
                return None
            
            channel_id = entity.id
            title = getattr(entity, 'title', username)
            
            # Проверяем discussion group
            discussion_id = None
            has_comments = False
            
            try:
                full = await client(functions.channels.GetFullChannelRequest(channel=entity))
                
                if full.full_chat.linked_chat_id:
                    discussion_id = full.full_chat.linked_chat_id
                    has_comments = True
                    logger.debug(f"Канал @{username} имеет discussion: {discussion_id}")
                    
            except Exception as e:
                logger.debug(f"Не удалось получить discussion для @{username}: {e}")
            
            # Создаём/обновляем запись
            channel = ChannelInfo(
                channel_id=channel_id,
                username=username,
                title=title,
                discussion_id=discussion_id,
                has_comments=has_comments
            )
            
            async with self._lock:
                self._channels[channel_id] = channel
                self._username_to_id[username] = channel_id
            
            # Сохраняем в БД
            await self._db.add_channel(
                channel_id=channel_id,
                username=username,
                title=title,
                discussion_id=discussion_id or 0
            )
            
            return channel
            
        except ChannelPrivateError:
            logger.warning(f"Канал @{username} приватный")
            return None
        
        except ChannelInvalidError:
            logger.warning(f"Канал @{username} невалидный")
            return None
        
        except FloodWaitError as e:
            logger.warning(f"FloodWait {e.seconds} сек при резолве @{username}")
            await asyncio.sleep(min(e.seconds, 60))
            return None
        
        except Exception as e:
            logger.warning(f"Ошибка резолва канала @{username}: {e}")
            return None
    
    def get_channel(self, channel_id: int) -> Optional[ChannelInfo]:
        """Получить канал по ID."""
        return self._channels.get(channel_id)
    
    def get_channel_by_username(self, username: str) -> Optional[ChannelInfo]:
        """Получить канал по username."""
        username = username.lower().replace('@', '')
        channel_id = self._username_to_id.get(username)
        
        if channel_id:
            return self._channels.get(channel_id)
        return None
    
    def get_active_channels(self) -> List[ChannelInfo]:
        """Получить активные каналы."""
        now = datetime.now()
        
        active = []
        for channel in self._channels.values():
            if channel.status == 'active':
                active.append(channel)
            elif channel.status == 'sleep' and channel.sleep_until:
                if now > channel.sleep_until:
                    channel.status = 'active'
                    active.append(channel)
        
        return active
    
    def get_channels_with_comments(self) -> List[ChannelInfo]:
        """Получить каналы с включёнными комментариями."""
        return [c for c in self.get_active_channels() if c.has_comments]
    
    def get_all_usernames(self) -> List[str]:
        """Получить все username каналов."""
        return list(self._username_to_id.keys())
    
    async def set_channel_sleep(self, channel_id: int, duration_minutes: int = 60) -> None:
        """Поставить канал в спящий режим."""
        async with self._lock:
            if channel_id in self._channels:
                channel = self._channels[channel_id]
                channel.status = 'sleep'
                channel.sleep_until = datetime.now() + timedelta(minutes=duration_minutes)
                
                logger.warning(f"Канал @{channel.username} в спячке на {duration_minutes} мин")
                
                await self._db.update_channel(channel_id, {
                    'status': 'sleep',
                    'sleep_until': channel.sleep_until.isoformat()
                })
    
    async def disable_channel(self, channel_id: int, reason: str = '') -> None:
        """Отключить канал."""
        async with self._lock:
            if channel_id in self._channels:
                channel = self._channels[channel_id]
                channel.status = 'disabled'
                
                logger.error(f"Канал @{channel.username} отключён: {reason}")
                
                await self._db.update_channel(channel_id, {
                    'status': 'disabled'
                })
    
    async def increment_deletions(self, channel_id: int) -> int:
        """Увеличить счётчик удалений."""
        async with self._lock:
            if channel_id in self._channels:
                self._channels[channel_id].deletion_count += 1
                count = self._channels[channel_id].deletion_count
                
                # Сохраняем в БД
                await self._db.increment_channel_deletions(channel_id)
                
                return count
            return 0
    
    def get_stats(self) -> Dict[str, int]:
        """Статистика каналов."""
        stats = {
            'total': len(self._channels),
            'active': 0,
            'sleep': 0,
            'disabled': 0,
            'with_comments': 0
        }
        
        for channel in self._channels.values():
            if channel.status == 'active':
                stats['active'] += 1
            elif channel.status == 'sleep':
                stats['sleep'] += 1
            elif channel.status == 'disabled':
                stats['disabled'] += 1
            
            if channel.has_comments:
                stats['with_comments'] += 1
        
        return stats


# Singleton
channel_service = ChannelService()
