import logging
from aiogram.types import ErrorEvent
from aiogram import Router

router = Router()
logger = logging.getLogger(__name__)


@router.errors()
async def handle_unknown_error(event: ErrorEvent):
    logger.exception("Unexpected error: %s", event.exception)
    try:
        if event.update and event.update.message:
            await event.update.message.answer("❗ Произошла неизвестная ошибка. Пожалуйста, попробуйте позже.")
    except Exception:
        pass


async def handle_mcp_connection_error(update, context=None):
    if hasattr(update, "message") and update.message:
        await update.message.answer("⚠️ MCP-сервер недоступен. Попробуйте позже.")


async def handle_channel_permission_error(update, context=None):
    if hasattr(update, "message") and update.message:
        await update.message.answer("🚫 У бота нет прав для публикации в этом канале. Добавьте бота как администратора с правом публикации.")


async def handle_rate_limit_error(update, context=None):
    if hasattr(update, "message") and update.message:
        await update.message.answer("⏳ Превышен лимит запросов. Попробуйте чуть позже.")
