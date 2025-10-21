import asyncio
import datetime as dt
import json
import os
from typing import Dict, Any, Optional, Tuple

from aiogram import Bot

from fastmcp.client import Client as FastMCPClient
from database.repository import Database, get_active_channel, get_user_settings, save_report


class ReportService:
    def __init__(self, bot: Bot, db: Database, mcp: FastMCPClient, storage_path: str, caption_template: str):
        self.bot = bot
        self.db = db
        self.mcp = mcp
        self.storage_path = storage_path
        self.caption_template = caption_template
        os.makedirs(self.storage_path, exist_ok=True)

    def _unwrap_tool_result(self, result: Any) -> Any:
        """Normalize fastmcp Client.call_tool return into a Python type we can use.

        - If it's the CallToolResult dataclass, prefer .data, else .structured_content,
          else try to extract text from .content.
        - If it's already a primitive/dict/str, return as-is.
        """
        # Already a basic type
        if isinstance(result, (dict, str, list)):
            return result

        # Duck-typing for CallToolResult
        if hasattr(result, "data") or hasattr(result, "structured_content") or hasattr(result, "content"):
            data = getattr(result, "data", None)
            if data is not None:
                # Convert common structured objects to dict
                try:
                    if isinstance(data, dict):
                        return data
                    if hasattr(data, "model_dump"):
                        return data.model_dump()  # pydantic v2
                    if hasattr(data, "dict"):
                        return data.dict()  # pydantic v1
                    if hasattr(data, "__dict__"):
                        return dict(data.__dict__)
                except Exception:
                    pass
                return data

            structured = getattr(result, "structured_content", None)
            if structured is not None:
                return structured

            # Fallback to textual content
            content = getattr(result, "content", None)
            if isinstance(content, list) and content:
                # Attempt to join text blocks
                texts: list[str] = []
                for block in content:
                    text = getattr(block, "text", None)
                    if isinstance(text, str):
                        texts.append(text)
                if texts:
                    combined = "\n".join(texts)
                    try:
                        parsed = json.loads(combined)
                        return parsed
                    except Exception:
                        return combined

        return result

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
        date_str = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
        top_trends = data.get("top_trends", [])
        growth = data.get("growth_leaders", [])
        top_trends_str = "\n".join([f"• {t}" for t in top_trends[:3]]) or "—"
        growth_str = "\n".join([f"• {g}" for g in growth[:3]]) or "—"
        caption = self.caption_template.format(date=date_str, top_trends=top_trends_str, growth_leaders=growth_str)
        return caption

    async def _call_tool_with_retries(self, tool_name: str, args: Dict[str, Any]) -> Any:
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt < 3:
            try:
                return await self.mcp.call_tool(tool_name, args)
            except Exception as e:
                last_exc = e
                attempt += 1
                await asyncio.sleep(2 * attempt)
        if last_exc:
            raise last_exc

    async def _analyze_trends(self, params: Dict[str, Any]) -> Dict[str, Any]:
        candidate_tools = [
            "analyze_trends",
            "analyze",
            "trends_analyze",
        ]
        for name in candidate_tools:
            try:
                result = await self._call_tool_with_retries(name, params)
                unwrapped = self._unwrap_tool_result(result)
                if isinstance(unwrapped, dict):
                    return unwrapped
                if isinstance(unwrapped, str):
                    try:
                        parsed = json.loads(unwrapped)
                        if isinstance(parsed, dict):
                            return parsed
                    except Exception:
                        pass
            except Exception:
                continue
        # Fallback stub
        return {
            "date": params.get("date") or "today",
            "top_trends": ["AI Agents", "Rust", "Kotlin Multiplatform"],
            "growth_leaders": ["LangChain", "WebGPU", "Bun"],
            "sources": params.get("sources", {"reddit": True, "freelance": True, "trends": True}),
            "summary": "Stub analysis due to MCP server unavailability.",
        }

    async def _generate_report(self, data: Dict[str, Any], fmt: str) -> str:
        payload = {"data": data, "format": fmt}
        candidate_tools = [
            "generate_report",
            "report_generate",
            "create_report",
        ]
        for name in candidate_tools:
            try:
                result = await self._call_tool_with_retries(name, payload)
                unwrapped = self._unwrap_tool_result(result)
                if isinstance(unwrapped, dict):
                    # Accept both 'file_path' and 'path' keys from the MCP server
                    for key in ("file_path", "path", "filepath"):
                        if key in unwrapped and unwrapped[key]:
                            return str(unwrapped[key])
                if isinstance(unwrapped, str):
                    # If server returns plain path as text
                    if os.path.exists(unwrapped):
                        return unwrapped
                    try:
                        parsed = json.loads(unwrapped)
                        if isinstance(parsed, dict) and "file_path" in parsed:
                            return str(parsed["file_path"]) 
                    except Exception:
                        pass
            except Exception:
                continue
        return ""

    async def create_report(self, user_id: int, params: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
        settings = await get_user_settings(self.db, user_id)
        fmt = params.get("format") or settings.report_format or "pdf"
        data = await self._analyze_trends(
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
        target_path = await self._generate_report(data, fmt)
        if not target_path:
            # Fallback: generate simple file locally
            filename = f"report_{user_id}_{int(dt.datetime.now(dt.timezone.utc).timestamp())}.{fmt if fmt != 'excel' else 'xlsx'}"
            target_path = os.path.join(self.storage_path, filename)
            if fmt == "html":
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write("<html><body><h1>IT Trends Report</h1><pre>" + json.dumps(data, ensure_ascii=False, indent=2) + "</pre></body></html>")
            else:
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write("IT Trends Report\n\n" + json.dumps(data, ensure_ascii=False, indent=2))
        await save_report(self.db, user_id=user_id, channel_id=None, file_path=target_path, fmt=fmt, data_json=data, status="completed")
        return target_path, data

    async def publish_to_channel(self, channel_id: str, report_path: str, caption: str):
        # Auto-detect by path extension
        if report_path.lower().endswith((".pdf", ".doc", ".docx", ".xlsx", ".xls", ".html", ".htm", ".txt")):
            await self.bot.send_document(chat_id=channel_id, document=open(report_path, "rb"), caption=caption)
        else:
            await self.bot.send_message(chat_id=channel_id, text=caption)
