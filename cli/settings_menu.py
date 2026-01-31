"""
Меню настроек с премиум оформлением
"""

import os
import platform
import asyncio
from typing import Any

from core.logger import logger
from core.state import state


class Colors:
    """ANSI цвета"""
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


class SettingsMenu:
    """Меню настроек"""
    
    WIDTH = 70
    
    def __init__(self):
        self._running = False
    
    @staticmethod
    def strip_ansi(text: str) -> str:
        """Убирает ANSI-коды"""
        import re
        return re.compile(r'\x1b\[[0-9;]*m').sub('', text)
    
    @staticmethod
    def visual_len(text: str) -> int:
        """Визуальная длина без ANSI"""
        return len(SettingsMenu.strip_ansi(text))
    
    @staticmethod
    def pad(text: str, width: int, align: str = 'left') -> str:
        """Выравнивание с учётом ANSI"""
        visual = SettingsMenu.visual_len(text)
        padding = width - visual
        if padding <= 0:
            return text
        if align == 'right':
            return ' ' * padding + text
        elif align == 'center':
            left = padding // 2
            return ' ' * left + text + ' ' * (padding - left)
        return text + ' ' * padding
    
    def box_line(self, text: str) -> str:
        """Строка в рамке"""
        C = Colors
        padded = self.pad(text, self.WIDTH)
        return f"{C.CYAN}║{C.RESET}{padded}{C.CYAN}║{C.RESET}"
    
    def box_line_lr(self, left: str, right: str) -> str:
        """Строка с текстом слева и справа"""
        C = Colors
        left_len = self.visual_len(left)
        right_len = self.visual_len(right)
        spaces = self.WIDTH - left_len - right_len
        if spaces < 1:
            spaces = 1
        content = left + ' ' * spaces + right
        return f"{C.CYAN}║{C.RESET}{content}{C.CYAN}║{C.RESET}"
    
    def _clear_screen(self) -> None:
        """Очистка экрана"""
        if platform.system() == 'Windows':
            os.system('cls')
        else:
            os.system('clear')
    
    def _print_menu(self) -> None:
        """Вывод меню настроек"""
        C = Colors
        W = self.WIDTH
        
        # Получаем текущие значения
        mode = state.get_mode()
        mode_color = C.GREEN if mode == "SAFE" else C.YELLOW
        
        delays = state.config.get('delays', {})
        min_delay = delays.get('min', 30)
        max_delay = delays.get('max', 90)
        read_min = delays.get('read_min', 5)
        read_max = delays.get('read_max', 15)
        type_min = delays.get('type_min', 2)
        type_max = delays.get('type_max', 8)
        
        limits = state.config.get('limits', {})
        hour_limit = limits.get('per_hour', 10)
        day_limit = limits.get('per_day', 100)
        
        gpt = state.config.get('gpt', {})
        gpt_model = gpt.get('model', 'gpt-4o-mini')
        gpt_temp = gpt.get('temperature', 0.9)
        
        prob = state.config.get('commenting', {}).get('comment_probability_percent', 100)
        
        monitor = state.config.get('monitor', {})
        check_interval = monitor.get('delete_check_interval_sec', 60)
        
        proxy_cfg = state.config.get('proxy', {})
        proxy_enabled = proxy_cfg.get('enabled', False)
        
        sanctions = state.config.get('sanctions', {})
        sleep_after = sanctions.get('sleep_after_deletions', 1)
        disable_after = sanctions.get('disable_after_deletions', 3)
        
        print()
        print(f"    {C.CYAN}╔{'═' * W}╗{C.RESET}")
        title = self.pad("⚙️  НАСТРОЙКИ", W, 'center')
        print(f"    {C.CYAN}║{C.RESET}{C.BOLD}{C.WHITE}{title}{C.RESET}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╠{'═' * W}╣{C.RESET}")
        
        # === РЕЖИМ ===
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ РЕЖИМ РАБОТЫ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        
        item = f"    {C.YELLOW}[1]{C.RESET} 🛡️  Режим безопасности"
        value = f"{mode_color}{mode}{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        # === ТАЙМИНГИ ===
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ ТАЙМИНГИ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        
        item = f"    {C.YELLOW}[2]{C.RESET} ⏱️  Задержки между действиями"
        value = f"{C.MAGENTA}{min_delay}-{max_delay} сек{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        item = f"    {C.YELLOW}[3]{C.RESET} 📖 Время чтения поста"
        value = f"{C.MAGENTA}{read_min}-{read_max} сек{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        item = f"    {C.YELLOW}[4]{C.RESET} ⌨️  Время набора текста"
        value = f"{C.MAGENTA}{type_min}-{type_max} сек{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        # === ЛИМИТЫ ===
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ ЛИМИТЫ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        
        item = f"    {C.YELLOW}[5]{C.RESET} 📊 Лимиты комментариев"
        value = f"{C.MAGENTA}{hour_limit}/час, {day_limit}/день{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        item = f"    {C.YELLOW}[6]{C.RESET} 🎲 Вероятность комментария"
        value = f"{C.MAGENTA}{prob}%{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        # === GPT ===
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ GPT ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        
        item = f"    {C.YELLOW}[7]{C.RESET} 🤖 Модель GPT"
        value = f"{C.MAGENTA}{gpt_model}{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        item = f"    {C.YELLOW}[8]{C.RESET} 🌡️  Temperature"
        value = f"{C.MAGENTA}{gpt_temp}{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        item = f"    {C.YELLOW}[9]{C.RESET} ✏️  Редактировать промпт"
        print(f"    " + self.box_line(item))
        
        # === МОНИТОРИНГ ===
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ МОНИТОРИНГ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        
        item = f"   {C.YELLOW}[10]{C.RESET} 👁️  Интервал проверки удалений"
        value = f"{C.MAGENTA}{check_interval} сек{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        item = f"   {C.YELLOW}[11]{C.RESET} ⚠️  Санкции (sleep/disable)"
        value = f"{C.MAGENTA}{sleep_after}/{disable_after} удалений{C.RESET}  "
        print(f"    " + self.box_line_lr(item, value))
        
        # === ПРОКСИ ===
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ ПРОКСИ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        
        proxy_status = f"{C.GREEN}✅ Вкл{C.RESET}" if proxy_enabled else f"{C.RED}❌ Выкл{C.RESET}"
        item = f"   {C.YELLOW}[12]{C.RESET} 🌐 Использовать прокси"
        print(f"    " + self.box_line_lr(item, proxy_status + "  "))
        
        # === УПРАВЛЕНИЕ ===
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╠{'═' * W}╣{C.RESET}")
        
        footer = f"    {C.GREEN}[S]{C.RESET} 💾 Сохранить      {C.YELLOW}[0]{C.RESET} 🔙 Назад"
        print(f"    " + self.box_line(self.pad(footer, W, 'center')))
        
        print(f"    {C.CYAN}║{C.RESET}{self.pad('', W)}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╚{'═' * W}╝{C.RESET}")
        print()
    
    async def _edit_mode(self) -> None:
        """Переключение режима SAFE/NORMAL"""
        C = Colors
        current = state.get_mode()
        new_mode = "NORMAL" if current == "SAFE" else "SAFE"
        state.set_mode(new_mode)
        
        if new_mode == "SAFE":
            print(f"\n    {C.GREEN}🛡️  Режим изменён на SAFE (безопасный){C.RESET}")
            print(f"    {C.DIM}   Задержки удвоены, лимиты уменьшены вдвое{C.RESET}")
        else:
            print(f"\n    {C.YELLOW}⚡ Режим изменён на NORMAL (обычный){C.RESET}")
        
        await asyncio.sleep(1.5)
    
    async def _edit_delays(self) -> None:
        """Редактирование задержек"""
        C = Colors
        print(f"\n    {C.CYAN}⏱️  Задержки между действиями{C.RESET}")
        print(f"    {C.DIM}Текущие: {state.config['delays']['min']}-{state.config['delays']['max']} сек{C.RESET}")
        
        try:
            min_val = input(f"    Минимум (сек): ").strip()
            max_val = input(f"    Максимум (сек): ").strip()
            
            if min_val and max_val:
                state.config['delays']['min'] = int(min_val)
                state.config['delays']['max'] = int(max_val)
                print(f"\n    {C.GREEN}✅ Задержки обновлены{C.RESET}")
            else:
                print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        except ValueError:
            print(f"\n    {C.RED}❌ Неверный формат числа{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_read_time(self) -> None:
        """Редактирование времени чтения"""
        C = Colors
        print(f"\n    {C.CYAN}📖 Время чтения поста{C.RESET}")
        
        try:
            min_val = input(f"    Минимум (сек): ").strip()
            max_val = input(f"    Максимум (сек): ").strip()
            
            if min_val and max_val:
                state.config['delays']['read_min'] = int(min_val)
                state.config['delays']['read_max'] = int(max_val)
                print(f"\n    {C.GREEN}✅ Время чтения обновлено{C.RESET}")
            else:
                print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        except ValueError:
            print(f"\n    {C.RED}❌ Неверный формат числа{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_type_time(self) -> None:
        """Редактирование времени набора"""
        C = Colors
        print(f"\n    {C.CYAN}⌨️  Время набора текста{C.RESET}")
        
        try:
            min_val = input(f"    Минимум (сек): ").strip()
            max_val = input(f"    Максимум (сек): ").strip()
            
            if min_val and max_val:
                state.config['delays']['type_min'] = int(min_val)
                state.config['delays']['type_max'] = int(max_val)
                print(f"\n    {C.GREEN}✅ Время набора обновлено{C.RESET}")
            else:
                print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        except ValueError:
            print(f"\n    {C.RED}❌ Неверный формат числа{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_limits(self) -> None:
        """Редактирование лимитов"""
        C = Colors
        print(f"\n    {C.CYAN}📊 Лимиты комментариев{C.RESET}")
        
        try:
            hour = input(f"    Лимит в час: ").strip()
            day = input(f"    Лимит в день: ").strip()
            
            if hour and day:
                state.config['limits']['per_hour'] = int(hour)
                state.config['limits']['per_day'] = int(day)
                print(f"\n    {C.GREEN}✅ Лимиты обновлены{C.RESET}")
            else:
                print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        except ValueError:
            print(f"\n    {C.RED}❌ Неверный формат числа{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_probability(self) -> None:
        """Редактирование вероятности комментирования"""
        C = Colors
        current = state.config.get('commenting', {}).get('comment_probability_percent', 100)
        print(f"\n    {C.CYAN}🎲 Вероятность комментирования{C.RESET}")
        print(f"    {C.DIM}Текущая: {current}%{C.RESET}")
        
        try:
            value = input(f"    Новое значение (0-100): ").strip()
            
            if value:
                prob = int(value)
                if 0 <= prob <= 100:
                    if 'commenting' not in state.config:
                        state.config['commenting'] = {}
                    state.config['commenting']['comment_probability_percent'] = prob
                    print(f"\n    {C.GREEN}✅ Вероятность: {prob}%{C.RESET}")
                else:
                    print(f"\n    {C.RED}❌ Значение должно быть от 0 до 100{C.RESET}")
            else:
                print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        except ValueError:
            print(f"\n    {C.RED}❌ Неверный формат числа{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_gpt_model(self) -> None:
        """Редактирование модели GPT"""
        C = Colors
        current = state.config.get('gpt', {}).get('model', 'gpt-4o-mini')
        print(f"\n    {C.CYAN}🤖 Модель GPT{C.RESET}")
        print(f"    {C.DIM}Текущая: {current}{C.RESET}")
        print(f"    {C.DIM}Доступные: gpt-4o-mini, gpt-4o, gpt-4-turbo, gpt-3.5-turbo{C.RESET}")
        
        value = input(f"    Модель: ").strip()
        
        if value:
            state.config['gpt']['model'] = value
            print(f"\n    {C.GREEN}✅ Модель: {value}{C.RESET}")
        else:
            print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_gpt_temp(self) -> None:
        """Редактирование temperature GPT"""
        C = Colors
        current = state.config.get('gpt', {}).get('temperature', 0.9)
        print(f"\n    {C.CYAN}🌡️  Temperature GPT{C.RESET}")
        print(f"    {C.DIM}Текущая: {current} (0.0-2.0, рекомендуется 0.7-1.0){C.RESET}")
        
        try:
            value = input(f"    Значение: ").strip()
            
            if value:
                temp = float(value)
                if 0.0 <= temp <= 2.0:
                    state.config['gpt']['temperature'] = temp
                    print(f"\n    {C.GREEN}✅ Temperature: {temp}{C.RESET}")
                else:
                    print(f"\n    {C.RED}❌ Значение должно быть от 0.0 до 2.0{C.RESET}")
            else:
                print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        except ValueError:
            print(f"\n    {C.RED}❌ Неверный формат числа{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_prompt(self) -> None:
        """Редактирование промпта"""
        C = Colors
        current = state.config.get('gpt', {}).get('prompt', '')
        
        print(f"\n    {C.CYAN}✏️  Системный промпт GPT{C.RESET}")
        print(f"    {C.DIM}Текущий промпт (первые 200 символов):{C.RESET}")
        print(f"    {C.DIM}{current[:200]}...{C.RESET}")
        print()
        print(f"    {C.YELLOW}Введите новый промпт (или Enter для отмены):{C.RESET}")
        
        value = input(f"    ").strip()
        
        if value:
            state.config['gpt']['prompt'] = value
            print(f"\n    {C.GREEN}✅ Промпт обновлён{C.RESET}")
        else:
            print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_check_interval(self) -> None:
        """Редактирование интервала проверки удалений"""
        C = Colors
        current = state.config.get('monitor', {}).get('delete_check_interval_sec', 60)
        print(f"\n    {C.CYAN}👁️  Интервал проверки удалений{C.RESET}")
        print(f"    {C.DIM}Текущий: {current} сек{C.RESET}")
        
        try:
            value = input(f"    Интервал (сек): ").strip()
            
            if value:
                interval = int(value)
                if interval >= 10:
                    if 'monitor' not in state.config:
                        state.config['monitor'] = {}
                    state.config['monitor']['delete_check_interval_sec'] = interval
                    print(f"\n    {C.GREEN}✅ Интервал: {interval} сек{C.RESET}")
                else:
                    print(f"\n    {C.RED}❌ Минимум 10 секунд{C.RESET}")
            else:
                print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        except ValueError:
            print(f"\n    {C.RED}❌ Неверный формат числа{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _edit_sanctions(self) -> None:
        """Редактирование санкций"""
        C = Colors
        sanctions = state.config.get('sanctions', {})
        sleep_after = sanctions.get('sleep_after_deletions', 1)
        disable_after = sanctions.get('disable_after_deletions', 3)
        
        print(f"\n    {C.CYAN}⚠️  Санкции для каналов{C.RESET}")
        print(f"    {C.DIM}Текущие: sleep после {sleep_after}, disable после {disable_after} удалений{C.RESET}")
        
        try:
            sleep_val = input(f"    Sleep после (удалений): ").strip()
            disable_val = input(f"    Disable после (удалений): ").strip()
            
            if sleep_val and disable_val:
                state.config['sanctions']['sleep_after_deletions'] = int(sleep_val)
                state.config['sanctions']['disable_after_deletions'] = int(disable_val)
                print(f"\n    {C.GREEN}✅ Санкции обновлены{C.RESET}")
            else:
                print(f"\n    {C.YELLOW}⚠️  Отменено{C.RESET}")
        except ValueError:
            print(f"\n    {C.RED}❌ Неверный формат числа{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _toggle_proxy(self) -> None:
        """Переключение прокси"""
        C = Colors
        current = state.config.get('proxy', {}).get('enabled', False)
        new_value = not current
        
        state.config['proxy']['enabled'] = new_value
        
        if new_value:
            print(f"\n    {C.GREEN}✅ Прокси включены{C.RESET}")
        else:
            print(f"\n    {C.YELLOW}⚠️  Прокси выключены{C.RESET}")
        
        await asyncio.sleep(1)
    
    async def _save_config(self) -> None:
        """Сохранение конфигурации"""
        C = Colors
        
        try:
            state.save_config()
            print(f"\n    {C.GREEN}💾 Конфигурация сохранена в config.yaml{C.RESET}")
            logger.info("Конфигурация сохранена")
        except Exception as e:
            logger.error(f"Ошибка сохранения конфигурации: {e}", exc_info=True)
            print(f"\n    {C.RED}❌ Ошибка сохранения: {e}{C.RESET}")
        
        await asyncio.sleep(1.5)
    
    async def run(self) -> None:
        """Главный цикл меню настроек"""
        self._running = True
        
        while self._running:
            self._clear_screen()
            self._print_menu()
            
            try:
                choice = input(f"    {Colors.CYAN}👉 Выберите пункт:{Colors.RESET} ").strip().lower()
                
                if choice == '1':
                    await self._edit_mode()
                elif choice == '2':
                    await self._edit_delays()
                elif choice == '3':
                    await self._edit_read_time()
                elif choice == '4':
                    await self._edit_type_time()
                elif choice == '5':
                    await self._edit_limits()
                elif choice == '6':
                    await self._edit_probability()
                elif choice == '7':
                    await self._edit_gpt_model()
                elif choice == '8':
                    await self._edit_gpt_temp()
                elif choice == '9':
                    await self._edit_prompt()
                elif choice == '10':
                    await self._edit_check_interval()
                elif choice == '11':
                    await self._edit_sanctions()
                elif choice == '12':
                    await self._toggle_proxy()
                elif choice == 's':
                    await self._save_config()
                elif choice == '0' or choice == 'q':
                    self._running = False
                else:
                    print(f"\n    {Colors.YELLOW}⚠️  Неверный выбор{Colors.RESET}")
                    await asyncio.sleep(0.5)
                    
            except KeyboardInterrupt:
                self._running = False
            except Exception as e:
                logger.error(f"Ошибка в настройках: {e}", exc_info=True)
                print(f"\n    {Colors.RED}❌ Ошибка: {e}{Colors.RESET}")
                await asyncio.sleep(2)
