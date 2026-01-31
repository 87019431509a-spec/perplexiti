# -*- coding: utf-8 -*-
"""
Сервис прогрева аккаунтов - ИСПРАВЛЕННЫЙ
Использует ТОЛЬКО пул прогрева
Корректная обработка Invalid Peer
"""

import os
import asyncio
import random
from typing import Optional, List, Dict, Any, Set
from datetime import datetime, timedelta
from telethon import TelegramClient, functions, types
from telethon.errors import (
    FloodWaitError, ChannelPrivateError, ChatIdInvalidError,
    UserBannedInChannelError, PeerIdInvalidError, RPCError
)

from core.logger import warmup_logger as logger
from core.state import app_state
from core.scheduler import scheduler
from core.database import Database


class WarmupService:
    """Сервис прогрева аккаунтов."""
    
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
        
        # Цели прогрева
        self._channels: List[str] = []
        self._chats: List[str] = []
        
        # Уровни прогрева аккаунтов
        self._warmup_levels: Dict[int, int] = {}
        
        self._db = Database()
        self._project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        self._initialized = True
    
    async def start(self) -> None:
        """Запуск сервиса прогрева."""
        if self._running:
            logger.warning("Сервис прогрева уже запущен")
            return
        
        logger.info("=" * 50)
        logger.info("ЗАПУСК СЕРВИСА ПРОГРЕВА")
        logger.info("=" * 50)
        
        # Загрузка целей
        await self._load_targets()
        
        if not self._channels and not self._chats:
            logger.error("Нет целей для прогрева! Добавьте каналы/чаты в папки.")
            return
        
        self._running = True
        
        # Создаём задачу прогрева
        task = asyncio.create_task(self._warmup_loop())
        self._tasks.append(task)
        
        scheduler.register_task('warmup', task)
        
        logger.info(f"Прогрев запущен: {len(self._channels)} каналов, {len(self._chats)} чатов")
    
    async def stop(self) -> None:
        """Остановка сервиса."""
        if not self._running:
            return
        
        logger.info("Остановка сервиса прогрева...")
        
        self._running = False
        
        # Отмена задач
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._tasks.clear()
        scheduler.unregister_tasks('warmup')
        
        logger.info("Сервис прогрева остановлен")
    
    def is_running(self) -> bool:
        """Проверка работы сервиса."""
        return self._running
    
    async def _load_targets(self) -> None:
        """Загрузка целей прогрева из папок."""
        self._channels.clear()
        self._chats.clear()
        
        # Каналы
        channels_folder = os.path.join(self._project_root, 'каналы_прогрев')
        if os.path.exists(channels_folder):
            for filename in os.listdir(channels_folder):
                if filename.endswith('.txt'):
                    filepath = os.path.join(channels_folder, filename)
                    self._channels.extend(self._read_targets_file(filepath))
        
        # Чаты
        chats_folder = os.path.join(self._project_root, 'чаты_прогрев')
        if os.path.exists(chats_folder):
            for filename in os.listdir(chats_folder):
                if filename.endswith('.txt'):
                    filepath = os.path.join(chats_folder, filename)
                    self._chats.extend(self._read_targets_file(filepath))
        
        logger.info(f"Загружено целей: {len(self._channels)} каналов, {len(self._chats)} чатов")
    
    def _read_targets_file(self, filepath: str) -> List[str]:
        """Чтение файла с целями."""
        targets = []
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Извлекаем username
                        if 't.me/' in line:
                            line = line.split('t.me/')[-1].split('/')[0].split('?')[0]
                        if line.startswith('@'):
                            line = line[1:]
                        if line:
                            targets.append(line)
        except Exception as e:
            logger.warning(f"Ошибка чтения файла {filepath}: {e}")
        
        return targets
    
    async def _warmup_loop(self) -> None:
        """Главный цикл прогрева."""
        logger.info("Запущен главный цикл прогрева")
        
        while self._running:
            try:
                await self._process_warmup_cycle()
                
                # Пауза между циклами
                delay = app_state.get_delay('warmup_cycle', 60, 180)
                logger.info(f"Пауза между циклами прогрева: {delay} сек")
                await asyncio.sleep(delay)
                
            except asyncio.CancelledError:
                logger.info("Цикл прогрева отменён")
                break
            except Exception as e:
                logger.error(f"Ошибка в цикле прогрева: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _process_warmup_cycle(self) -> None:
        """Обработка одного цикла прогрева."""
        from services.account_service import account_service
        
        # ВАЖНО: Получаем клиенты ТОЛЬКО из пула прогрева!
        clients = account_service.get_warmup_clients()
        
        if not clients:
            logger.warning("Нет активных аккаунтов для прогрева")
            return
        
        logger.info(f"Цикл прогрева: {len(clients)} аккаунтов")
        
        for account_id, client in clients.items():
            if not self._running:
                break
            
            try:
                await self._warmup_account(account_id, client)
            except Exception as e:
                logger.warning(f"Ошибка прогрева аккаунта {account_id}: {e}", exc_info=True)
            
            # Пауза между аккаунтами
            delay = app_state.get_delay('between_accounts', 10, 30)
            await asyncio.sleep(delay)
    
    async def _warmup_account(self, account_id: int, client: TelegramClient) -> None:
        """Прогрев одного аккаунта."""
        
        # Получаем уровень прогрева
        level = await self._get_warmup_level(account_id)
        
        logger.info(f"Аккаунт {account_id} | Уровень прогрева: {level}/100")
        
        if level >= 100:
            logger.info(f"Аккаунт {account_id} полностью прогрет!")
            return
        
        # Выбираем действие по уровню
        actions_done = 0
        max_actions = app_state.config.get('warmup', {}).get('actions_per_session', 5)
        
        while actions_done < max_actions and self._running:
            try:
                action_done = await self._perform_action(account_id, client, level)
                
                if action_done:
                    actions_done += 1
                    # Увеличиваем уровень
                    increment = app_state.config.get('warmup', {}).get('level_increment', 2)
                    level = min(100, level + increment)
                    await self._set_warmup_level(account_id, level)
                    logger.info(f"Аккаунт {account_id} | Уровень: {level}/100 (+{increment})")
                
                # Пауза между действиями
                min_delay = app_state.config.get('warmup', {}).get('min_delay', 30)
                max_delay = app_state.config.get('warmup', {}).get('max_delay', 120)
                delay = random.randint(min_delay, max_delay)
                
                logger.debug(f"Пауза {delay} сек...")
                await asyncio.sleep(delay)
                
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning(f"Ошибка действия прогрева: {e}", exc_info=True)
                await asyncio.sleep(10)
    
    async def _perform_action(self, account_id: int, client: TelegramClient, level: int) -> bool:
        """
        Выполнить действие прогрева в зависимости от уровня.
        
        Возвращает True если действие успешно.
        """
        levels = app_state.config.get('warmup', {}).get('levels', {})
        
        read_only = levels.get('read_only', 20)
        reactions = levels.get('reactions', 40)
        joins = levels.get('joins', 60)
        comments = levels.get('comments', 80)
        
        if level < read_only:
            # Только чтение
            return await self._perform_read_action(account_id, client)
        
        elif level < reactions:
            # Чтение + реакции
            if random.random() < 0.3:
                return await self._perform_reaction_action(account_id, client)
            else:
                return await self._perform_read_action(account_id, client)
        
        elif level < joins:
            # + вступления
            action = random.choice(['read', 'read', 'reaction', 'join'])
            if action == 'join':
                return await self._perform_join_action(account_id, client)
            elif action == 'reaction':
                return await self._perform_reaction_action(account_id, client)
            else:
                return await self._perform_read_action(account_id, client)
        
        elif level < comments:
            # + комментарии
            action = random.choice(['read', 'reaction', 'join', 'comment'])
            if action == 'comment':
                return await self._perform_comment_action(account_id, client)
            elif action == 'join':
                return await self._perform_join_action(account_id, client)
            elif action == 'reaction':
                return await self._perform_reaction_action(account_id, client)
            else:
                return await self._perform_read_action(account_id, client)
        
        else:
            # Полная активность
            return await self._perform_read_action(account_id, client)
    
    async def _perform_read_action(self, account_id: int, client: TelegramClient) -> bool:
        """Действие: чтение истории."""
        target = self._get_random_target()
        if not target:
            logger.warning("Нет целей для чтения")
            return False
        
        logger.info(f"[{account_id}] Чтение истории: @{target}")
        
        try:
            entity = await self._get_entity_safe(client, target)
            if not entity:
                logger.warning(f"[{account_id}] Пропущено @{target} - не удалось получить entity")
                return False
            
            # Проверяем тип entity
            if not self._is_valid_peer(entity):
                logger.warning(f"[{account_id}] Пропущено @{target} - невалидный peer (бот или пользователь)")
                return False
            
            # Читаем историю
            messages = await client.get_messages(entity, limit=random.randint(5, 20))
            
            if messages:
                logger.info(f"[{account_id}] Прочитано {len(messages)} сообщений из @{target}")
                
                # Эмуляция просмотра
                await asyncio.sleep(random.uniform(2, 5))
                
                return True
            else:
                logger.debug(f"[{account_id}] Нет сообщений в @{target}")
                return False
            
        except FloodWaitError as e:
            logger.warning(f"[{account_id}] FloodWait {e.seconds} сек при чтении @{target}")
            await asyncio.sleep(min(e.seconds, 60))
            return False
        
        except (ChannelPrivateError, ChatIdInvalidError):
            logger.warning(f"[{account_id}] Канал @{target} недоступен")
            return False
        
        except PeerIdInvalidError:
            logger.warning(f"[{account_id}] Пропущено @{target} - Invalid Peer")
            return False
        
        except Exception as e:
            logger.warning(f"[{account_id}] Ошибка чтения @{target}: {e}", exc_info=True)
            return False
    
    async def _perform_reaction_action(self, account_id: int, client: TelegramClient) -> bool:
        """Действие: поставить реакцию."""
        target = self._get_random_target()
        if not target:
            return False
        
        logger.info(f"[{account_id}] Ставлю реакцию в @{target}")
        
        try:
            entity = await self._get_entity_safe(client, target)
            if not entity:
                logger.warning(f"[{account_id}] Пропущено @{target} - не удалось получить entity")
                return False
            
            if not self._is_valid_peer(entity):
                logger.warning(f"[{account_id}] Пропущено @{target} - невалидный peer")
                return False
            
            # Получаем последние посты
            messages = await client.get_messages(entity, limit=10)
            
            if not messages:
                logger.debug(f"[{account_id}] Нет сообщений для реакции в @{target}")
                return False
            
            # Выбираем случайное сообщение
            msg = random.choice(messages)
            
            # Выбираем реакцию
            reactions = ['👍', '❤️', '🔥', '👏', '🎉', '😍', '🤔']
            reaction = random.choice(reactions)
            
            # Отправляем реакцию
            await client(functions.messages.SendReactionRequest(
                peer=entity,
                msg_id=msg.id,
                reaction=[types.ReactionEmoji(emoticon=reaction)]
            ))
            
            logger.info(f"[{account_id}] Реакция {reaction} отправлена на пост в @{target}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"[{account_id}] FloodWait {e.seconds} сек")
            await asyncio.sleep(min(e.seconds, 60))
            return False
        
        except PeerIdInvalidError:
            logger.warning(f"[{account_id}] Пропущено @{target} - Invalid Peer при реакции")
            return False
        
        except Exception as e:
            logger.warning(f"[{account_id}] Ошибка реакции в @{target}: {e}", exc_info=True)
            return True  # Считаем попытку за действие
    
    async def _perform_join_action(self, account_id: int, client: TelegramClient) -> bool:
        """Действие: вступить в канал/чат."""
        target = self._get_random_target()
        if not target:
            return False
        
        logger.info(f"[{account_id}] Вступаю в @{target}")
        
        try:
            # Пробуем вступить
            await client(functions.channels.JoinChannelRequest(channel=target))
            
            logger.info(f"[{account_id}] Успешно вступил в @{target}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"[{account_id}] FloodWait {e.seconds} сек при вступлении")
            await asyncio.sleep(min(e.seconds, 60))
            return False
        
        except (ChannelPrivateError, ChatIdInvalidError):
            logger.warning(f"[{account_id}] Канал @{target} приватный или недоступен")
            return False
        
        except PeerIdInvalidError:
            logger.warning(f"[{account_id}] Пропущено @{target} - Invalid Peer при вступлении")
            return False
        
        except Exception as e:
            logger.warning(f"[{account_id}] Ошибка вступления в @{target}: {e}", exc_info=True)
            return False
    
    async def _perform_comment_action(self, account_id: int, client: TelegramClient) -> bool:
        """Действие: написать комментарий (осторожно)."""
        # Выбираем только каналы (не чаты)
        if not self._channels:
            return await self._perform_read_action(account_id, client)
        
        target = random.choice(self._channels)
        
        logger.info(f"[{account_id}] Пробую комментарий в @{target}")
        
        try:
            entity = await self._get_entity_safe(client, target)
            if not entity:
                return False
            
            if not self._is_valid_peer(entity):
                logger.warning(f"[{account_id}] Пропущено @{target} - невалидный peer для комментария")
                return False
            
            # Получаем полную информацию о канале
            full = await client(functions.channels.GetFullChannelRequest(channel=entity))
            
            if not full.full_chat.linked_chat_id:
                logger.debug(f"[{account_id}] У канала @{target} нет обсуждения")
                return await self._perform_read_action(account_id, client)
            
            # Получаем discussion group
            discussion = await client.get_entity(full.full_chat.linked_chat_id)
            
            # Получаем последний пост
            messages = await client.get_messages(entity, limit=5)
            
            if not messages:
                return False
            
            post = random.choice(messages)
            
            # Простой комментарий
            simple_comments = [
                "👍", "❤️", "🔥", "интересно", "круто", "ого", "вау",
                "спасибо", "класс", "супер", "топ", "💯"
            ]
            comment = random.choice(simple_comments)
            
            # Отправляем
            await client.send_message(
                discussion,
                comment,
                reply_to=post.id
            )
            
            logger.info(f"[{account_id}] Комментарий '{comment}' отправлен в @{target}")
            return True
            
        except FloodWaitError as e:
            logger.warning(f"[{account_id}] FloodWait {e.seconds} сек")
            await asyncio.sleep(min(e.seconds, 60))
            return False
        
        except PeerIdInvalidError:
            logger.warning(f"[{account_id}] Пропущено @{target} - Invalid Peer при комментарии")
            return False
        
        except Exception as e:
            logger.warning(f"[{account_id}] Ошибка комментария в @{target}: {e}", exc_info=True)
            return False
    
    def _get_random_target(self) -> Optional[str]:
        """Получить случайную цель."""
        all_targets = self._channels + self._chats
        if not all_targets:
            return None
        return random.choice(all_targets)
    
    async def _get_entity_safe(self, client: TelegramClient, target: str) -> Optional[Any]:
        """Безопасное получение entity."""
        try:
            return await client.get_entity(target)
        except PeerIdInvalidError:
            logger.debug(f"Invalid Peer: {target}")
            return None
        except (ChannelPrivateError, ChatIdInvalidError):
            logger.debug(f"Недоступен: {target}")
            return None
        except ValueError as e:
            logger.debug(f"ValueError для {target}: {e}")
            return None
        except Exception as e:
            logger.debug(f"Ошибка get_entity для {target}: {e}")
            return None
    
    def _is_valid_peer(self, entity: Any) -> bool:
        """Проверка что entity валиден для прогрева."""
        # Не работаем с ботами
        if hasattr(entity, 'bot') and entity.bot:
            return False
        
        # Не работаем с обычными пользователями
        if hasattr(entity, 'first_name') and not hasattr(entity, 'broadcast'):
            return False
        
        # Каналы и чаты - ОК
        return True
    
    async def _get_warmup_level(self, account_id: int) -> int:
        """Получить уровень прогрева аккаунта."""
        # Сначала из кеша
        if account_id in self._warmup_levels:
            return self._warmup_levels[account_id]
        
        # Потом из БД
        try:
            account = await self._db.get_account(account_id)
            if account:
                level = account.get('warmup_level', 0)
                self._warmup_levels[account_id] = level
                return level
        except Exception as e:
            logger.warning(f"Ошибка получения уровня прогрева: {e}", exc_info=True)
        
        return 0
    
    async def _set_warmup_level(self, account_id: int, level: int) -> None:
        """Установить уровень прогрева."""
        self._warmup_levels[account_id] = level
        
        try:
            await self._db.update_account(account_id, {'warmup_level': level})
        except Exception as e:
            logger.warning(f"Ошибка сохранения уровня прогрева: {e}", exc_info=True)


# Singleton
warmup_service = WarmupService()
