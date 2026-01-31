# -*- coding: utf-8 -*-
"""
Конвертер tdata в Telethon session
Использует opentele для конвертации
"""

import os
from typing import Optional

from core.logger import logger


class TDataConverter:
    """Конвертер tdata → session."""
    
    def __init__(self):
        self._opentele_available = False
        
        try:
            from opentele.tl import TelegramClient as OpenTeleClient
            from opentele.api import API, UseCurrentSession
            self._opentele_available = True
        except ImportError:
            logger.warning(
                "opentele не установлен! Конвертация tdata невозможна.\n"
                "Установите: pip install opentele"
            )
    
    async def convert(self, tdata_path: str, session_path: str) -> bool:
        """
        Конвертировать tdata в session.
        
        Args:
            tdata_path: Путь к папке tdata (содержащей key_data)
            session_path: Путь для сохранения .session файла
        
        Returns:
            True если успешно
        """
        if not self._opentele_available:
            logger.error("opentele не установлен, конвертация невозможна")
            return False
        
        try:
            from opentele.tl import TelegramClient as OpenTeleClient
            from opentele.api import API, UseCurrentSession
            
            # Проверяем что tdata валидна
            key_data = os.path.join(tdata_path, 'key_data')
            if not os.path.exists(key_data):
                logger.error(f"Не найден key_data в {tdata_path}")
                return False
            
            logger.info(f"Конвертация tdata: {tdata_path}")
            
            # Создаём клиент из tdata
            client = OpenTeleClient.FromTDesktop(
                tdata_path,
                session=session_path.replace('.session', ''),
                api=API.TelegramDesktop
            )
            
            # Подключаемся для проверки
            await client.connect()
            
            if await client.is_user_authorized():
                me = await client.get_me()
                logger.info(f"Успешно: +{me.phone} ({me.first_name})")
                await client.disconnect()
                return True
            else:
                logger.warning(f"Сессия не авторизована: {tdata_path}")
                await client.disconnect()
                return False
                
        except Exception as e:
            logger.error(f"Ошибка конвертации tdata: {e}", exc_info=True)
            return False
    
    def is_available(self) -> bool:
        """Проверка доступности конвертера."""
        return self._opentele_available
