"""
Главное меню с премиум оформлением
"""

import os
import sys
import asyncio
import subprocess
import platform
from datetime import datetime
from typing import Optional, Tuple

from core.logger import logger
from core.state import state
from core.database import db
from core.scheduler import scheduler


class Colors:
    """ANSI цвета для консоли"""
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
    
    # Фоновые цвета
    BG_RED = '\033[41m'
    BG_GREEN = '\033[42m'
    BG_YELLOW = '\033[43m'
    BG_BLUE = '\033[44m'


class MenuUI:
    """Премиум интерфейс меню"""
    
    # Константы ширины
    WIDTH = 70  # Внутренняя ширина (между рамками)
    FULL_WIDTH = 72  # Полная ширина с рамками
    
    def __init__(self):
        self._running = False
        self._log_windows = {
            'comments': None,
            'warmup': None
        }
    
    @staticmethod
    def strip_ansi(text: str) -> str:
        """Убирает ANSI-коды из текста для подсчёта реальной длины"""
        import re
        ansi_pattern = re.compile(r'\x1b\[[0-9;]*m')
        return ansi_pattern.sub('', text)
    
    @staticmethod
    def visual_len(text: str) -> int:
        """Возвращает визуальную длину текста (без ANSI-кодов)"""
        return len(MenuUI.strip_ansi(text))
    
    @staticmethod
    def pad(text: str, width: int, align: str = 'left', fill: str = ' ') -> str:
        """
        Выравнивает текст с учётом ANSI-кодов
        align: 'left', 'right', 'center'
        """
        visual = MenuUI.visual_len(text)
        padding = width - visual
        if padding <= 0:
            return text
        
        if align == 'right':
            return fill * padding + text
        elif align == 'center':
            left_pad = padding // 2
            right_pad = padding - left_pad
            return fill * left_pad + text + fill * right_pad
        else:  # left
            return text + fill * padding
    
    @staticmethod
    def box_line(text: str, width: int = None) -> str:
        """Создаёт строку в рамке с выравниванием"""
        if width is None:
            width = MenuUI.WIDTH
        C = Colors
        padded = MenuUI.pad(text, width)
        return f"{C.CYAN}║{C.RESET}{padded}{C.CYAN}║{C.RESET}"
    
    @staticmethod
    def box_line_lr(left: str, right: str, width: int = None) -> str:
        """Строка с текстом слева и справа"""
        if width is None:
            width = MenuUI.WIDTH
        C = Colors
        left_len = MenuUI.visual_len(left)
        right_len = MenuUI.visual_len(right)
        spaces = width - left_len - right_len
        if spaces < 1:
            spaces = 1
        content = left + ' ' * spaces + right
        return f"{C.CYAN}║{C.RESET}{content}{C.CYAN}║{C.RESET}"
    
    def _clear_screen(self) -> None:
        """Очистка экрана кроссплатформенно"""
        if platform.system() == 'Windows':
            os.system('cls')
        else:
            os.system('clear')
    
    def _open_log_window(self, log_type: str) -> None:
        """Открывает отдельное окно для логов"""
        if platform.system() != 'Windows':
            logger.debug(f"Окна логов поддерживаются только на Windows")
            return
        
        if self._log_windows.get(log_type):
            # Окно уже открыто
            return
        
        try:
            if log_type == 'comments':
                log_file = 'logs/comments.log'
                title = 'NEURO-COMMENT :: Logs Commenting'
            else:
                log_file = 'logs/warmup.log'
                title = 'NEURO-COMMENT :: Logs Warmup'
            
            # Создаём файл если не существует
            os.makedirs('logs', exist_ok=True)
            if not os.path.exists(log_file):
                open(log_file, 'w', encoding='utf-8').close()
            
            # Открываем PowerShell с tail
            cmd = f'powershell -Command "chcp 65001 > $null; $Host.UI.RawUI.WindowTitle = \'{title}\'; Get-Content -Path \'{log_file}\' -Wait -Tail 50"'
            
            process = subprocess.Popen(
                f'start cmd /c "{cmd}"',
                shell=True,
                creationflags=subprocess.CREATE_NEW_CONSOLE if platform.system() == 'Windows' else 0
            )
            
            self._log_windows[log_type] = process
            logger.info(f"Открыто окно логов: {log_type}")
            
        except Exception as e:
            logger.warning(f"Не удалось открыть окно логов {log_type}: {e}")
    
    def _print_header(self) -> None:
        """Выводит красивый заголовок"""
        C = Colors
        W = self.WIDTH
        
        print()
        print(f"    {C.CYAN}╔{'═' * W}╗{C.RESET}")
        print(f"    {C.CYAN}║{C.RESET}{C.BOLD}{C.WHITE}{MenuUI.pad('', W)}{C.RESET}{C.CYAN}║{C.RESET}")
        
        # ASCII-арт NEURO (центрируем)
        logo_lines = [
            "███╗   ██╗███████╗██╗   ██╗██████╗  ██████╗ ",
            "████╗  ██║██╔════╝██║   ██║██╔══██╗██╔═══██╗",
            "██╔██╗ ██║█████╗  ██║   ██║██████╔╝██║   ██║",
            "██║╚██╗██║██╔══╝  ██║   ██║██╔══██╗██║   ██║",
            "██║ ╚████║███████╗╚██████╔╝██║  ██║╚██████╔╝",
            "╚═╝  ╚═══╝╚══════╝ ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ "
        ]
        
        for line in logo_lines:
            centered = MenuUI.pad(line, W, 'center')
            print(f"    {C.CYAN}║{C.RESET}{C.WHITE}{centered}{C.RESET}{C.CYAN}║{C.RESET}")
        
        # COMMENT
        comment_lines = [
            " ██████╗ ██████╗ ███╗   ███╗███╗   ███╗███████╗███╗   ██╗████████╗",
            "██╔════╝██╔═══██╗████╗ ████║████╗ ████║██╔════╝████╗  ██║╚══██╔══╝",
            "██║     ██║   ██║██╔████╔██║██╔████╔██║█████╗  ██╔██╗ ██║   ██║   ",
            "██║     ██║   ██║██║╚██╔╝██║██║╚██╔╝██║██╔══╝  ██║╚██╗██║   ██║   ",
            "╚██████╗╚██████╔╝██║ ╚═╝ ██║██║ ╚═╝ ██║███████╗██║ ╚████║   ██║   ",
            " ╚═════╝ ╚═════╝ ╚═╝     ╚═╝╚═╝     ╚═╝╚══════╝╚═╝  ╚═══╝   ╚═╝   "
        ]
        
        for line in comment_lines:
            centered = MenuUI.pad(line, W, 'center')
            print(f"    {C.CYAN}║{C.RESET}{C.CYAN}{centered}{C.RESET}{C.CYAN}║{C.RESET}")
        
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        subtitle = "🤖 Telegram Neuro Commenting Bot v2.0"
        centered_sub = MenuUI.pad(subtitle, W, 'center')
        print(f"    {C.CYAN}║{C.RESET}{C.DIM}{centered_sub}{C.RESET}{C.CYAN}║{C.RESET}")
        
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╚{'═' * W}╝{C.RESET}")
        print()
    
    def _print_menu(self) -> None:
        """Выводит главное меню"""
        C = Colors
        W = self.WIDTH
        
        # Статусы сервисов
        commenting_on = scheduler.is_running('commenting')
        warmup_on = scheduler.is_running('warmup')
        
        # Текущий режим
        mode = state.get_mode()
        mode_icon = "🛡️" if mode == "SAFE" else "⚡"
        mode_color = C.GREEN if mode == "SAFE" else C.YELLOW
        
        # Время
        time_str = datetime.now().strftime("%H:%M:%S")
        
        # === ЗАГОЛОВОК ===
        print(f"    {C.CYAN}╔{'═' * W}╗{C.RESET}")
        
        title = f"{mode_icon} NEURO COMMENT BOT"
        right_info = f"Режим: {mode} │ {time_str}"
        print(f"    " + self.box_line_lr(f"  {C.BOLD}{C.WHITE}{title}{C.RESET}", f"{mode_color}{right_info}{C.RESET}  "))
        
        print(f"    {C.CYAN}╠{'═' * W}╣{C.RESET}")
        
        # === КОММЕНТИРОВАНИЕ ===
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        section_title = f"  {C.BOLD}{C.WHITE}─── КОММЕНТИРОВАНИЕ ───{C.RESET}"
        print(f"    " + self.box_line(section_title))
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        # Пункт 1
        status1 = f"{C.GREEN}● РАБОТАЕТ{C.RESET}" if commenting_on else f"{C.DIM}○ Выключено{C.RESET}"
        item1 = f"    {C.YELLOW}[1]{C.RESET} 🚀 Запустить комментирование"
        print(f"    " + self.box_line_lr(item1, status1 + "  "))
        
        # Пункт 2
        item2 = f"    {C.YELLOW}[2]{C.RESET} ⏹️  Остановить комментирование"
        print(f"    " + self.box_line(item2))
        
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        # === ПРОГРЕВ ===
        section_title2 = f"  {C.BOLD}{C.WHITE}─── ПРОГРЕВ ───{C.RESET}"
        print(f"    " + self.box_line(section_title2))
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        # Пункт 3
        status3 = f"{C.GREEN}● РАБОТАЕТ{C.RESET}" if warmup_on else f"{C.DIM}○ Выключено{C.RESET}"
        item3 = f"    {C.YELLOW}[3]{C.RESET} 🔥 Запустить прогрев"
        print(f"    " + self.box_line_lr(item3, status3 + "  "))
        
        # Пункт 4
        item4 = f"    {C.YELLOW}[4]{C.RESET} ⏹️  Остановить прогрев"
        print(f"    " + self.box_line(item4))
        
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        # === УПРАВЛЕНИЕ ===
        section_title3 = f"  {C.BOLD}{C.WHITE}─── УПРАВЛЕНИЕ ───{C.RESET}"
        print(f"    " + self.box_line(section_title3))
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        items = [
            f"    {C.YELLOW}[5]{C.RESET} 📊 Статус системы",
            f"    {C.YELLOW}[6]{C.RESET} ⚙️  Настройки",
            f"    {C.YELLOW}[7]{C.RESET} 🔍 Проверить прокси",
            f"    {C.YELLOW}[8]{C.RESET} 📁 Информация о данных",
            f"    {C.YELLOW}[9]{C.RESET} 🚪 Выход",
        ]
        
        for item in items:
            print(f"    " + self.box_line(item))
        
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╚{'═' * W}╝{C.RESET}")
        print()
    
    async def _show_status(self) -> None:
        """Показывает подробный статус системы"""
        C = Colors
        W = self.WIDTH
        
        self._clear_screen()
        
        print()
        print(f"    {C.CYAN}╔{'═' * W}╗{C.RESET}")
        title = MenuUI.pad("📊 СТАТУС СИСТЕМЫ", W, 'center')
        print(f"    {C.CYAN}║{C.RESET}{C.BOLD}{C.WHITE}{title}{C.RESET}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╠{'═' * W}╣{C.RESET}")
        
        # === СЕРВИСЫ ===
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ СЕРВИСЫ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        services = [
            ("💬 Комментирование", scheduler.is_running('commenting')),
            ("🔥 Прогрев", scheduler.is_running('warmup')),
            ("👁️  Мониторинг", scheduler.is_running('monitor')),
        ]
        
        for name, is_on in services:
            if is_on:
                status = f"{C.GREEN}[  ● РАБОТАЕТ  ]{C.RESET}"
            else:
                status = f"{C.DIM}[  ○ Выключено ]{C.RESET}"
            line = f"    {name}"
            print(f"    " + self.box_line_lr(line, status + "  "))
        
        # === АККАУНТЫ ===
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ АККАУНТЫ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        # Подсчёт файлов
        sessions_c = len([f for f in os.listdir('sessions_комменты') if f.endswith('.session')]) if os.path.exists('sessions_комменты') else 0
        tdata_c = len([d for d in os.listdir('tdata_комменты') if os.path.isdir(os.path.join('tdata_комменты', d))]) if os.path.exists('tdata_комменты') else 0
        sessions_w = len([f for f in os.listdir('sessions_прогрев') if f.endswith('.session')]) if os.path.exists('sessions_прогрев') else 0
        tdata_w = len([d for d in os.listdir('tdata_прогрев') if os.path.isdir(os.path.join('tdata_прогрев', d))]) if os.path.exists('tdata_прогрев') else 0
        
        line1 = f"    📱 Комменты:  {C.GREEN}{sessions_c}{C.RESET} sessions, {C.YELLOW}{tdata_c}{C.RESET} tdata"
        line2 = f"    🔥 Прогрев:   {C.GREEN}{sessions_w}{C.RESET} sessions, {C.YELLOW}{tdata_w}{C.RESET} tdata"
        print(f"    " + self.box_line(line1))
        print(f"    " + self.box_line(line2))
        
        # === КАНАЛЫ ===
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ КАНАЛЫ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        # Подсчёт каналов
        channels_c = 0
        if os.path.exists('каналы'):
            for f in os.listdir('каналы'):
                if f.endswith('.txt'):
                    try:
                        with open(os.path.join('каналы', f), 'r', encoding='utf-8') as file:
                            channels_c += len([l for l in file if l.strip() and not l.startswith('#')])
                    except Exception:
                        pass
        
        channels_w = 0
        if os.path.exists('каналы_прогрев'):
            for f in os.listdir('каналы_прогрев'):
                if f.endswith('.txt'):
                    try:
                        with open(os.path.join('каналы_прогрев', f), 'r', encoding='utf-8') as file:
                            channels_w += len([l for l in file if l.strip() and not l.startswith('#')])
                    except Exception:
                        pass
        
        chats_w = 0
        if os.path.exists('чаты_прогрев'):
            for f in os.listdir('чаты_прогрев'):
                if f.endswith('.txt'):
                    try:
                        with open(os.path.join('чаты_прогрев', f), 'r', encoding='utf-8') as file:
                            chats_w += len([l for l in file if l.strip() and not l.startswith('#')])
                    except Exception:
                        pass
        
        line1 = f"    📢 Комменты:  {C.GREEN}{channels_c}{C.RESET} каналов"
        line2 = f"    🔥 Прогрев:   {C.GREEN}{channels_w}{C.RESET} каналов, {C.GREEN}{chats_w}{C.RESET} чатов"
        print(f"    " + self.box_line(line1))
        print(f"    " + self.box_line(line2))
        
        # === СТАТИСТИКА ===
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ НАСТРОЙКИ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        mode = state.get_mode()
        mode_icon = "🛡️" if mode == "SAFE" else "⚡"
        mode_color = C.GREEN if mode == "SAFE" else C.YELLOW
        
        prob = state.config.get('commenting', {}).get('comment_probability_percent', 100)
        interval = state.config.get('monitor', {}).get('delete_check_interval_sec', 60)
        
        line1 = f"    {mode_icon} Режим: {mode_color}{mode}{C.RESET}"
        line2 = f"    🎲 Вероятность: {C.MAGENTA}{prob}%{C.RESET}"
        line3 = f"    ⏱️  Проверка удалений: каждые {C.CYAN}{interval}{C.RESET} сек"
        print(f"    " + self.box_line(line1))
        print(f"    " + self.box_line(line2))
        print(f"    " + self.box_line(line3))
        
        # === СТАТИСТИКА БД ===
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        section = f"  {C.BOLD}━━━ СТАТИСТИКА ЗА СЕГОДНЯ ━━━{C.RESET}"
        print(f"    " + self.box_line(section))
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        try:
            stats = await db.get_stats_today()
            sent = stats.get('sent', 0)
            deleted = stats.get('deleted', 0)
            warmup_actions = stats.get('warmup_actions', 0)
            
            line1 = f"    💬 Комментариев: {C.GREEN}{sent}{C.RESET} отправлено, {C.RED}{deleted}{C.RESET} удалено"
            line2 = f"    🔥 Действий прогрева: {C.GREEN}{warmup_actions}{C.RESET}"
            print(f"    " + self.box_line(line1))
            print(f"    " + self.box_line(line2))
        except Exception as e:
            logger.warning(f"Не удалось получить статистику: {e}", exc_info=True)
            line = f"    {C.DIM}Статистика недоступна{C.RESET}"
            print(f"    " + self.box_line(line))
        
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╚{'═' * W}╝{C.RESET}")
        
        print()
        input(f"    {C.DIM}[Enter] Вернуться в меню{C.RESET}")
    
    async def _show_data_info(self) -> None:
        """Показывает информацию о загруженных данных"""
        C = Colors
        W = self.WIDTH
        
        self._clear_screen()
        
        print()
        print(f"    {C.CYAN}╔{'═' * W}╗{C.RESET}")
        title = MenuUI.pad("📁 ИНФОРМАЦИЯ О ДАННЫХ", W, 'center')
        print(f"    {C.CYAN}║{C.RESET}{C.BOLD}{C.WHITE}{title}{C.RESET}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╠{'═' * W}╣{C.RESET}")
        
        folders = [
            ("КОММЕНТИРОВАНИЕ", [
                ("каналы", "📢 Каналы", ".txt"),
                ("sessions_комменты", "📱 Sessions", ".session"),
                ("tdata_комменты", "📦 TData", None),
                ("прокси_комменты", "🌐 Прокси", ".txt"),
            ]),
            ("ПРОГРЕВ", [
                ("каналы_прогрев", "📢 Каналы", ".txt"),
                ("чаты_прогрев", "💬 Чаты", ".txt"),
                ("sessions_прогрев", "📱 Sessions", ".session"),
                ("tdata_прогрев", "📦 TData", None),
                ("прокси_прогрев", "🌐 Прокси", ".txt"),
            ]),
        ]
        
        for section_name, items in folders:
            print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
            section = f"  {C.BOLD}━━━ {section_name} ━━━{C.RESET}"
            print(f"    " + self.box_line(section))
            print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
            
            for folder, label, ext in items:
                if os.path.exists(folder):
                    if ext == ".txt":
                        # Считаем строки в txt файлах
                        count = 0
                        for f in os.listdir(folder):
                            if f.endswith('.txt'):
                                try:
                                    with open(os.path.join(folder, f), 'r', encoding='utf-8') as file:
                                        count += len([l for l in file if l.strip() and not l.startswith('#')])
                                except Exception:
                                    pass
                        status = f"{C.GREEN}{count}{C.RESET} записей"
                    elif ext == ".session":
                        count = len([f for f in os.listdir(folder) if f.endswith('.session')])
                        status = f"{C.GREEN}{count}{C.RESET} файлов"
                    else:
                        # Папки tdata
                        count = len([d for d in os.listdir(folder) if os.path.isdir(os.path.join(folder, d))])
                        if count > 0:
                            status = f"{C.YELLOW}{count}{C.RESET} папок (ждут конверт)"
                        else:
                            status = f"{C.DIM}пусто{C.RESET}"
                else:
                    status = f"{C.DIM}папка не найдена{C.RESET}"
                
                line = f"    {label}: {status}"
                print(f"    " + self.box_line(line))
        
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╚{'═' * W}╝{C.RESET}")
        
        print()
        input(f"    {C.DIM}[Enter] Вернуться в меню{C.RESET}")
    
    async def _check_proxies(self) -> None:
        """Проверка прокси"""
        C = Colors
        W = self.WIDTH
        
        self._clear_screen()
        
        print()
        print(f"    {C.CYAN}╔{'═' * W}╗{C.RESET}")
        title = MenuUI.pad("🔍 ПРОВЕРКА ПРОКСИ", W, 'center')
        print(f"    {C.CYAN}║{C.RESET}{C.BOLD}{C.WHITE}{title}{C.RESET}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╠{'═' * W}╣{C.RESET}")
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        
        print(f"    " + self.box_line(f"    {C.YELLOW}[1]{C.RESET} 🌐 Проверить прокси комментирования"))
        print(f"    " + self.box_line(f"    {C.YELLOW}[2]{C.RESET} 🌐 Проверить прокси прогрева"))
        print(f"    " + self.box_line(f"    {C.YELLOW}[0]{C.RESET} 🔙 Назад"))
        
        print(f"    {C.CYAN}║{C.RESET}{MenuUI.pad('', W)}{C.CYAN}║{C.RESET}")
        print(f"    {C.CYAN}╚{'═' * W}╝{C.RESET}")
        
        print()
        choice = input(f"    {C.CYAN}👉 Выберите:{C.RESET} ").strip()
        
        if choice == '1':
            await self._run_proxy_check('comments')
        elif choice == '2':
            await self._run_proxy_check('warmup')
    
    async def _run_proxy_check(self, pool_type: str) -> None:
        """Запуск проверки прокси"""
        C = Colors
        
        from services.proxy_service import proxy_service
        
        pool_name = "комментирования" if pool_type == 'comments' else "прогрева"
        print()
        print(f"    {C.YELLOW}⏳ Проверяю прокси {pool_name}...{C.RESET}")
        print()
        
        try:
            if pool_type == 'comments':
                results = await proxy_service.check_all_comments_proxies()
            else:
                results = await proxy_service.check_all_warmup_proxies()
            
            ok_count = sum(1 for r in results if r.get('ok'))
            fail_count = len(results) - ok_count
            
            for i, r in enumerate(results, 1):
                addr = r.get('address', 'unknown')
                if r.get('ok'):
                    ping = r.get('ping', 0)
                    print(f"    {C.GREEN}✅ #{i:2} {addr:<40} OK   ping: {ping}ms{C.RESET}")
                else:
                    error = r.get('error', 'unknown')
                    print(f"    {C.RED}❌ #{i:2} {addr:<40} FAIL {error}{C.RESET}")
            
            print()
            print(f"    {'═' * 60}")
            print(f"    {C.BOLD}📊 РЕЗУЛЬТАТ:{C.RESET} {len(results)} всего │ {C.GREEN}{ok_count} ✅{C.RESET} │ {C.RED}{fail_count} ❌{C.RESET}")
            print(f"    {'═' * 60}")
        except Exception as e:
            logger.warning(f"Ошибка проверки прокси: {e}", exc_info=True)
            print(f"    {C.RED}❌ Ошибка: {e}{C.RESET}")
        
        print()
        input(f"    {C.DIM}[Enter] Продолжить{C.RESET}")
    
    async def _start_commenting(self) -> None:
        """Запуск комментирования"""
        C = Colors
        
        if scheduler.is_running('commenting'):
            print(f"\n    {C.YELLOW}⚠️  Комментирование уже запущено{C.RESET}")
            await asyncio.sleep(1)
            return
        
        print(f"\n    {C.CYAN}🚀 Запуск комментирования...{C.RESET}")
        
        try:
            from services.commenting_service import commenting_service
            from services.monitor_service import monitor_service
            
            await commenting_service.start()
            await monitor_service.start()
            
            # Открываем окно логов комментирования
            self._open_log_window('comments')
            
            print(f"    {C.GREEN}✅ Комментирование запущено!{C.RESET}")
            logger.info("Комментирование запущено")
        except Exception as e:
            logger.error(f"Ошибка запуска комментирования: {e}", exc_info=True)
            print(f"    {C.RED}❌ Ошибка: {e}{C.RESET}")
        
        await asyncio.sleep(1.5)
    
    async def _stop_commenting(self) -> None:
        """Остановка комментирования"""
        C = Colors
        
        if not scheduler.is_running('commenting'):
            print(f"\n    {C.YELLOW}⚠️  Комментирование не запущено{C.RESET}")
            await asyncio.sleep(1)
            return
        
        print(f"\n    {C.CYAN}⏹️  Остановка комментирования...{C.RESET}")
        
        try:
            from services.commenting_service import commenting_service
            from services.monitor_service import monitor_service
            
            await commenting_service.stop()
            await monitor_service.stop()
            
            print(f"    {C.GREEN}✅ Комментирование остановлено{C.RESET}")
            logger.info("Комментирование остановлено")
        except Exception as e:
            logger.error(f"Ошибка остановки: {e}", exc_info=True)
            print(f"    {C.RED}❌ Ошибка: {e}{C.RESET}")
        
        await asyncio.sleep(1.5)
    
    async def _start_warmup(self) -> None:
        """Запуск прогрева"""
        C = Colors
        
        if scheduler.is_running('warmup'):
            print(f"\n    {C.YELLOW}⚠️  Прогрев уже запущен{C.RESET}")
            await asyncio.sleep(1)
            return
        
        print(f"\n    {C.CYAN}🔥 Запуск прогрева...{C.RESET}")
        
        try:
            from services.warmup_service import warmup_service
            
            await warmup_service.start()
            
            # Открываем окно логов прогрева
            self._open_log_window('warmup')
            
            print(f"    {C.GREEN}✅ Прогрев запущен!{C.RESET}")
            logger.info("Прогрев запущен")
        except Exception as e:
            logger.error(f"Ошибка запуска прогрева: {e}", exc_info=True)
            print(f"    {C.RED}❌ Ошибка: {e}{C.RESET}")
        
        await asyncio.sleep(1.5)
    
    async def _stop_warmup(self) -> None:
        """Остановка прогрева"""
        C = Colors
        
        if not scheduler.is_running('warmup'):
            print(f"\n    {C.YELLOW}⚠️  Прогрев не запущен{C.RESET}")
            await asyncio.sleep(1)
            return
        
        print(f"\n    {C.CYAN}⏹️  Остановка прогрева...{C.RESET}")
        
        try:
            from services.warmup_service import warmup_service
            
            await warmup_service.stop()
            
            print(f"    {C.GREEN}✅ Прогрев остановлен{C.RESET}")
            logger.info("Прогрев остановлен")
        except Exception as e:
            logger.error(f"Ошибка остановки: {e}", exc_info=True)
            print(f"    {C.RED}❌ Ошибка: {e}{C.RESET}")
        
        await asyncio.sleep(1.5)
    
    async def _open_settings(self) -> None:
        """Открывает меню настроек"""
        from cli.settings_menu import SettingsMenu
        settings_menu = SettingsMenu()
        await settings_menu.run()
    
    async def run(self) -> None:
        """Главный цикл меню"""
        self._running = True
        
        while self._running:
            self._clear_screen()
            self._print_header()
            self._print_menu()
            
            try:
                choice = input(f"    {Colors.CYAN}👉 Выберите действие [1-9]:{Colors.RESET} ").strip()
                
                if choice == '1':
                    await self._start_commenting()
                elif choice == '2':
                    await self._stop_commenting()
                elif choice == '3':
                    await self._start_warmup()
                elif choice == '4':
                    await self._stop_warmup()
                elif choice == '5':
                    await self._show_status()
                elif choice == '6':
                    await self._open_settings()
                elif choice == '7':
                    await self._check_proxies()
                elif choice == '8':
                    await self._show_data_info()
                elif choice == '9' or choice.lower() == 'q':
                    await self._exit()
                else:
                    print(f"\n    {Colors.YELLOW}⚠️  Неверный выбор{Colors.RESET}")
                    await asyncio.sleep(0.5)
                    
            except KeyboardInterrupt:
                await self._exit()
            except Exception as e:
                logger.error(f"Ошибка в меню: {e}", exc_info=True)
                print(f"\n    {Colors.RED}❌ Ошибка: {e}{Colors.RESET}")
                await asyncio.sleep(2)
    
    async def _exit(self) -> None:
        """Выход из программы"""
        C = Colors
        
        print(f"\n    {C.CYAN}👋 Завершение работы...{C.RESET}")
        
        # Останавливаем все сервисы
        try:
            await scheduler.stop_all()
        except Exception as e:
            logger.warning(f"Ошибка при остановке сервисов: {e}", exc_info=True)
        
        print(f"    {C.GREEN}✅ До свидания!{C.RESET}\n")
        self._running = False


# Синглтон
menu = MenuUI()
