# -*- coding: utf-8 -*-
"""
GPT сервис для генерации комментариев
Персонаж: девушка-анимешница-музыкантша
"""

import asyncio
import random
from typing import Optional

import openai

from core.logger import comments_logger as logger
from core.state import app_state


# ПРОМПТ ПЕРСОНАЖА
SYSTEM_PROMPT = """Ты — девушка 20 лет. Анимешница, любишь музыку и играешь на укулеле. 
Ты милая, добрая, немного наивная, но искренняя.

ПРАВИЛА ОТВЕТОВ:
1. Пиши ОЧЕНЬ коротко: обычно 2-5 слов, максимум 10 слов
2. Можешь делать небольшие грамматические ошибки (как живой человек)
3. Используй молодёжный сленг: "ваау", "ооо", "кайф", "вайб", "топчик", "огонь"
4. Иногда добавляй эмодзи (но не много): 😊 ✨ 💕 🎵 🌸
5. Будь естественной, как будто пишешь другу

СТРОГО ЗАПРЕЩЕНО:
- Любые упоминания войны, политики, геополитики
- Стороны конфликтов, военные действия
- Смерть, раненые, трагедии
- Любые политические деятели и события

ЕСЛИ ПОСТ О ВОЙНЕ/ПОЛИТИКЕ/СМЕРТИ:
Ответь ТОЛЬКО одним грустным эмодзи: 😢 или 🖤 или 💔
Никакого текста!

ЕСЛИ ПОСТ НЕИНТЕРЕСНЫЙ ИЛИ НЕПОНЯТНЫЙ:
Ответь: SKIP

ПРИМЕРЫ ХОРОШИХ ОТВЕТОВ:
- "ваау красиво 🌸"
- "оо круто"  
- "какой милый"
- "топчик ✨"
- "эт огонь"
- "вайб 🎵"
- "ааа обожаю"
- "хочу такое"
- "кайфф"

Отвечай на пост ниже. Помни — ты живой человек, не бот!"""


class GPTService:
    """Сервис генерации комментариев через GPT."""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._client: Optional[openai.AsyncOpenAI] = None
        self._initialized = True
    
    def _ensure_client(self) -> bool:
        """Проверить/создать клиент OpenAI."""
        if self._client:
            return True
        
        api_key = app_state.config.get('gpt', {}).get('api_key', '')
        
        if not api_key:
            logger.error("GPT API ключ не задан в config.yaml")
            return False
        
        self._client = openai.AsyncOpenAI(api_key=api_key)
        return True
    
    async def generate_comment(self, post_text: str) -> Optional[str]:
        """
        Сгенерировать комментарий к посту.
        
        Args:
            post_text: Текст поста
        
        Returns:
            Текст комментария или None
            "SKIP" если пост нужно пропустить
        """
        if not self._ensure_client():
            return None
        
        if not post_text or len(post_text.strip()) < 3:
            logger.debug("Пост пустой или слишком короткий")
            return "SKIP"
        
        # Ограничиваем длину поста
        post_text = post_text[:1000]
        
        try:
            gpt_config = app_state.config.get('gpt', {})
            
            model = gpt_config.get('model', 'gpt-3.5-turbo')
            temperature = gpt_config.get('temperature', 0.9)
            max_tokens = gpt_config.get('max_tokens', 60)
            
            response = await self._client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"Пост:\n{post_text}"}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                presence_penalty=0.6,
                frequency_penalty=0.3
            )
            
            comment = response.choices[0].message.content.strip()
            
            # Проверяем на SKIP
            if comment.upper() == 'SKIP':
                logger.info("GPT решил пропустить пост")
                return "SKIP"
            
            # Убираем кавычки если есть
            comment = comment.strip('"\'')
            
            # Проверяем на политику (дополнительный фильтр)
            if self._is_political(comment):
                logger.warning("GPT сгенерировал политический контент, заменяем на эмодзи")
                return random.choice(['😢', '🖤', '💔'])
            
            # Добавляем вариативность
            comment = self._add_variation(comment)
            
            logger.info(f"GPT сгенерировал: {comment}")
            return comment
            
        except openai.RateLimitError:
            logger.warning("GPT rate limit, ждём...")
            await asyncio.sleep(30)
            return None
        
        except openai.APIError as e:
            logger.error(f"GPT API ошибка: {e}")
            return None
        
        except Exception as e:
            logger.error(f"Ошибка генерации GPT: {e}", exc_info=True)
            return None
    
    def _is_political(self, text: str) -> bool:
        """Проверка на политический контент."""
        text_lower = text.lower()
        
        political_words = [
            'война', 'войн', 'военн', 'солдат', 'армия', 'армии',
            'политик', 'политика', 'президент', 'путин', 'зеленск',
            'украин', 'росси', 'нато', 'байден', 'трамп',
            'бомб', 'ракет', 'атак', 'обстрел', 'погиб', 'убит',
            'конфликт', 'фронт', 'окоп', 'мобилизац', 'всу', 'сво',
            'донбас', 'крым', 'херсон', 'харьков', 'киев', 'москв'
        ]
        
        for word in political_words:
            if word in text_lower:
                return True
        
        return False
    
    def _add_variation(self, text: str) -> str:
        """Добавить вариативность в текст."""
        # Случайно меняем регистр первой буквы
        if random.random() < 0.3 and len(text) > 0:
            text = text[0].lower() + text[1:]
        
        # Случайно добавляем опечатку (удвоение буквы)
        if random.random() < 0.1 and len(text) > 3:
            pos = random.randint(1, len(text) - 2)
            if text[pos].isalpha():
                text = text[:pos] + text[pos] + text[pos:]
        
        # Случайно убираем точку в конце
        if text.endswith('.') and random.random() < 0.5:
            text = text[:-1]
        
        return text
    
    async def is_available(self) -> bool:
        """Проверить доступность GPT."""
        return self._ensure_client()


# Singleton
gpt_service = GPTService()
