import asyncio
from aiogram import Router, F
from aiogram.types import CallbackQuery

from services import container
from database.repository import get_active_channel

router = Router()


@router.callback_query(F.data == "run_analysis")
async def on_run_analysis(cb: CallbackQuery):
    await cb.answer()
    # Reuse analyze flow with defaults
    ch = await get_active_channel(container.db, cb.from_user.id)
    if not ch:
        await cb.message.answer("Сначала укажи канал публикации: /set_channel <@username или id>")
        return

    msg = await cb.message.answer("⏳ Запускаю анализ...")
    try:
        path, data = await container.report_service.create_report(cb.from_user.id, {"days": 1})
        caption = container.report_service.format_caption(data)
        await container.report_service.publish_to_channel(ch.channel_id, path, caption)
        await cb.message.answer(f"✅ Отчет опубликован в {ch.channel_username or ch.channel_id}")
    except Exception:
        await cb.message.answer("❗ Ошибка при генерации отчета. Попробуй позже.")
