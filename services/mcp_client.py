import asyncio
import json
import logging
from typing import Any, Dict, Optional

import aiohttp


logger = logging.getLogger(__name__)


class MCPClient:
    def __init__(self, server_url: str, timeout: int = 300, retry_attempts: int = 3, retry_delay: int = 5):
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self._session: Optional[aiohttp.ClientSession] = None

    async def connect(self) -> None:
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(total=self.timeout)
            self._session = aiohttp.ClientSession(timeout=timeout)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, path: str, json_payload: Optional[Dict[str, Any]] = None) -> Any:
        await self.connect()
        attempt = 0
        last_exc: Optional[Exception] = None
        while attempt < self.retry_attempts:
            try:
                assert self._session is not None
                url = f"{self.server_url}{path}"
                async with self._session.request(method, url, json=json_payload) as resp:
                    resp.raise_for_status()
                    content_type = resp.headers.get("Content-Type", "")
                    if "application/json" in content_type:
                        return await resp.json()
                    return await resp.text()
            except Exception as e:
                last_exc = e
                attempt += 1
                logger.warning(
                    "MCP request failed (attempt %d/%d): %s %s; payload_keys=%s; error=%s",
                    attempt,
                    self.retry_attempts,
                    method,
                    url,
                    list(json_payload.keys()) if isinstance(json_payload, dict) else None,
                    repr(e),
                )
                if attempt >= self.retry_attempts:
                    break
                await asyncio.sleep(self.retry_delay * attempt)  # simple exponential backoff
        if last_exc:
            logger.error(
                "MCP request failed after %d attempts: %s %s",
                self.retry_attempts,
                method,
                f"{self.server_url}{path}",
            )
            raise last_exc

    async def health_check(self) -> bool:
        try:
            data = await self._request("GET", "/health")
            if isinstance(data, dict):
                return data.get("status") == "ok"
            return True
        except Exception:
            logger.warning("MCP health check failed", exc_info=True)
            return False

    async def analyze_trends(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Call analyze_reddit + analyze_freelance + search_trends via MCP server. Fallback to stub data."""
        try:
            result = await self._request("POST", "/analyze", json_payload=params)
            if isinstance(result, dict):
                return result
        except Exception:
            logger.exception("MCP analyze_trends failed; params=%s", params)
        # Fallback stub
        return {
            "date": params.get("date") or "today",
            "top_trends": ["AI Agents", "Rust", "Kotlin Multiplatform"],
            "growth_leaders": ["LangChain", "WebGPU", "Bun"],
            "sources": params.get("sources", {"reddit": True, "freelance": True, "trends": True}),
            "summary": "Stub analysis due to MCP server unavailability.",
        }

    async def generate_report(self, data: Dict[str, Any], fmt: str) -> str:
        """Ask MCP to generate report and return path, fallback to local stub path signal to caller to save."""
        payload = {"data": data, "format": fmt}
        try:
            result = await self._request("POST", "/generate_report", json_payload=payload)
            if isinstance(result, dict) and "file_path" in result:
                return result["file_path"]
        except Exception:
            logger.exception("MCP generate_report failed; fmt=%s", fmt)
        # Fallback: caller will create the file locally using returned hint
        return ""

    async def get_historical_data(self, technology: str) -> Dict[str, Any]:
        try:
            result = await self._request("GET", f"/historical?technology={technology}")
            if isinstance(result, dict):
                return result
        except Exception:
            logger.exception("MCP get_historical_data failed; technology=%s", technology)
        return {"technology": technology, "history": []}
