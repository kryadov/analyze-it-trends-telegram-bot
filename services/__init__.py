from typing import Optional

from aiogram import Bot

from .mcp_client import MCPClient
from ..database.repository import Database


class Container:
    bot: Optional[Bot] = None
    db: Optional[Database] = None
    mcp: Optional[MCPClient] = None
    report_service: Optional[object] = None
    config: Optional[dict] = None
    scheduler: Optional[object] = None


container = Container()
