# -*- coding: utf-8 -*-
"""
Сервис комментирования - ГЛАВНАЯ ЛОГИКА
Получение постов, генерация GPT, отправка в discussion group
ЖЁСТКИЙ КОНТРАКТ peer_id
"""

import asyncio
import random
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from telethon import TelegramClient, functions, types
from telethon.errors import (
    FloodWaitError, ChatWriteForbiddenError, UserBannedInChannelError,
    ChannelPrivateError, MsgIdInvalidError, RPCError
)

from core.logger import comments_logger as logger
from core.state import app_state
from core.scheduler import scheduler
from core.database import Database
from services.gpt_service import gpt_service


class CommentingService:
    """Сервис автокомментирования."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
        # Антидубликаты: channel_id -> set(post_ids)
        self._commented_posts: Dict[int, set] = {}
        
        self._db = Database()
        self._initialized = True
    
    async def start(self) -> None:
        """Запуск сервиса комментирования."""
        if self._running:
            logger.warning("Сервис комментирования уже запущен")
            return
        
        logger.info("=" * 50)
        logger.info("ЗАПУСК СЕРВИСА КОММЕНТИРОВАНИЯ")
        logger.info("=" * 50)
        
        self._running = True
        
        # Создаём главную задачу
        task = asyncio.create_task(self._commenting_loop())
        self._tasks.append(task)
        
        scheduler.register_task('commenting', task)
        
        logger.info("Комментирование запущено")
    
    async def stop(self) -> None:
        """Остановка сервиса."""
        if not self._running:
            return
        
        logger.info("Остановка сервиса комментирования...")
        
        self._running = False
        
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._tasks.clear()
        scheduler.unregister_tasks('commenting')
        
        logger.info("Сервис комментирования остановлен")
    
    def is_running(self) -> bool:
        """Проверка работы сервиса."""
        return self._running
    
    async def _commenting_loop(self) -> None:
        """Главный цикл комментирования."""
        logger.info("Запущен главный цикл комментирования")
        
        while self._running:
            try:
                await self._process_commenting_cycle()
                
                # Пауза между циклами
                delay = app_state.get_delay('cycle', 30, 90)
                logger.info(f"Пауза между циклами: {delay} сек")
                await asyncio.sleep(delay)
                
            except asyncio.CancelledError:
                logger.info("Цикл комментирования отменён")
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле комментирования: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _process_commenting_cycle(self) -> None:
        """Обработка одного цикла."""
        from services.account_service import account_service
        from services.channel_service import channel_service
        
        # Получаем клиенты для комментирования
        clients = account_service.get_comments_clients()
        
        if not clients:
            logger.warning("Нет активных аккаунтов для комментирования")
            return
        
        # Получаем каналы
        usernames = channel_service.get_all_usernames()
        
        if not usernames:
            logger.warning("Нет каналов для комментирования")
            return
        
        logger.info(f"Цикл: {len(clients)} аккаунтов, {len(usernames)} каналов")
        
        # Для каждого аккаунта
        for account_id, client in clients.items():
            if not self._running:
                break
            
            # Проверяем лимиты
            if not await account_service.check_limits(account_id, 'comments'):
                logger.debug(f"Аккаунт {account_id}: лимит исчерпан")
                continue
            
            # Выбираем случайный канал
            username = random.choice(usernames)
            
            try:
                await self._comment_on_channel(account_id, client, username)
            except Exception as e:
                logger.warning(f"Ошибка комментирования: {e}", exc_info=True)
            
            # Пауза между аккаунтами
            delay = app_state.get_delay('between_accounts', 15, 45)
            await asyncio.sleep(delay)
    
    async def _comment_on_channel(
        self, 
        account_id: int, 
        client: TelegramClient,
        username: str
    ) -> Optional[int]:
        """
        Прокомментировать пост в канале.
        
        Returns:
            comment_id если успешно, None если нет
        """
        from services.channel_service import channel_service
        from services.account_service import account_service
        
        logger.info(f"[Аккаунт {account_id}] Проверяю канал @{username}")
        
        # Резолвим канал
        channel = channel_service.get_channel_by_username(username)
        
        if not channel:
            channel = await channel_service.resolve_channel(username, client)
        
        if not channel:
            logger.warning(f"Не удалось получить информацию о @{username}")
            return None
        
        # Проверяем статус
        if channel.status != 'active':
            logger.debug(f"Канал @{username} не активен: {channel.status}")
            return None
        
        # Проверяем комментарии
        if not channel.has_comments:
            logger.debug(f"У канала @{username} нет комментариев")
            return None
        
        # ВЕРОЯТНОСТЬ КОММЕНТИРОВАНИЯ
        probability = app_state.config.get('commenting', {}).get('probability_percent', 100)
        
        if random.randint(1, 100) > probability:
            logger.info(f"[Аккаунт {account_id}] Пропуск по вероятности ({probability}%)")
            return None
        
        try:
            # Получаем entity канала
            channel_entity = await client.get_entity(username)
            
            # Получаем последние посты
            messages = await client.get_messages(channel_entity, limit=5)
            
            if not messages:
                logger.debug(f"Нет постов в @{username}")
                return None
            
            # Ищем пост для комментирования
            post = None
            for msg in messages:
                if not msg.text:
                    continue
                
                # Проверяем антидубликат
                if self._is_commented(channel.channel_id, msg.id):
                    continue
                
                # Проверяем в БД
                if await self._db.is_post_commented(channel.channel_id, msg.id):
                    self._mark_commented(channel.channel_id, msg.id)
                    continue
                
                post = msg
                break
            
            if not post:
                logger.debug(f"Нет новых постов для комментирования в @{username}")
                return None
            
            logger.info(f"[Аккаунт {account_id}] Найден пост #{post.id} в @{username}")
            
            # Генерируем комментарий через GPT
            comment_text = await gpt_service.generate_comment(post.text)
            
            if not comment_text:
                logger.warning(f"GPT не смог сгенерировать комментарий")
                return None
            
            if comment_text == "SKIP":
                logger.info(f"[Аккаунт {account_id}] Пост пропущен (SKIP от GPT)")
                self._mark_commented(channel.channel_id, post.id)
                return None
            
            # Получаем discussion group
            full = await client(functions.channels.GetFullChannelRequest(channel=channel_entity))
            
            if not full.full_chat.linked_chat_id:
                logger.warning(f"У канала @{username} нет discussion group")
                channel.has_comments = False
                return None
            
            discussion_entity = await client.get_entity(full.full_chat.linked_chat_id)
            
            # ИЗВЛЕКАЕМ peer_id ИЗ РЕАЛЬНОЙ ENTITY
            peer_id = discussion_entity.id
            
            logger.debug(f"Discussion entity: id={peer_id}, type={type(discussion_entity).__name__}")
            
            # Эмуляция чтения
            read_time = app_state.config.get('delays', {}).get('read_time', 5)
            logger.info(f"[Аккаунт {account_id}] Читаю пост... ({read_time} сек)")
            await asyncio.sleep(read_time)
            
            # Эмуляция набора
            type_time = app_state.config.get('delays', {}).get('type_time', 3)
            logger.info(f"[Аккаунт {account_id}] Печатаю... ({type_time} сек)")
            await asyncio.sleep(type_time)
            
            # ОТПРАВЛЯЕМ КОММЕНТАРИЙ
            logger.info(f"[Аккаунт {account_id}] Отправляю: {comment_text}")
            
            sent_message = await client.send_message(
                discussion_entity,
                comment_text,
                reply_to=post.id
            )
            
            # ИЗВЛЕКАЕМ comment_id И peer_id ИЗ ОТПРАВЛЕННОГО СООБЩЕНИЯ
            comment_id = sent_message.id
            
            # Приоритет: peer_id из sent_message, затем из entity
            if hasattr(sent_message, 'peer_id') and sent_message.peer_id:
                if hasattr(sent_message.peer_id, 'channel_id'):
                    # PeerChannel: -100 + channel_id
                    peer_id = -1000000000000 - sent_message.peer_id.channel_id
                elif hasattr(sent_message.peer_id, 'chat_id'):
                    # PeerChat: -chat_id
                    peer_id = -sent_message.peer_id.chat_id
                else:
                    # Используем peer_id из entity
                    pass
            
            # ВАЛИДАЦИЯ peer_id
            if peer_id is None or peer_id == 0:
                logger.error(f"[Аккаунт {account_id}] Не удалось получить peer_id! Комментарий НЕ сохранён.")
                return None
            
            logger.info(
                f"[Аккаунт {account_id}] ✓ Комментарий отправлен! "
                f"comment_id={comment_id}, peer_id={peer_id}"
            )
            
            # СОХРАНЯЕМ В БД
            try:
                await self._db.add_comment(
                    comment_id=comment_id,
                    peer_id=peer_id,
                    channel_id=channel.channel_id,
                    account_id=account_id,
                    post_id=post.id,
                    text=comment_text
                )
            except ValueError as e:
                logger.error(f"Ошибка сохранения комментария: {e}")
                return None
            
            # Обновляем антидубликат
            self._mark_commented(channel.channel_id, post.id)
            
            # Увеличиваем счётчик аккаунта
            await account_service.increment_comment_count(account_id, 'comments')
            
            return comment_id
            
        except FloodWaitError as e:
            logger.warning(f"[Аккаунт {account_id}] FloodWait {e.seconds} сек")
            await asyncio.sleep(min(e.seconds, 120))
            return None
        
        except ChatWriteForbiddenError:
            logger.warning(f"[Аккаунт {account_id}] Нет прав на комментирование в @{username}")
            return None
        
        except UserBannedInChannelError:
            logger.error(f"[Аккаунт {account_id}] ЗАБАНЕН в @{username}")
            await account_service.pause_account(account_id, 'comments', f'Бан в @{username}')
            return None
        
        except ChannelPrivateError:
            logger.warning(f"Канал @{username} стал приватным")
            return None
        
        except Exception as e:
            logger.error(f"[Аккаунт {account_id}] Ошибка: {e}", exc_info=True)
            return None
    
    def _is_commented(self, channel_id: int, post_id: int) -> bool:
        """Проверить закомментирован ли пост (кеш)."""
        if channel_id not in self._commented_posts:
            return False
        return post_id in self._commented_posts[channel_id]
    
    def _mark_commented(self, channel_id: int, post_id: int) -> None:
        """Пометить пост как закомментированный (кеш)."""
        if channel_id not in self._commented_posts:
            self._commented_posts[channel_id] = set()
        self._commented_posts[channel_id].add(post_id)
        
        # Ограничиваем размер кеша
        if len(self._commented_posts[channel_id]) > 1000:
            # Удаляем старые
            self._commented_posts[channel_id] = set(
                list(self._commented_posts[channel_id])[-500:]
            )


# Singleton
commenting_service = CommentingService()
