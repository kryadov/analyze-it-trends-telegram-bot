import asyncio
import re
import time
from typing import Optional, Dict, Any

from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from ..keyboards.inline import main_menu_keyboard
from ..services import container
from ..database.repository import get_or_create_user, get_active_channel, set_channel

router = Router()

# Simple in-memory rate limiter: one analysis per user per 10 minutes
_LAST_ANALYZE_AT: dict[int, float] = {}
_ANALYZE_COOLDOWN_SECONDS = 600


def _parse_analyze_args(text: str) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    m_days = re.search(r"--days\s+(\d+)", text)
    if m_days:
        params["days"] = int(m_days.group(1))
    m_format = re.search(r"--format\s+(pdf|excel|html)", text, flags=re.IGNORECASE)
    if m_format:
        fmt = m_format.group(1).lower()
        params["format"] = "xlsx" if fmt == "excel" else fmt
    return params


@router.message(CommandStart())
async def cmd_start(message: Message):
    cfg = container.config or {}
    admin_ids = cfg.get("bot", {}).get("admin_users", [])
    await get_or_create_user(container.db, message.from_user.id, message.from_user.username, message.from_user.first_name, admin_ids)

    text = (
        "👋 Привет! Я бот для анализа IT-трендов.\n\n"
        "Я помогу тебе:\n"
        "📊 Анализировать популярные технологии\n"
        "📈 Отслеживать тренды на биржах фриланса\n"
        "🔮 Прогнозировать спрос на IT-услуги\n\n"
        "Выбери действие ниже или используй команды:\n"
        "/analyze — запустить анализ вручную\n"
        "/set_channel <@username|id> — указать канал для публикации\n"
        "/get_channel — показать текущий канал"
    )
    await message.answer(text, reply_markup=main_menu_keyboard())


@router.message(Command(commands=["get_channel"]))
async def cmd_get_channel(message: Message):
    ch = await get_active_channel(container.db, message.from_user.id)
    if ch:
        await message.answer(f"📢 Текущий канал: {ch.channel_username or ch.channel_id}")
    else:
        await message.answer("Канал не настроен. Используй: /set_channel <@channel_username или channel_id>")


@router.message(Command(commands=["set_channel"]))
async def cmd_set_channel(message: Message):
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("Укажи канал: /set_channel <@username или id>")
        return
    raw = parts[1].strip()

    # Validate and resolve channel
    channel_id = raw
    channel_username: Optional[str] = None

    if raw.startswith("@"):
        channel_username = raw
        channel_id = raw

    # Check bot permissions by attempting to fetch chat and member info
    try:
        chat = await container.bot.get_chat(channel_id)
        me = await container.bot.get_chat_member(chat.id, container.bot.id)
        # If private channel, chat.username may be None
        can_post = getattr(me, "can_post_messages", True)
        if not can_post and chat.type in ("channel", "supergroup"):
            await message.answer("🚫 У бота нет прав для публикации в этом канале. Добавьте бота как администратора.")
            return
        channel_id = str(chat.id)
        channel_username = chat.username and ("@" + chat.username)
    except Exception:
        # Fallback: allow saving raw ID; real send will fail if wrong
        pass

    ch = await set_channel(container.db, message.from_user.id, channel_id, channel_username)
    await message.answer(f"✅ Канал сохранен: {channel_username or channel_id}")


@router.message(Command(commands=["analyze", "report"]))
async def cmd_analyze(message: Message):
    # Rate limiting
    now = time.time()
    last = _LAST_ANALYZE_AT.get(message.from_user.id, 0)
    if now - last < _ANALYZE_COOLDOWN_SECONDS:
        wait = int(_ANALYZE_COOLDOWN_SECONDS - (now - last))
        await message.answer(f"⏳ Слишком часто. Подожди {wait} сек.")
        return

    # Ensure channel is configured
    ch = await get_active_channel(container.db, message.from_user.id)
    if not ch:
        await message.answer("Сначала укажи канал публикации: /set_channel <@username или id>")
        return

    params = _parse_analyze_args(message.text or "")

    # Progress updates
    msg_id = await container.report_service.send_progress_updates(message.chat.id, "start")
    await container.report_service.send_progress_updates(message.chat.id, "reddit", msg_id)
    await asyncio.sleep(0.2)
    await container.report_service.send_progress_updates(message.chat.id, "freelance", msg_id)
    await asyncio.sleep(0.2)
    await container.report_service.send_progress_updates(message.chat.id, "trends", msg_id)

    try:
        path, data = await container.report_service.create_report(message.from_user.id, params)
        await container.report_service.send_progress_updates(message.chat.id, "report", msg_id)
        caption = container.report_service.format_caption(data)
        await container.report_service.publish_to_channel(ch.channel_id, path, caption)
        await container.report_service.send_progress_updates(message.chat.id, "done", msg_id)
        await container.bot.send_message(message.chat.id, f"✅ Отчет опубликован в {ch.channel_username or ch.channel_id}")
        _LAST_ANALYZE_AT[message.from_user.id] = time.time()
    except Exception as e:
        await container.bot.edit_message_text(chat_id=message.chat.id, message_id=msg_id, text="❗ Ошибка при генерации отчета.")
        await message.answer("Попробуй позже или сообщи администратору.")
        raise
