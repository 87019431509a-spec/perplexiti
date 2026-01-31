# -*- coding: utf-8 -*-
"""
База данных SQLite
Таблицы: accounts, channels, comments, actions
Жёсткий контракт peer_id
"""

import os
import asyncio
import aiosqlite
from typing import Optional, Dict, Any, List
from datetime import datetime

from core.logger import logger


class Database:
    """Асинхронная работа с SQLite."""
    
    _instance = None
    _db: Optional[aiosqlite.Connection] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        data_dir = os.path.join(project_root, 'data')
        os.makedirs(data_dir, exist_ok=True)
        
        self._db_path = os.path.join(data_dir, 'bot.db')
        self._lock = asyncio.Lock()
        self._initialized = True
    
    async def init(self) -> None:
        """Инициализация БД и создание таблиц."""
        async with self._lock:
            self._db = await aiosqlite.connect(self._db_path)
            self._db.row_factory = aiosqlite.Row
            
            await self._create_tables()
            
            logger.info(f"База данных инициализирована: {self._db_path}")
    
    async def _create_tables(self) -> None:
        """Создание таблиц."""
        
        # Аккаунты
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT UNIQUE,
                session_file TEXT,
                pool_type TEXT DEFAULT 'comments',
                status TEXT DEFAULT 'active',
                warmup_level INTEGER DEFAULT 0,
                comments_today INTEGER DEFAULT 0,
                last_comment_at TEXT,
                last_error TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Каналы
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS channels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER UNIQUE,
                username TEXT,
                title TEXT,
                discussion_id INTEGER,
                status TEXT DEFAULT 'active',
                deletion_count INTEGER DEFAULT 0,
                last_post_at TEXT,
                last_comment_at TEXT,
                sleep_until TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Комментарии - ЖЁСТКИЙ КОНТРАКТ peer_id
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                comment_id INTEGER NOT NULL,
                peer_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                post_id INTEGER NOT NULL,
                text TEXT,
                status TEXT DEFAULT 'sent',
                checked_at TEXT,
                deleted_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(peer_id, comment_id)
            )
        """)
        
        # Индексы для быстрого поиска
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_comments_status 
            ON comments(status)
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_comments_channel 
            ON comments(channel_id)
        """)
        
        await self._db.execute("""
            CREATE INDEX IF NOT EXISTS idx_comments_peer 
            ON comments(peer_id, comment_id)
        """)
        
        # Действия (лог)
        await self._db.execute("""
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT,
                account_id INTEGER,
                channel_id INTEGER,
                details TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        await self._db.commit()
    
    async def add_comment(
        self,
        comment_id: int,
        peer_id: int,
        channel_id: int,
        account_id: int,
        post_id: int,
        text: str = ''
    ) -> int:
        """
        Добавить комментарий в БД.
        
        КОНТРАКТ (ЖЁСТКИЙ):
        - peer_id ОБЯЗАТЕЛЕН и не может быть None или 0
        - comment_id ОБЯЗАТЕЛЕН и не может быть None или 0
        - channel_id, account_id, post_id ОБЯЗАТЕЛЬНЫ
        
        peer_id может быть отрицательным (супергруппы -100xxxx)
        
        Raises:
            ValueError: Если peer_id или comment_id невалидны
        """
        # ЖЁСТКАЯ ВАЛИДАЦИЯ
        if peer_id is None or peer_id == 0:
            error_msg = f"peer_id обязателен и не может быть 0 (получено: {peer_id})"
            logger.error(f"[DATABASE] {error_msg}")
            raise ValueError(error_msg)
        
        if comment_id is None or comment_id <= 0:
            error_msg = f"comment_id обязателен и должен быть > 0 (получено: {comment_id})"
            logger.error(f"[DATABASE] {error_msg}")
            raise ValueError(error_msg)
        
        if channel_id is None or channel_id == 0:
            error_msg = f"channel_id обязателен (получено: {channel_id})"
            logger.error(f"[DATABASE] {error_msg}")
            raise ValueError(error_msg)
        
        if account_id is None or account_id <= 0:
            error_msg = f"account_id обязателен (получено: {account_id})"
            logger.error(f"[DATABASE] {error_msg}")
            raise ValueError(error_msg)
        
        if post_id is None or post_id <= 0:
            error_msg = f"post_id обязателен (получено: {post_id})"
            logger.error(f"[DATABASE] {error_msg}")
            raise ValueError(error_msg)
        
        async with self._lock:
            try:
                cursor = await self._db.execute("""
                    INSERT INTO comments 
                    (comment_id, peer_id, channel_id, account_id, post_id, text, status)
                    VALUES (?, ?, ?, ?, ?, ?, 'sent')
                """, (comment_id, peer_id, channel_id, account_id, post_id, text))
                
                await self._db.commit()
                
                logger.debug(
                    f"[DATABASE] Комментарий сохранён: "
                    f"comment_id={comment_id}, peer_id={peer_id}, channel_id={channel_id}"
                )
                
                return cursor.lastrowid
                
            except aiosqlite.IntegrityError:
                logger.warning(f"[DATABASE] Комментарий уже существует: peer_id={peer_id}, comment_id={comment_id}")
                return 0
    
    async def get_pending_comments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить комментарии для проверки."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT * FROM comments 
                WHERE status = 'sent'
                ORDER BY created_at ASC
                LIMIT ?
            """, (limit,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def mark_comment_deleted(self, comment_id: int, peer_id: int) -> None:
        """Пометить комментарий как удалённый."""
        async with self._lock:
            await self._db.execute("""
                UPDATE comments 
                SET status = 'deleted', deleted_at = ?
                WHERE comment_id = ? AND peer_id = ?
            """, (datetime.now().isoformat(), comment_id, peer_id))
            
            await self._db.commit()
            
            logger.info(f"[DATABASE] Комментарий помечен удалённым: peer_id={peer_id}, comment_id={comment_id}")
    
    async def mark_comment_checked(self, comment_id: int, peer_id: int) -> None:
        """Обновить время проверки комментария."""
        async with self._lock:
            await self._db.execute("""
                UPDATE comments 
                SET checked_at = ?
                WHERE comment_id = ? AND peer_id = ?
            """, (datetime.now().isoformat(), comment_id, peer_id))
            
            await self._db.commit()
    
    async def is_post_commented(self, channel_id: int, post_id: int) -> bool:
        """Проверить был ли пост уже прокомментирован."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT COUNT(*) FROM comments 
                WHERE channel_id = ? AND post_id = ?
            """, (channel_id, post_id))
            
            row = await cursor.fetchone()
            return row[0] > 0
    
    async def get_channel(self, channel_id: int) -> Optional[Dict[str, Any]]:
        """Получить информацию о канале."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT * FROM channels WHERE channel_id = ?
            """, (channel_id,))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def add_channel(
        self,
        channel_id: int,
        username: str = '',
        title: str = '',
        discussion_id: int = 0
    ) -> int:
        """Добавить канал."""
        async with self._lock:
            try:
                cursor = await self._db.execute("""
                    INSERT INTO channels (channel_id, username, title, discussion_id)
                    VALUES (?, ?, ?, ?)
                """, (channel_id, username, title, discussion_id))
                
                await self._db.commit()
                return cursor.lastrowid
                
            except aiosqlite.IntegrityError:
                # Канал уже существует
                return 0
    
    async def update_channel(self, channel_id: int, data: Dict[str, Any]) -> None:
        """Обновить данные канала."""
        if not data:
            return
        
        async with self._lock:
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            values = list(data.values()) + [channel_id]
            
            await self._db.execute(f"""
                UPDATE channels 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            """, values)
            
            await self._db.commit()
    
    async def increment_channel_deletions(self, channel_id: int) -> int:
        """Увеличить счётчик удалений канала."""
        async with self._lock:
            # Получаем текущее значение
            cursor = await self._db.execute("""
                SELECT deletion_count FROM channels WHERE channel_id = ?
            """, (channel_id,))
            
            row = await cursor.fetchone()
            current = row[0] if row else 0
            new_count = current + 1
            
            # Обновляем
            await self._db.execute("""
                UPDATE channels 
                SET deletion_count = ?, updated_at = CURRENT_TIMESTAMP
                WHERE channel_id = ?
            """, (new_count, channel_id))
            
            await self._db.commit()
            
            return new_count
    
    async def get_account(self, account_id: int) -> Optional[Dict[str, Any]]:
        """Получить информацию об аккаунте."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT * FROM accounts WHERE id = ?
            """, (account_id,))
            
            row = await cursor.fetchone()
            return dict(row) if row else None
    
    async def update_account(self, account_id: int, data: Dict[str, Any]) -> None:
        """Обновить данные аккаунта."""
        if not data:
            return
        
        async with self._lock:
            set_clause = ', '.join([f"{k} = ?" for k in data.keys()])
            values = list(data.values()) + [account_id]
            
            await self._db.execute(f"""
                UPDATE accounts 
                SET {set_clause}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, values)
            
            await self._db.commit()
    
    async def add_action(
        self,
        action_type: str,
        account_id: int = 0,
        channel_id: int = 0,
        details: str = ''
    ) -> None:
        """Добавить запись в лог действий."""
        async with self._lock:
            await self._db.execute("""
                INSERT INTO actions (action_type, account_id, channel_id, details)
                VALUES (?, ?, ?, ?)
            """, (action_type, account_id, channel_id, details))
            
            await self._db.commit()
    
    async def get_stats(self) -> Dict[str, int]:
        """Получить статистику."""
        async with self._lock:
            stats = {}
            
            # Комментарии
            cursor = await self._db.execute("""
                SELECT COUNT(*) FROM comments WHERE status = 'sent'
            """)
            stats['comments_sent'] = (await cursor.fetchone())[0]
            
            cursor = await self._db.execute("""
                SELECT COUNT(*) FROM comments WHERE status = 'deleted'
            """)
            stats['comments_deleted'] = (await cursor.fetchone())[0]
            
            # Каналы
            cursor = await self._db.execute("""
                SELECT COUNT(*) FROM channels WHERE status = 'sleep'
            """)
            stats['channels_sleeping'] = (await cursor.fetchone())[0]
            
            cursor = await self._db.execute("""
                SELECT COUNT(*) FROM channels WHERE status = 'disabled'
            """)
            stats['channels_disabled'] = (await cursor.fetchone())[0]
            
            return stats
    
    async def get_stats_today(self) -> Dict[str, int]:
        """Получить статистику за сегодня."""
        async with self._lock:
            stats = {'sent': 0, 'success': 0, 'deleted': 0, 'warmup_actions': 0}
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            try:
                # Комментарии отправленные сегодня
                cursor = await self._db.execute("""
                    SELECT COUNT(*) FROM comments 
                    WHERE date(created_at) = ?
                """, (today,))
                stats['sent'] = (await cursor.fetchone())[0]
                
                # Успешные (не удалены)
                cursor = await self._db.execute("""
                    SELECT COUNT(*) FROM comments 
                    WHERE status = 'sent' AND date(created_at) = ?
                """, (today,))
                stats['success'] = (await cursor.fetchone())[0]
                
                # Удалённые сегодня
                cursor = await self._db.execute("""
                    SELECT COUNT(*) FROM comments 
                    WHERE status = 'deleted' AND date(deleted_at) = ?
                """, (today,))
                stats['deleted'] = (await cursor.fetchone())[0]
                
                # Действия прогрева сегодня
                cursor = await self._db.execute("""
                    SELECT COUNT(*) FROM actions 
                    WHERE action_type = 'warmup' AND date(created_at) = ?
                """, (today,))
                stats['warmup_actions'] = (await cursor.fetchone())[0]
            except Exception:
                pass
            
            return stats
    
    async def get_hourly_stats(self) -> Dict[str, List[int]]:
        """Получить почасовую статистику за сегодня."""
        async with self._lock:
            comments = [0] * 24
            warmup = [0] * 24
            
            today = datetime.now().strftime('%Y-%m-%d')
            
            try:
                # Комментарии по часам
                cursor = await self._db.execute("""
                    SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
                    FROM comments 
                    WHERE date(created_at) = ?
                    GROUP BY hour
                """, (today,))
                
                for row in await cursor.fetchall():
                    hour = int(row[0])
                    comments[hour] = row[1]
                
                # Прогрев по часам
                cursor = await self._db.execute("""
                    SELECT strftime('%H', created_at) as hour, COUNT(*) as cnt
                    FROM actions 
                    WHERE action_type = 'warmup' AND date(created_at) = ?
                    GROUP BY hour
                """, (today,))
                
                for row in await cursor.fetchall():
                    hour = int(row[0])
                    warmup[hour] = row[1]
            except Exception:
                pass
            
            return {'comments': comments, 'warmup': warmup}
    
    async def get_stats_history(self, days: int = 7) -> List[Dict[str, Any]]:
        """Получить историю статистики за N дней."""
        async with self._lock:
            history = []
            
            try:
                cursor = await self._db.execute("""
                    SELECT date(created_at) as day, COUNT(*) as cnt
                    FROM comments 
                    WHERE date(created_at) >= date('now', ?)
                    GROUP BY day
                    ORDER BY day
                """, (f'-{days} days',))
                
                for row in await cursor.fetchall():
                    history.append({'date': row[0], 'comments': row[1]})
            except Exception:
                pass
            
            return history
    
    async def get_all_accounts(self) -> List[Dict[str, Any]]:
        """Получить все аккаунты."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT * FROM accounts ORDER BY id
            """)
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_all_channels(self) -> List[Dict[str, Any]]:
        """Получить все каналы."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT * FROM channels ORDER BY id
            """)
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def update_account_status(self, account_id: int, status: str) -> None:
        """Обновить статус аккаунта."""
        await self.update_account(account_id, {'status': status})
    
    async def update_channel_status(self, channel_id: int, status: str) -> None:
        """Обновить статус канала по ID записи."""
        async with self._lock:
            await self._db.execute("""
                UPDATE channels 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, channel_id))
            
            await self._db.commit()
    
    async def get_recent_comments(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Получить последние комментарии."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT c.*, ch.username as channel
                FROM comments c
                LEFT JOIN channels ch ON c.channel_id = ch.channel_id
                ORDER BY c.created_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_deleted_comments(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Получить удалённые комментарии."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT c.*, ch.username as channel
                FROM comments c
                LEFT JOIN channels ch ON c.channel_id = ch.channel_id
                WHERE c.status = 'deleted'
                ORDER BY c.deleted_at DESC
                LIMIT ?
            """, (limit,))
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def get_active_accounts(self) -> List[Dict[str, Any]]:
        """Получить все активные аккаунты."""
        async with self._lock:
            cursor = await self._db.execute("""
                SELECT * FROM accounts WHERE status = 'active'
            """)
            
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]
    
    async def close(self) -> None:
        """Закрыть соединение."""
        if self._db:
            await self._db.close()
            self._db = None


# Singleton
db = Database()
