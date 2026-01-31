# -*- coding: utf-8 -*-
"""
NEURO COMMENT BOT — Premium Web Server
ПОЛНОСТЬЮ РАБОЧИЙ API для всех функций
"""

import os
import sys
import json
import asyncio
import aiofiles
import zipfile
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Добавляем путь к проекту
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.logger import logger, comments_logger, warmup_logger
from core.state import state
from core.database import db
from core.scheduler import scheduler

app = FastAPI(title="NEURO COMMENT BOT", version="3.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# WebSocket connections для логов
log_clients: List[WebSocket] = []

# Корневая папка проекта
PROJECT_ROOT = Path(__file__).parent.parent


# ============================================================
# МОДЕЛИ ДАННЫХ
# ============================================================

class ModeRequest(BaseModel):
    mode: str

class ChannelsRequest(BaseModel):
    channels: List[str]
    type: str = "comments"  # comments, warmup_channels, warmup_chats

class ProxyRequest(BaseModel):
    proxies: List[str]
    type: str = "comments"  # comments, warmup

class SettingsRequest(BaseModel):
    delays: Optional[Dict[str, Any]] = None
    limits: Optional[Dict[str, Any]] = None
    probability: Optional[int] = None
    check_interval: Optional[int] = None
    sanctions: Optional[Dict[str, Any]] = None
    telegram: Optional[Dict[str, str]] = None

class GPTSettingsRequest(BaseModel):
    model: Optional[str] = None
    api_key: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    prompt: Optional[str] = None


# ============================================================
# СЛУЖЕБНЫЕ ФУНКЦИИ
# ============================================================

async def broadcast_log(log_type: str, message: str):
    """Отправить лог всем подключённым клиентам"""
    log_entry = {
        "time": datetime.now().strftime("%H:%M:%S"),
        "type": log_type,
        "message": message
    }
    
    disconnected = []
    for client in log_clients:
        try:
            await client.send_json(log_entry)
        except:
            disconnected.append(client)
    
    for client in disconnected:
        if client in log_clients:
            log_clients.remove(client)


def get_project_dirs() -> Dict[str, Path]:
    """Получить пути к директориям проекта"""
    return {
        "каналы": PROJECT_ROOT / "каналы",
        "tdata_комменты": PROJECT_ROOT / "tdata_комменты",
        "sessions_комменты": PROJECT_ROOT / "sessions_комменты",
        "прокси_комменты": PROJECT_ROOT / "прокси_комменты",
        "каналы_прогрев": PROJECT_ROOT / "каналы_прогрев",
        "чаты_прогрев": PROJECT_ROOT / "чаты_прогрев",
        "tdata_прогрев": PROJECT_ROOT / "tdata_прогрев",
        "sessions_прогрев": PROJECT_ROOT / "sessions_прогрев",
        "прокси_прогрев": PROJECT_ROOT / "прокси_прогрев",
        "logs": PROJECT_ROOT / "logs",
        "data": PROJECT_ROOT / "data",
    }


def ensure_dirs():
    """Создать все необходимые папки"""
    for path in get_project_dirs().values():
        path.mkdir(parents=True, exist_ok=True)


# ============================================================
# ГЛАВНАЯ СТРАНИЦА
# ============================================================

@app.get("/", response_class=HTMLResponse)
async def index():
    """Главная страница"""
    template_path = Path(__file__).parent / "templates" / "index.html"
    if template_path.exists():
        async with aiofiles.open(template_path, "r", encoding="utf-8") as f:
            return await f.read()
    return HTMLResponse("<h1>NEURO COMMENT BOT</h1><p>Template not found</p>")


# ============================================================
# СТАТУС И СТАТИСТИКА
# ============================================================

@app.get("/api/status")
async def get_status():
    """Получить полный статус системы"""
    ensure_dirs()
    dirs = get_project_dirs()
    
    def count_sessions(path: Path) -> int:
        if not path.exists():
            return 0
        return len(list(path.glob("*.session")))
    
    def count_tdata(path: Path) -> int:
        if not path.exists():
            return 0
        return len([d for d in path.iterdir() if d.is_dir()])
    
    def read_list_file(path: Path) -> List[str]:
        if not path.exists():
            return []
        items = []
        for file in path.glob("*.txt"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    items.extend([line.strip() for line in f if line.strip() and not line.startswith("#")])
            except:
                pass
        return items
    
    def count_proxy(path: Path) -> Dict[str, int]:
        proxies = read_list_file(path)
        return {"total": len(proxies), "ok": len(proxies), "bad": 0}
    
    # Статистика из БД
    stats = {"comments_today": 0, "successful": 0, "deleted": 0, "warmup_actions": 0}
    try:
        await db.init()
        db_stats = await db.get_stats_today()
        if db_stats:
            stats["comments_today"] = db_stats.get("total", 0)
            stats["successful"] = db_stats.get("successful", 0)
            stats["deleted"] = db_stats.get("deleted", 0)
    except Exception as e:
        logger.warning(f"Ошибка получения статистики: {e}")
    
    # Каналы
    channels_comments = read_list_file(dirs["каналы"])
    channels_warmup = read_list_file(dirs["каналы_прогрев"])
    chats_warmup = read_list_file(dirs["чаты_прогрев"])
    
    # Прокси
    proxy_comments = count_proxy(dirs["прокси_комменты"])
    proxy_warmup = count_proxy(dirs["прокси_прогрев"])
    
    # Статус сервисов
    commenting_running = scheduler.is_running("commenting")
    warmup_running = scheduler.is_running("warmup")
    monitor_running = scheduler.is_running("monitor")
    
    return {
        "mode": state.get_mode(),
        "services": {
            "commenting": {
                "running": commenting_running,
                "uptime": scheduler.get_uptime("commenting") if commenting_running else 0
            },
            "warmup": {
                "running": warmup_running,
                "uptime": scheduler.get_uptime("warmup") if warmup_running else 0
            },
            "monitor": {
                "running": monitor_running
            }
        },
        "stats": stats,
        "accounts": {
            "comments": {
                "sessions": count_sessions(dirs["sessions_комменты"]),
                "tdata": count_tdata(dirs["tdata_комменты"]),
            },
            "warmup": {
                "sessions": count_sessions(dirs["sessions_прогрев"]),
                "tdata": count_tdata(dirs["tdata_прогрев"]),
            }
        },
        "channels": {
            "comments": len(channels_comments),
            "warmup": len(channels_warmup),
            "chats": len(chats_warmup),
            "active": len(channels_comments)
        },
        "proxy": {
            "comments": proxy_comments,
            "warmup": proxy_warmup,
            "ok": proxy_comments["ok"] + proxy_warmup["ok"],
            "bad": proxy_comments["bad"] + proxy_warmup["bad"]
        }
    }


@app.get("/api/stats/today")
async def get_stats_today():
    """Статистика за сегодня"""
    try:
        await db.init()
        return await db.get_stats_today()
    except Exception as e:
        return {"error": str(e)}


# ============================================================
# УПРАВЛЕНИЕ СЕРВИСАМИ
# ============================================================

@app.post("/api/commenting/start")
async def start_commenting():
    """Запустить комментирование"""
    try:
        from services.account_service import account_service
        from services.commenting_service import commenting_service
        from services.monitor_service import monitor_service
        
        # Загружаем аккаунты
        await account_service.load_accounts('comments')
        
        # Запускаем сервисы
        await commenting_service.start()
        await monitor_service.start()
        
        await broadcast_log("success", "🚀 Комментирование запущено")
        logger.info("Комментирование запущено через Web API")
        
        return {"status": "ok", "message": "Комментирование запущено"}
        
    except Exception as e:
        await broadcast_log("error", f"❌ Ошибка запуска: {e}")
        logger.error(f"Ошибка запуска комментирования: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/commenting/stop")
async def stop_commenting():
    """Остановить комментирование"""
    try:
        from services.commenting_service import commenting_service
        from services.monitor_service import monitor_service
        
        await commenting_service.stop()
        await monitor_service.stop()
        
        await broadcast_log("info", "⏹️ Комментирование остановлено")
        logger.info("Комментирование остановлено через Web API")
        
        return {"status": "ok", "message": "Комментирование остановлено"}
        
    except Exception as e:
        logger.error(f"Ошибка остановки комментирования: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/warmup/start")
async def start_warmup():
    """Запустить прогрев"""
    try:
        from services.account_service import account_service
        from services.warmup_service import warmup_service
        
        # Загружаем аккаунты прогрева
        await account_service.load_accounts('warmup')
        
        # Запускаем прогрев
        await warmup_service.start()
        
        await broadcast_log("success", "🔥 Прогрев запущен")
        logger.info("Прогрев запущен через Web API")
        
        return {"status": "ok", "message": "Прогрев запущен"}
        
    except Exception as e:
        await broadcast_log("error", f"❌ Ошибка запуска прогрева: {e}")
        logger.error(f"Ошибка запуска прогрева: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/warmup/stop")
async def stop_warmup():
    """Остановить прогрев"""
    try:
        from services.warmup_service import warmup_service
        
        await warmup_service.stop()
        
        # Дополнительно через scheduler
        await scheduler.stop_service('warmup')
        
        await broadcast_log("info", "⏹️ Прогрев остановлен")
        logger.info("Прогрев остановлен через Web API")
        
        return {"status": "ok", "message": "Прогрев остановлен"}
        
    except Exception as e:
        logger.error(f"Ошибка остановки прогрева: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# РЕЖИМ РАБОТЫ
# ============================================================

@app.get("/api/mode")
async def get_mode():
    """Получить текущий режим"""
    return {"mode": state.get_mode()}


@app.post("/api/mode")
async def set_mode(request: ModeRequest):
    """Установить режим SAFE/NORMAL"""
    mode = request.mode.upper()
    state.set_mode(mode)
    state.save_config()
    
    await broadcast_log("info", f"🛡️ Режим изменён на {mode}")
    return {"status": "ok", "mode": mode}


# ============================================================
# АККАУНТЫ
# ============================================================

@app.get("/api/accounts")
async def get_accounts():
    """Получить список аккаунтов"""
    ensure_dirs()
    dirs = get_project_dirs()
    
    accounts = {
        "comments": {"sessions": [], "tdata": []},
        "warmup": {"sessions": [], "tdata": []}
    }
    
    # Sessions для комментирования
    sessions_dir = dirs["sessions_комменты"]
    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.session"):
            accounts["comments"]["sessions"].append({
                "name": session_file.stem,
                "path": str(session_file),
                "size": session_file.stat().st_size,
                "status": "ready"
            })
    
    # TData для комментирования
    tdata_dir = dirs["tdata_комменты"]
    if tdata_dir.exists():
        for tdata_folder in tdata_dir.iterdir():
            if tdata_folder.is_dir():
                accounts["comments"]["tdata"].append({
                    "name": tdata_folder.name,
                    "path": str(tdata_folder),
                    "status": "pending"
                })
    
    # Sessions для прогрева
    sessions_dir = dirs["sessions_прогрев"]
    if sessions_dir.exists():
        for session_file in sessions_dir.glob("*.session"):
            accounts["warmup"]["sessions"].append({
                "name": session_file.stem,
                "path": str(session_file),
                "size": session_file.stat().st_size,
                "status": "ready"
            })
    
    # TData для прогрева
    tdata_dir = dirs["tdata_прогрев"]
    if tdata_dir.exists():
        for tdata_folder in tdata_dir.iterdir():
            if tdata_folder.is_dir():
                accounts["warmup"]["tdata"].append({
                    "name": tdata_folder.name,
                    "path": str(tdata_folder),
                    "status": "pending"
                })
    
    return accounts


@app.post("/api/accounts/upload")
async def upload_accounts(
    files: List[UploadFile] = File(...),
    account_type: str = Form(default="comments")
):
    """Загрузить аккаунты (session или zip с tdata)"""
    ensure_dirs()
    dirs = get_project_dirs()
    
    if account_type == "warmup":
        sessions_dir = dirs["sessions_прогрев"]
        tdata_dir = dirs["tdata_прогрев"]
    else:
        sessions_dir = dirs["sessions_комменты"]
        tdata_dir = dirs["tdata_комменты"]
    
    sessions_dir.mkdir(parents=True, exist_ok=True)
    tdata_dir.mkdir(parents=True, exist_ok=True)
    
    uploaded = 0
    errors = []
    
    for file in files:
        try:
            filename = file.filename or "unknown"
            content = await file.read()
            
            if filename.endswith(".session"):
                # Сохраняем session файл
                file_path = sessions_dir / filename
                async with aiofiles.open(file_path, "wb") as f:
                    await f.write(content)
                uploaded += 1
                await broadcast_log("success", f"📱 Загружен аккаунт: {filename}")
                logger.info(f"Загружен session: {filename}")
                
            elif filename.endswith(".zip"):
                # Распаковываем ZIP с tdata
                with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp:
                    tmp.write(content)
                    tmp_path = tmp.name
                
                try:
                    folder_name = filename.replace(".zip", "")
                    extract_path = tdata_dir / folder_name
                    extract_path.mkdir(parents=True, exist_ok=True)
                    
                    with zipfile.ZipFile(tmp_path, "r") as zip_ref:
                        zip_ref.extractall(extract_path)
                    
                    uploaded += 1
                    await broadcast_log("success", f"📁 Загружен tdata: {folder_name}")
                    logger.info(f"Загружен tdata: {folder_name}")
                finally:
                    os.unlink(tmp_path)
            else:
                errors.append(f"Неизвестный формат: {filename}")
                
        except Exception as e:
            error_msg = f"Ошибка загрузки {file.filename}: {e}"
            errors.append(error_msg)
            await broadcast_log("error", f"❌ {error_msg}")
            logger.error(error_msg, exc_info=True)
    
    return {
        "status": "ok",
        "uploaded": uploaded,
        "errors": errors
    }


@app.delete("/api/accounts/{account_type}/{account_name}")
async def delete_account(account_type: str, account_name: str):
    """Удалить аккаунт"""
    dirs = get_project_dirs()
    
    if account_type == "warmup":
        sessions_dir = dirs["sessions_прогрев"]
        tdata_dir = dirs["tdata_прогрев"]
    else:
        sessions_dir = dirs["sessions_комменты"]
        tdata_dir = dirs["tdata_комменты"]
    
    # Пробуем удалить session
    session_file = sessions_dir / f"{account_name}.session"
    if session_file.exists():
        session_file.unlink()
        await broadcast_log("info", f"🗑️ Удалён аккаунт: {account_name}")
        return {"status": "ok"}
    
    # Пробуем удалить tdata
    tdata_folder = tdata_dir / account_name
    if tdata_folder.exists():
        shutil.rmtree(tdata_folder)
        await broadcast_log("info", f"🗑️ Удалён tdata: {account_name}")
        return {"status": "ok"}
    
    raise HTTPException(status_code=404, detail="Аккаунт не найден")


# ============================================================
# КАНАЛЫ
# ============================================================

@app.get("/api/channels")
async def get_channels():
    """Получить список каналов"""
    ensure_dirs()
    dirs = get_project_dirs()
    
    def read_channels(path: Path) -> List[Dict]:
        if not path.exists():
            return []
        channels = []
        for file in path.glob("*.txt"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            channels.append({
                                "name": line,
                                "status": "active",
                                "file": file.name
                            })
            except:
                pass
        return channels
    
    return {
        "comments": read_channels(dirs["каналы"]),
        "warmup_channels": read_channels(dirs["каналы_прогрев"]),
        "warmup_chats": read_channels(dirs["чаты_прогрев"])
    }


@app.post("/api/channels/add")
async def add_channels(request: ChannelsRequest):
    """Добавить каналы"""
    ensure_dirs()
    dirs = get_project_dirs()
    
    if request.type == "comments":
        target_dir = dirs["каналы"]
        filename = "channels.txt"
    elif request.type == "warmup_channels":
        target_dir = dirs["каналы_прогрев"]
        filename = "channels.txt"
    else:
        target_dir = dirs["чаты_прогрев"]
        filename = "chats.txt"
    
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / filename
    
    # Читаем существующие
    existing = set()
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            existing = set(line.strip() for line in f if line.strip() and not line.startswith("#"))
    
    # Добавляем новые
    added = 0
    for channel in request.channels:
        channel = channel.strip()
        if channel and channel not in existing:
            existing.add(channel)
            added += 1
    
    # Записываем
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(existing)))
    
    await broadcast_log("success", f"📢 Добавлено {added} каналов")
    logger.info(f"Добавлено {added} каналов в {request.type}")
    
    return {"status": "ok", "added": added, "total": len(existing)}


@app.delete("/api/channels/{channel_type}/{channel_name:path}")
async def delete_channel(channel_type: str, channel_name: str):
    """Удалить канал"""
    dirs = get_project_dirs()
    
    if channel_type == "comments":
        target_dir = dirs["каналы"]
    elif channel_type == "warmup_channels":
        target_dir = dirs["каналы_прогрев"]
    else:
        target_dir = dirs["чаты_прогрев"]
    
    deleted = False
    for file in target_dir.glob("*.txt"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            new_lines = [line for line in lines if line.strip() != channel_name]
            
            if len(new_lines) != len(lines):
                with open(file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                deleted = True
                break
        except:
            pass
    
    if deleted:
        await broadcast_log("info", f"🗑️ Удалён канал: {channel_name}")
        return {"status": "ok"}
    
    raise HTTPException(status_code=404, detail="Канал не найден")


# ============================================================
# ПРОКСИ
# ============================================================

@app.get("/api/proxy")
async def get_proxy():
    """Получить список прокси"""
    ensure_dirs()
    dirs = get_project_dirs()
    
    def read_proxies(path: Path) -> List[Dict]:
        if not path.exists():
            return []
        proxies = []
        for file in path.glob("*.txt"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            proxy_type = "socks5"
                            if line.startswith("http://"):
                                proxy_type = "http"
                            elif line.startswith("socks5://"):
                                proxy_type = "socks5"
                            
                            proxies.append({
                                "address": line,
                                "type": proxy_type,
                                "status": "unknown",
                                "ping": None
                            })
            except:
                pass
        return proxies
    
    return {
        "comments": read_proxies(dirs["прокси_комменты"]),
        "warmup": read_proxies(dirs["прокси_прогрев"])
    }


@app.post("/api/proxy/add")
async def add_proxy(request: ProxyRequest):
    """Добавить прокси"""
    ensure_dirs()
    dirs = get_project_dirs()
    
    if request.type == "warmup":
        target_dir = dirs["прокси_прогрев"]
    else:
        target_dir = dirs["прокси_комменты"]
    
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / "proxies.txt"
    
    # Читаем существующие
    existing = set()
    if file_path.exists():
        with open(file_path, "r", encoding="utf-8") as f:
            existing = set(line.strip() for line in f if line.strip())
    
    # Добавляем новые
    added = 0
    for proxy in request.proxies:
        proxy = proxy.strip()
        if proxy and proxy not in existing:
            existing.add(proxy)
            added += 1
    
    # Записываем
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(existing)))
    
    await broadcast_log("success", f"🌐 Добавлено {added} прокси")
    logger.info(f"Добавлено {added} прокси в {request.type}")
    
    return {"status": "ok", "added": added, "total": len(existing)}


@app.post("/api/proxy/check")
async def check_proxy(proxy_type: str = Query(default="comments")):
    """Проверить все прокси"""
    await broadcast_log("info", "🔍 Проверяю прокси...")
    
    try:
        from services.proxy_service import proxy_service
        
        if proxy_type == "warmup":
            result = await proxy_service.check_all_warmup_proxies()
        else:
            result = await proxy_service.check_all_comments_proxies()
        
        await broadcast_log("success", f"✅ Прокси проверены: {result.get('ok', 0)} ОК, {result.get('bad', 0)} BAD")
        return result
        
    except Exception as e:
        await broadcast_log("error", f"❌ Ошибка проверки прокси: {e}")
        return {"ok": 0, "bad": 0, "error": str(e)}


@app.delete("/api/proxy/{proxy_type}/{proxy_address:path}")
async def delete_proxy(proxy_type: str, proxy_address: str):
    """Удалить прокси"""
    dirs = get_project_dirs()
    
    if proxy_type == "warmup":
        target_dir = dirs["прокси_прогрев"]
    else:
        target_dir = dirs["прокси_комменты"]
    
    deleted = False
    for file in target_dir.glob("*.txt"):
        try:
            with open(file, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            new_lines = [line for line in lines if line.strip() != proxy_address]
            
            if len(new_lines) != len(lines):
                with open(file, "w", encoding="utf-8") as f:
                    f.writelines(new_lines)
                deleted = True
                break
        except:
            pass
    
    if deleted:
        await broadcast_log("info", f"🗑️ Удалён прокси")
        return {"status": "ok"}
    
    raise HTTPException(status_code=404, detail="Прокси не найден")


# ============================================================
# НАСТРОЙКИ
# ============================================================

@app.get("/api/settings")
async def get_settings():
    """Получить настройки"""
    config = state.config
    return {
        "mode": state.get_mode(),
        "delays": config.get("delays", {}),
        "limits": config.get("limits", {}),
        "probability": config.get("commenting", {}).get("probability_percent", 75),
        "check_interval": config.get("monitor", {}).get("delete_check_interval_sec", 60),
        "sanctions": config.get("sanctions", {}),
        "telegram": {
            "api_id": config.get("telegram", {}).get("api_id", ""),
            "api_hash": "***" if config.get("telegram", {}).get("api_hash") else ""
        }
    }


@app.post("/api/settings")
async def save_settings(request: SettingsRequest):
    """Сохранить настройки"""
    try:
        if request.delays:
            if "delays" not in state.config:
                state.config["delays"] = {}
            state.config["delays"].update(request.delays)
        
        if request.limits:
            if "limits" not in state.config:
                state.config["limits"] = {}
            state.config["limits"].update(request.limits)
        
        if request.probability is not None:
            if "commenting" not in state.config:
                state.config["commenting"] = {}
            state.config["commenting"]["probability_percent"] = request.probability
        
        if request.check_interval is not None:
            if "monitor" not in state.config:
                state.config["monitor"] = {}
            state.config["monitor"]["delete_check_interval_sec"] = request.check_interval
        
        if request.sanctions:
            if "sanctions" not in state.config:
                state.config["sanctions"] = {}
            state.config["sanctions"].update(request.sanctions)
        
        if request.telegram:
            if "telegram" not in state.config:
                state.config["telegram"] = {}
            if request.telegram.get("api_id"):
                state.config["telegram"]["api_id"] = request.telegram["api_id"]
            if request.telegram.get("api_hash") and request.telegram["api_hash"] != "***":
                state.config["telegram"]["api_hash"] = request.telegram["api_hash"]
        
        state.save_config()
        await broadcast_log("success", "💾 Настройки сохранены")
        logger.info("Настройки сохранены через Web API")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# GPT НАСТРОЙКИ
# ============================================================

@app.get("/api/gpt/settings")
async def get_gpt_settings():
    """Получить настройки GPT"""
    config = state.config.get("gpt", {})
    return {
        "model": config.get("model", "gpt-4.1"),
        "api_key": "***" if config.get("api_key") else "",
        "temperature": config.get("temperature", 0.9),
        "max_tokens": config.get("max_tokens", 60),
        "prompt": config.get("prompt", "")
    }


@app.post("/api/gpt/settings")
async def save_gpt_settings(request: GPTSettingsRequest):
    """Сохранить настройки GPT"""
    try:
        if "gpt" not in state.config:
            state.config["gpt"] = {}
        
        if request.model:
            state.config["gpt"]["model"] = request.model
        
        if request.api_key and request.api_key != "***":
            state.config["gpt"]["api_key"] = request.api_key
        
        if request.temperature is not None:
            state.config["gpt"]["temperature"] = request.temperature
        
        if request.max_tokens is not None:
            state.config["gpt"]["max_tokens"] = request.max_tokens
        
        if request.prompt is not None:
            state.config["gpt"]["prompt"] = request.prompt
        
        state.save_config()
        await broadcast_log("success", "🤖 Настройки GPT сохранены")
        logger.info("Настройки GPT сохранены через Web API")
        
        return {"status": "ok"}
        
    except Exception as e:
        logger.error(f"Ошибка сохранения GPT настроек: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/gpt/test")
async def test_gpt():
    """Тест генерации комментария"""
    try:
        from services.gpt_service import gpt_service
        
        test_post = "Вышел новый трек от любимого исполнителя! 🎵"
        comment = await gpt_service.generate_comment(test_post, "@test_channel")
        
        await broadcast_log("success", f"🤖 Тест GPT: {comment}")
        
        return {"status": "ok", "comment": comment}
        
    except Exception as e:
        await broadcast_log("error", f"❌ Ошибка теста GPT: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
# ЛОГИ
# ============================================================

@app.get("/api/logs")
async def get_logs(log_type: str = "all", limit: int = 100):
    """Получить логи"""
    dirs = get_project_dirs()
    logs_dir = dirs["logs"]
    
    logs = []
    
    if log_type in ["all", "comments"]:
        comments_log = logs_dir / "comments.log"
        if comments_log.exists():
            try:
                with open(comments_log, "r", encoding="utf-8") as f:
                    lines = f.readlines()[-limit:]
                    for line in lines:
                        logs.append({"type": "comments", "message": line.strip()})
            except:
                pass
    
    if log_type in ["all", "warmup"]:
        warmup_log = logs_dir / "warmup.log"
        if warmup_log.exists():
            try:
                with open(warmup_log, "r", encoding="utf-8") as f:
                    lines = f.readlines()[-limit:]
                    for line in lines:
                        logs.append({"type": "warmup", "message": line.strip()})
            except:
                pass
    
    return {"logs": logs[-limit:]}


# ============================================================
# WEBSOCKET ДЛЯ ЛОГОВ В РЕАЛЬНОМ ВРЕМЕНИ
# ============================================================

@app.websocket("/ws/logs")
async def websocket_logs(websocket: WebSocket):
    """WebSocket для логов в реальном времени"""
    await websocket.accept()
    log_clients.append(websocket)
    
    try:
        await websocket.send_json({
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": "info",
            "message": "🔌 Подключено к серверу логов"
        })
        
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                if data == "ping":
                    await websocket.send_json({"type": "pong"})
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
                
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.debug(f"WebSocket error: {e}")
    finally:
        if websocket in log_clients:
            log_clients.remove(websocket)


# ============================================================
# ЗАПУСК СЕРВЕРА
# ============================================================

async def start_server(host: str = "0.0.0.0", port: int = 8080):
    """Запустить веб-сервер"""
    ensure_dirs()
    
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="warning",
        access_log=False
    )
    server = uvicorn.Server(config)
    await server.serve()


def run_server(host: str = "0.0.0.0", port: int = 8080):
    """Запустить сервер (синхронно)"""
    ensure_dirs()
    uvicorn.run(app, host=host, port=port, log_level="warning")


if __name__ == "__main__":
    run_server()
