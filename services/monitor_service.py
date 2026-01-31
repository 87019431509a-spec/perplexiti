# -*- coding: utf-8 -*-
"""
Сервис мониторинга комментариев - ИСПРАВЛЕННЫЙ
Проверка удалений ТОЛЬКО через get_messages(peer_id, comment_id)
НИКАКИХ ложных удалений
"""

import asyncio
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError, MsgIdInvalidError, ChannelPrivateError,
    ChannelInvalidError, ChatIdInvalidError, RPCError
)
from telethon.tl.types import MessageEmpty

from core.logger import comments_logger as logger
from core.state import app_state
from core.scheduler import scheduler
from core.database import Database


class CheckResult(Enum):
    """Результат проверки комментария."""
    OK = "ok"           # Комментарий существует
    DELETED = "deleted" # Комментарий ТОЧНО удалён
    UNKNOWN = "unknown" # Невозможно проверить (НЕ применять санкции!)


class MonitorService:
    """Сервис мониторинга удалений комментариев."""
    
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
        
        self._db = Database()
        
        # Статистика
        self._stats = {
            'checked': 0,
            'ok': 0,
            'deleted': 0,
            'unknown': 0
        }
        
        self._initialized = True
    
    async def start(self) -> None:
        """Запуск мониторинга."""
        if self._running:
            logger.warning("Мониторинг уже запущен")
            return
        
        logger.info("=" * 50)
        logger.info("ЗАПУСК МОНИТОРИНГА КОММЕНТАРИЕВ")
        logger.info("=" * 50)
        
        self._running = True
        
        task = asyncio.create_task(self._monitor_loop())
        self._tasks.append(task)
        
        scheduler.register_task('monitor', task)
        
        logger.info("Мониторинг запущен")
    
    async def stop(self) -> None:
        """Остановка мониторинга."""
        if not self._running:
            return
        
        logger.info("Остановка мониторинга...")
        
        self._running = False
        
        for task in self._tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        
        self._tasks.clear()
        scheduler.unregister_tasks('monitor')
        
        logger.info("Мониторинг остановлен")
    
    def is_running(self) -> bool:
        return self._running
    
    async def _monitor_loop(self) -> None:
        """Главный цикл мониторинга."""
        logger.info("Запущен цикл мониторинга")
        
        while self._running:
            try:
                await self._check_comments()
                
                # Интервал из конфига
                interval = app_state.config.get('monitor', {}).get(
                    'delete_check_interval_sec', 60
                )
                
                logger.debug(f"Следующая проверка через {interval} сек")
                await asyncio.sleep(interval)
                
            except asyncio.CancelledError:
                logger.info("Цикл мониторинга отменён")
                break
            except Exception as e:
                logger.error(f"Ошибка мониторинга: {e}", exc_info=True)
                await asyncio.sleep(30)
    
    async def _check_comments(self) -> None:
        """Проверка комментариев."""
        from services.account_service import account_service
        
        # Получаем комментарии для проверки
        comments = await self._db.get_pending_comments(limit=50)
        
        if not comments:
            logger.debug("Нет комментариев для проверки")
            return
        
        logger.info(f"Проверка {len(comments)} комментариев...")
        
        # Получаем клиент для проверки
        clients = account_service.get_comments_clients()
        
        if not clients:
            logger.warning("Нет клиентов для проверки комментариев")
            return
        
        # Берём первый доступный клиент
        client = list(clients.values())[0]
        
        for comment in comments:
            if not self._running:
                break
            
            result = await self._check_single_comment(client, comment)
            
            self._stats['checked'] += 1
            
            if result == CheckResult.OK:
                self._stats['ok'] += 1
                await self._db.mark_comment_checked(
                    comment['comment_id'],
                    comment['peer_id']
                )
                logger.info(
                    f"[CHECK_OK] comment_id={comment['comment_id']} "
                    f"peer_id={comment['peer_id']} - существует"
                )
                
            elif result == CheckResult.DELETED:
                self._stats['deleted'] += 1
                await self._handle_deletion(comment)
                logger.warning(
                    f"[CHECK_DELETED] comment_id={comment['comment_id']} "
                    f"peer_id={comment['peer_id']} - УДАЛЁН"
                )
                
            else:  # UNKNOWN
                self._stats['unknown'] += 1
                # НЕ применяем санкции! Оставляем для повторной проверки
                logger.info(
                    f"[CHECK_UNKNOWN] comment_id={comment['comment_id']} "
                    f"peer_id={comment['peer_id']} - невозможно проверить"
                )
            
            # Пауза между проверками
            await asyncio.sleep(1)
    
    async def _check_single_comment(
        self,
        client: TelegramClient,
        comment: Dict[str, Any]
    ) -> CheckResult:
        """
        Проверить существование одного комментария.
        
        ПРАВИЛА:
        - CheckResult.OK = комментарий точно существует
        - CheckResult.DELETED = комментарий точно удалён (get_messages вернул пусто БЕЗ ошибок)
        - CheckResult.UNKNOWN = невозможно проверить (любая ошибка, FloodWait, нет доступа)
        
        КРИТИЧЕСКИ ВАЖНО:
        - DELETED возвращается ТОЛЬКО при подтверждённом отсутствии
        - При ЛЮБОЙ ошибке возвращаем UNKNOWN
        """
        peer_id = comment.get('peer_id')
        comment_id = comment.get('comment_id')
        channel_id = comment.get('channel_id')
        
        # Валидация
        if peer_id is None or peer_id == 0:
            logger.warning(f"Невалидный peer_id: {peer_id}")
            return CheckResult.UNKNOWN
        
        if comment_id is None or comment_id <= 0:
            logger.warning(f"Невалидный comment_id: {comment_id}")
            return CheckResult.UNKNOWN
        
        # ОСНОВНОЙ МЕТОД: Проверка через peer_id
        try:
            # Получаем entity по peer_id
            try:
                entity = await client.get_entity(peer_id)
            except ValueError as e:
                logger.debug(f"ValueError при get_entity({peer_id}): {e}")
                return CheckResult.UNKNOWN
            
            # Получаем сообщение
            messages = await client.get_messages(entity, ids=[comment_id])
            
            # Анализируем результат
            if not messages:
                # Пустой список = сообщение удалено
                logger.debug(f"get_messages вернул пустой список - комментарий удалён")
                return CheckResult.DELETED
            
            msg = messages[0]
            
            if msg is None:
                # None = сообщение удалено
                logger.debug(f"get_messages вернул None - комментарий удалён")
                return CheckResult.DELETED
            
            if isinstance(msg, MessageEmpty):
                # MessageEmpty = сообщение удалено
                logger.debug(f"get_messages вернул MessageEmpty - комментарий удалён")
                return CheckResult.DELETED
            
            if hasattr(msg, 'id') and msg.id == 0:
                # id=0 = сообщение удалено
                logger.debug(f"msg.id == 0 - комментарий удалён")
                return CheckResult.DELETED
            
            # Проверяем что ID совпадает
            if hasattr(msg, 'id') and msg.id == comment_id:
                # Сообщение существует!
                return CheckResult.OK
            else:
                # ID не совпадает - странная ситуация, не считаем удалением
                logger.warning(f"ID не совпадает: ожидали {comment_id}, получили {msg.id}")
                return CheckResult.UNKNOWN
            
        except MsgIdInvalidError:
            # ID невалидный - НЕ означает удаление!
            logger.debug(f"MsgIdInvalidError - НЕ удаление, возвращаем UNKNOWN")
            return CheckResult.UNKNOWN
        
        except FloodWaitError as e:
            logger.warning(f"FloodWait {e.seconds} сек - возвращаем UNKNOWN")
            await asyncio.sleep(min(e.seconds, 30))
            return CheckResult.UNKNOWN
        
        except ChannelPrivateError:
            logger.debug(f"ChannelPrivateError - нет доступа, UNKNOWN")
            return CheckResult.UNKNOWN
        
        except ChannelInvalidError:
            logger.debug(f"ChannelInvalidError - UNKNOWN")
            return CheckResult.UNKNOWN
        
        except ChatIdInvalidError:
            logger.debug(f"ChatIdInvalidError - UNKNOWN")
            return CheckResult.UNKNOWN
        
        except RPCError as e:
            logger.warning(f"RPCError: {e} - возвращаем UNKNOWN")
            return CheckResult.UNKNOWN
        
        except ConnectionError as e:
            logger.warning(f"ConnectionError: {e} - UNKNOWN")
            return CheckResult.UNKNOWN
        
        except asyncio.TimeoutError:
            logger.warning(f"TimeoutError - UNKNOWN")
            return CheckResult.UNKNOWN
        
        except asyncio.CancelledError:
            # Пробрасываем отмену
            raise
        
        except Exception as e:
            # ЛЮБАЯ другая ошибка = UNKNOWN (не DELETED!)
            logger.warning(f"Неожиданная ошибка проверки: {e} - возвращаем UNKNOWN", exc_info=True)
            return CheckResult.UNKNOWN
    
    async def _handle_deletion(self, comment: Dict[str, Any]) -> None:
        """Обработка удалённого комментария."""
        from services.channel_service import channel_service
        
        comment_id = comment['comment_id']
        peer_id = comment['peer_id']
        channel_id = comment['channel_id']
        
        # Помечаем в БД
        await self._db.mark_comment_deleted(comment_id, peer_id)
        
        # Увеличиваем счётчик удалений канала
        deletion_count = await channel_service.increment_deletions(channel_id)
        
        # Получаем настройки санкций
        sanctions = app_state.config.get('sanctions', {})
        deletions_to_sleep = sanctions.get('deletions_to_sleep', 1)
        deletions_to_disable = sanctions.get('deletions_to_disable', 3)
        sleep_duration = sanctions.get('sleep_duration_min', 60)
        
        # Применяем санкции
        if deletion_count >= deletions_to_disable:
            await channel_service.disable_channel(
                channel_id,
                f"Превышен лимит удалений: {deletion_count}"
            )
            logger.error(f"Канал {channel_id} ОТКЛЮЧЁН: {deletion_count} удалений")
            
        elif deletion_count >= deletions_to_sleep:
            await channel_service.set_channel_sleep(channel_id, sleep_duration)
            logger.warning(f"Канал {channel_id} в СПЯЧКЕ на {sleep_duration} мин")
        
        # Логируем действие
        await self._db.add_action(
            action_type='comment_deleted',
            channel_id=channel_id,
            details=f"comment_id={comment_id}, peer_id={peer_id}, deletions={deletion_count}"
        )
    
    def get_stats(self) -> Dict[str, int]:
        """Получить статистику."""
        return dict(self._stats)


# Singleton
monitor_service = MonitorService()
