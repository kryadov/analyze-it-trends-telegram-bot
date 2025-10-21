import asyncio
import datetime as dt
import json
import os
import logging
from typing import Dict, Any, Optional, Tuple

from aiogram import Bot
from aiogram.types import FSInputFile

from fastmcp.client import Client as FastMCPClient
from database.repository import Database, get_active_channel, get_user_settings, save_report


class ReportService:
    def __init__(self, bot: Bot, db: Database, mcp: FastMCPClient, storage_path: str, caption_template: str):
        self.bot = bot
        self.db = db
        self.mcp = mcp
        self.storage_path = storage_path
        self.caption_template = caption_template
        self.logger = logging.getLogger(__name__)
        os.makedirs(self.storage_path, exist_ok=True)
        self.logger.info("ReportService initialized. storage_path=%s", os.path.abspath(self.storage_path))

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
                    if hasattr(data, "__dict"):
                        return dict(data.__dict__)
                except Exception as e:
                    self.logger.debug("_unwrap_tool_result: failed to normalize data field: %s", e, exc_info=True)
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
        redacted_args = {k: ('...' if k in {'token', 'api_key'} else v) for k, v in (args or {}).items()}
        while attempt < 3:
            try:
                self.logger.debug("Calling MCP tool '%s' attempt=%d args=%s", tool_name, attempt + 1, redacted_args)
                result = await self.mcp.call_tool(tool_name, args)
                self.logger.debug("MCP tool '%s' succeeded on attempt=%d", tool_name, attempt + 1)
                return result
            except Exception as e:
                last_exc = e
                attempt += 1
                self.logger.warning("MCP tool '%s' failed on attempt=%d: %s", tool_name, attempt, e, exc_info=True)
                await asyncio.sleep(2 * attempt)
        if last_exc:
            self.logger.error("MCP tool '%s' failed after %d attempts: %s", tool_name, attempt, last_exc)
            raise last_exc

    async def _analyze_trends(self, params: Dict[str, Any]) -> Dict[str, Any]:
        candidate_tools = [
            "analyze_trends",
            "analyze",
            "trends_analyze",
        ]
        for name in candidate_tools:
            try:
                self.logger.info("Analyzing trends via MCP tool='%s' params=%s", name, {k: params.get(k) for k in ('days','include_charts','language')})
                result = await self._call_tool_with_retries(name, params)
                unwrapped = self._unwrap_tool_result(result)
                if isinstance(unwrapped, dict):
                    self.logger.info("Analyze result received as dict from tool='%s'", name)
                    return unwrapped
                if isinstance(unwrapped, str):
                    try:
                        parsed = json.loads(unwrapped)
                        if isinstance(parsed, dict):
                            self.logger.info("Analyze result parsed from JSON string from tool='%s'", name)
                            return parsed
                    except Exception as e:
                        self.logger.debug("Analyze result from tool='%s' is not JSON: %s", name, e)
                        pass
            except Exception as e:
                self.logger.warning("Analyze via tool='%s' failed: %s", name, e, exc_info=True)
                continue
        # Fallback stub
        self.logger.warning("Using stub analysis due to MCP server unavailability or tool failure")
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
                self.logger.info("Generating report via MCP tool='%s' format=%s", name, fmt)
                result = await self._call_tool_with_retries(name, payload)
                unwrapped = self._unwrap_tool_result(result)
                candidate_path: Optional[str] = None
                if isinstance(unwrapped, dict):
                    # Accept both 'file_path' and 'path' keys from the MCP server
                    for key in ("file_path", "path", "filepath"):
                        if key in unwrapped and unwrapped[key]:
                            candidate_path = str(unwrapped[key])
                            break
                elif isinstance(unwrapped, str):
                    # If server returns plain path as text
                    if os.path.exists(unwrapped):
                        candidate_path = unwrapped
                    else:
                        try:
                            parsed = json.loads(unwrapped)
                            if isinstance(parsed, dict):
                                for key in ("file_path", "path", "filepath"):
                                    if key in parsed and parsed[key]:
                                        candidate_path = str(parsed[key])
                                        break
                        except Exception as e:
                            self.logger.debug("MCP output from tool='%s' is not JSON/path: %s", name, e)
                if candidate_path:
                    try:
                        size = os.path.getsize(candidate_path)
                        if size > 0:
                            self.logger.info("MCP generated file accepted: path=%s size=%d", candidate_path, size)
                            return candidate_path
                        else:
                            self.logger.warning("MCP generated file is empty (size=0), ignoring. path=%s", candidate_path)
                    except Exception as e:
                        self.logger.warning("Failed to stat MCP-generated path: %s error=%s", candidate_path, e, exc_info=True)
            except Exception as e:
                self.logger.warning("Generate via tool='%s' failed: %s", name, e, exc_info=True)
                continue
        self.logger.warning("MCP report generation failed; will use local fallback. format=%s", fmt)
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
        self.logger.info("Creating report for user_id=%s with params=%s", user_id, params)
        target_path = await self._generate_report(data, fmt)
        if not target_path:
            # Fallback: generate simple file locally
            requested_fmt = (fmt or "pdf").lower()
            fallback_ext = "html" if requested_fmt == "html" else "txt"
            if requested_fmt in {"excel", "xlsx", "xls", "pdf", "doc", "docx"} and fallback_ext != requested_fmt:
                self.logger.warning("Downgrading fallback format from %s to %s due to missing generator", requested_fmt, fallback_ext)
            filename = f"report_{user_id}_{int(dt.datetime.now(dt.timezone.utc).timestamp())}.{fallback_ext}"
            target_path = os.path.join(self.storage_path, filename)
            try:
                if fallback_ext == "html":
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write("<html><body><h1>IT Trends Report</h1><pre>" + json.dumps(data, ensure_ascii=False, indent=2) + "</pre></body></html>")
                else:
                    with open(target_path, "w", encoding="utf-8") as f:
                        f.write("IT Trends Report\n\n" + json.dumps(data, ensure_ascii=False, indent=2))
                size = os.path.getsize(target_path)
                self.logger.info("Local fallback report created: path=%s size=%d", target_path, size)
            except Exception as e:
                self.logger.exception("Failed to create local fallback report at %s: %s", target_path, e)
                raise
            # Override fmt to actual file type we created for record accuracy
            fmt = fallback_ext
        try:
            await save_report(self.db, user_id=user_id, channel_id=None, file_path=target_path, fmt=fmt, data_json=data, status="completed")
            self.logger.info("Report metadata saved to DB: user_id=%s path=%s fmt=%s", user_id, target_path, fmt)
        except Exception as e:
            self.logger.exception("Failed to save report metadata to DB for user_id=%s: %s", user_id, e)
            raise
        return target_path, data

    async def publish_to_channel(self, channel_id: str, report_path: str, caption: str):
        # Auto-detect by path extension
        try:
            size = os.path.getsize(report_path)
        except Exception:
            size = -1
        self.logger.info("Publishing report to channel_id=%s path=%s size=%s", channel_id, report_path, size)
        if report_path.lower().endswith((".pdf", ".doc", ".docx", ".xlsx", ".xls", ".html", ".htm", ".txt")):
            try:
                input_file = FSInputFile(report_path)
                await self.bot.send_document(chat_id=channel_id, document=input_file, caption=caption)
                self.logger.info("Report document sent to channel_id=%s", channel_id)
            except Exception as e:
                self.logger.exception("Failed to send document to channel_id=%s: %s", channel_id, e)
                raise
        else:
            await self.bot.send_message(chat_id=channel_id, text=caption)
            self.logger.info("Text message sent to channel_id=%s (no document)", channel_id)
