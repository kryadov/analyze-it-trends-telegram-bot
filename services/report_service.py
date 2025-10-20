import asyncio
import datetime as dt
import json
import os
from typing import Dict, Any, Optional, Tuple

from aiogram import Bot

from .mcp_client import MCPClient
from ..database.repository import Database, get_active_channel, get_user_settings, save_report


class ReportService:
    def __init__(self, bot: Bot, db: Database, mcp: MCPClient, storage_path: str, caption_template: str):
        self.bot = bot
        self.db = db
        self.mcp = mcp
        self.storage_path = storage_path
        self.caption_template = caption_template
        os.makedirs(self.storage_path, exist_ok=True)

    async def send_progress_updates(self, chat_id: int, stage: str, message_id: Optional[int] = None) -> int:
        stages_map = {
            "start": "⏳ Запускаю анализ...",
            "reddit": "🔍 Собираю данные с Reddit...",
            "freelance": "💼 Анализирую биржи фриланса...",
            "trends": "📊 Обрабатываю Google Trends...",
            "report": "📝 Генерирую отчет...",
            "done": "✅ Готово!",
        }
        text = stages_map.get(stage, stage)
        if message_id:
            await self.bot.edit_message_text(text=text, chat_id=chat_id, message_id=message_id)
            return message_id
        else:
            msg = await self.bot.send_message(chat_id, text)
            return msg.message_id

    def format_caption(self, data: Dict[str, Any]) -> str:
        date_str = dt.datetime.utcnow().strftime("%Y-%m-%d")
        top_trends = data.get("top_trends", [])
        growth = data.get("growth_leaders", [])
        top_trends_str = "\n".join([f"• {t}" for t in top_trends[:3]]) or "—"
        growth_str = "\n".join([f"• {g}" for g in growth[:3]]) or "—"
        caption = self.caption_template.format(date=date_str, top_trends=top_trends_str, growth_leaders=growth_str)
        return caption

    async def create_report(self, user_id: int, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        settings = await get_user_settings(self.db, user_id)
        fmt = params.get("format") or settings.report_format or "pdf"
        data = await self.mcp.analyze_trends(
            {
                "days": params.get("days", settings.analysis_days),
                "sources": params.get(
                    "sources",
                    {"reddit": settings.sources.get("reddit", True),
                     "freelance": settings.sources.get("freelance", True),
                     "trends": settings.sources.get("trends", True)}
                ),
                "include_charts": params.get("include_charts", settings.include_charts),
                "language": params.get("language", settings.language),
            }
        )
        # Try to let MCP generate the file
        target_path = await self.mcp.generate_report(data, fmt)
        if not target_path:
            # Fallback: generate simple file locally
            filename = f"report_{user_id}_{int(dt.datetime.utcnow().timestamp())}.{fmt if fmt != 'excel' else 'xlsx'}"
            target_path = os.path.join(self.storage_path, filename)
            if fmt == "html":
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write("<html><body><h1>IT Trends Report</h1><pre>" + json.dumps(data, ensure_ascii=False, indent=2) + "</pre></body></html>")
            else:
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write("IT Trends Report\n\n" + json.dumps(data, ensure_ascii=False, indent=2))
        await save_report(self.db, user_id=user_id, channel_id=None, file_path=target_path, fmt=fmt, data_json=data, status="completed")
        return target_path

    async def publish_to_channel(self, channel_id: str, report_path: str, caption: str):
        # Auto-detect by path extension
        if report_path.lower().endswith((".pdf", ".doc", ".docx", ".xlsx", ".xls", ".html", ".htm", ".txt")):
            await self.bot.send_document(chat_id=channel_id, document=open(report_path, "rb"), caption=caption)
        else:
            await self.bot.send_message(chat_id=channel_id, text=caption)
