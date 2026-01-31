#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║                    СБОРКА NEURO COMMENT BOT В .EXE                           ║
╠══════════════════════════════════════════════════════════════════════════════╣
║                                                                              ║
║  Этот скрипт собирает проект в один .exe файл                               ║
║                                                                              ║
║  Запуск:  python build_exe.py                                               ║
║                                                                              ║
║  Результат: dist/NeuroCommentBot.exe                                        ║
║                                                                              ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import sys
import subprocess
import shutil

def check_pyinstaller():
    """Проверка установки PyInstaller"""
    try:
        import PyInstaller
        print("✅ PyInstaller установлен")
        return True
    except ImportError:
        print("❌ PyInstaller не установлен")
        print("   Устанавливаю...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("✅ PyInstaller установлен")
        return True

def create_spec_file():
    """Создание .spec файла для PyInstaller"""
    
    spec_content = '''# -*- mode: python ; coding: utf-8 -*-

import os
import sys

block_cipher = None

# Путь к проекту
project_path = os.path.abspath('.')

# Собираем все Python файлы
added_files = [
    # Шаблоны веб-интерфейса
    ('web/templates', 'web/templates'),
    # Конфигурация
    ('config.yaml', '.'),
]

# Скрытые импорты для async библиотек
hidden_imports = [
    'uvicorn',
    'uvicorn.logging',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'fastapi',
    'starlette',
    'starlette.routing',
    'starlette.responses',
    'starlette.websockets',
    'aiohttp',
    'aiosqlite',
    'telethon',
    'openai',
    'socks',
    'python_socks',
    'yaml',
    'asyncio',
    'websockets',
    'httptools',
    'watchfiles',
    'websockets.legacy',
    'websockets.legacy.server',
    'anyio',
    'anyio._backends',
    'anyio._backends._asyncio',
]

a = Analysis(
    ['main.py'],
    pathex=[project_path],
    binaries=[],
    datas=added_files,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NeuroCommentBot',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,  # Показывать консоль для логов
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icon.ico' if os.path.exists('icon.ico') else None,
)
'''
    
    with open('NeuroCommentBot.spec', 'w', encoding='utf-8') as f:
        f.write(spec_content)
    
    print("✅ Создан NeuroCommentBot.spec")

def build_exe():
    """Сборка .exe"""
    print("\n" + "="*60)
    print("🔨 СБОРКА NEURO COMMENT BOT В .EXE")
    print("="*60 + "\n")
    
    # Проверяем PyInstaller
    check_pyinstaller()
    
    # Создаём spec файл
    create_spec_file()
    
    print("\n📦 Начинаю сборку...")
    print("   Это может занять 2-5 минут...\n")
    
    # Запускаем PyInstaller
    try:
        subprocess.check_call([
            sys.executable, "-m", "PyInstaller",
            "--clean",
            "--noconfirm",
            "NeuroCommentBot.spec"
        ])
        
        print("\n" + "="*60)
        print("✅ СБОРКА ЗАВЕРШЕНА УСПЕШНО!")
        print("="*60)
        print("\n📁 Файл находится в: dist/NeuroCommentBot.exe")
        print("\n⚠️  ВАЖНО: Рядом с .exe должны быть папки:")
        print("    • каналы/")
        print("    • tdata_комменты/")
        print("    • sessions_комменты/")
        print("    • прокси_комменты/")
        print("    • каналы_прогрев/")
        print("    • чаты_прогрев/")
        print("    • tdata_прогрев/")
        print("    • sessions_прогрев/")
        print("    • прокси_прогрев/")
        print("    • logs/")
        print("    • data/")
        print("    • config.yaml")
        print("\n🚀 Запуск: дважды кликни на NeuroCommentBot.exe")
        print("   Браузер откроется автоматически!\n")
        
        # Копируем config.yaml в dist
        if os.path.exists('config.yaml'):
            shutil.copy('config.yaml', 'dist/config.yaml')
            print("✅ config.yaml скопирован в dist/")
        
        # Создаём папки в dist
        folders = [
            'dist/каналы',
            'dist/tdata_комменты',
            'dist/sessions_комменты',
            'dist/прокси_комменты',
            'dist/каналы_прогрев',
            'dist/чаты_прогрев',
            'dist/tdata_прогрев',
            'dist/sessions_прогрев',
            'dist/прокси_прогрев',
            'dist/logs',
            'dist/data',
        ]
        
        for folder in folders:
            os.makedirs(folder, exist_ok=True)
        
        print("✅ Все папки созданы в dist/")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ ОШИБКА СБОРКИ: {e}")
        return False

def create_portable_package():
    """Создание портативного пакета с .bat файлом"""
    
    bat_content = '''@echo off
chcp 65001 >nul
title Neuro Comment Bot
echo.
echo ╔══════════════════════════════════════════════════════════════╗
echo ║              NEURO COMMENT BOT - ЗАПУСК                      ║
echo ╚══════════════════════════════════════════════════════════════╝
echo.
echo Запускаю бота...
echo Браузер откроется автоматически на http://localhost:8080
echo.
NeuroCommentBot.exe
pause
'''
    
    with open('dist/Запустить.bat', 'w', encoding='utf-8') as f:
        f.write(bat_content)
    
    print("✅ Создан Запустить.bat")
    
    # README
    readme_content = '''# 🤖 NEURO COMMENT BOT

## 🚀 Запуск

1. Дважды кликните на `Запустить.bat` или `NeuroCommentBot.exe`
2. Браузер откроется автоматически на http://localhost:8080
3. Управляйте ботом через веб-интерфейс

## 📁 Структура папок

```
NeuroCommentBot/
├── NeuroCommentBot.exe     # Главный файл
├── Запустить.bat           # Запуск через bat
├── config.yaml             # Настройки (API ключи)
│
├── каналы/                 # Каналы для комментирования
│   └── channels.txt        # Один канал на строку (@channel)
│
├── sessions_комменты/      # .session файлы аккаунтов
├── tdata_комменты/         # Папки tdata1, tdata2...
├── прокси_комменты/        # Прокси (socks5://user:pass@host:port)
│
├── каналы_прогрев/         # Каналы для прогрева
├── чаты_прогрев/           # Чаты для прогрева
├── sessions_прогрев/       # Sessions прогрева
├── tdata_прогрев/          # TData прогрева
├── прокси_прогрев/         # Прокси прогрева
│
├── logs/                   # Логи
└── data/                   # База данных
```

## ⚙️ Первоначальная настройка

1. Откройте `config.yaml` в блокноте
2. Заполните:
   - telegram.api_id: ВАШЕ_ID
   - telegram.api_hash: ВАШ_HASH
   - gpt.api_key: sk-ваш-ключ-openai

3. Добавьте .session файлы в папку sessions_комменты/
4. Добавьте каналы в каналы/channels.txt

## 🌐 Веб-интерфейс

После запуска откройте: http://localhost:8080

Там вы можете:
- 📊 Смотреть статистику
- ▶️ Запускать/останавливать комментирование
- 🔥 Управлять прогревом
- 📱 Загружать аккаунты (drag & drop)
- 📢 Добавлять каналы пачкой
- 🌐 Управлять прокси
- ⚙️ Настраивать параметры
- 🤖 Настраивать GPT

## ❓ Проблемы?

1. Не открывается браузер → откройте http://localhost:8080 вручную
2. Ошибка порта → закройте другую программу на порту 8080
3. Не видит аккаунты → положите .session файлы в sessions_комменты/

---
Neuro Comment Bot v3.0 Premium
'''
    
    with open('dist/README.txt', 'w', encoding='utf-8') as f:
        f.write(readme_content)
    
    print("✅ Создан README.txt")

if __name__ == '__main__':
    if build_exe():
        create_portable_package()
        
        print("\n" + "="*60)
        print("🎉 ПОРТАТИВНЫЙ ПАКЕТ ГОТОВ!")
        print("="*60)
        print("\n📁 Папка dist/ содержит:")
        print("   • NeuroCommentBot.exe")
        print("   • Запустить.bat")
        print("   • config.yaml")
        print("   • README.txt")
        print("   • Все необходимые папки")
        print("\n📦 Можете заархивировать папку dist/ и распространять!")
        print()
