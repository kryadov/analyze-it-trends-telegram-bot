import asyncio
import datetime as dt
import logging
from typing import List, Dict, Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from . import container

logger = logging.getLogger(__name__)


class TrendsScheduler:
    def __init__(self, timezone: str = "UTC"):
        self.scheduler = AsyncIOScheduler(timezone=timezone)
        self.jobs_by_user: Dict[int, List[str]] = {}

    def start(self):
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Scheduler started")

    def shutdown(self):
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("Scheduler stopped")

    def _cron_from_time_days(self, time_str: str, days: List[str]) -> CronTrigger:
        hour, minute = map(int, time_str.split(":"))
        # days: e.g., ["mon","wed","fri"] or ["daily"]
        if len(days) == 1 and days[0].lower() == "daily":
            dow = "*"
        elif len(days) == 1 and days[0].lower() == "weekdays":
            dow = "mon-fri"
        else:
            dow = ",".join([d[:3].lower() for d in days])
        return CronTrigger(hour=hour, minute=minute, day_of_week=dow)

    def add_job(self, user_id: int, chat_id: int, time: str, days: List[str], timezone: str = "UTC") -> str:
        trigger = self._cron_from_time_days(time, days)
        job = self.scheduler.add_job(self.execute_scheduled_analysis, trigger=trigger, args=[{"user_id": user_id, "chat_id": chat_id}], replace_existing=False)
        self.jobs_by_user.setdefault(user_id, []).append(job.id)
        logger.info("Added job %s for user %s", job.id, user_id)
        return job.id

    def remove_job(self, job_id: str):
        try:
            self.scheduler.remove_job(job_id)
            logger.info("Removed job %s", job_id)
        except Exception:
            logger.warning("Failed to remove job %s", job_id)

    def pause_all(self, user_id: int):
        for job_id in self.jobs_by_user.get(user_id, []):
            try:
                self.scheduler.pause_job(job_id)
            except Exception:
                pass

    def resume_all(self, user_id: int):
        for job_id in self.jobs_by_user.get(user_id, []):
            try:
                self.scheduler.resume_job(job_id)
            except Exception:
                pass

    async def execute_scheduled_analysis(self, job_context: Dict[str, Any]):
        user_id = job_context["user_id"]
        chat_id = job_context["chat_id"]
        try:
            msg = await container.bot.send_message(chat_id, "⏳ Плановый анализ запущен...")
            path, data = await container.report_service.create_report(user_id, {"days": 7})
            caption = container.report_service.format_caption(data)
            # Get user channel
            from ..database.repository import get_active_channel
            ch = await get_active_channel(container.db, user_id)
            if not ch:
                await container.bot.send_message(chat_id, "⚠️ Канал не настроен, пропускаю публикацию.")
                return
            await container.report_service.publish_to_channel(ch.channel_id, path, caption)
            await container.bot.send_message(chat_id, f"✅ Плановый отчет опубликован в {ch.channel_username or ch.channel_id}")
        except Exception as e:
            logger.exception("Scheduled analysis failed: %s", e)
            try:
                await container.bot.send_message(chat_id, "❗ Ошибка при плановом анализе.")
            except Exception:
                pass
