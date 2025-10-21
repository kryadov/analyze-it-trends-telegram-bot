from typing import Optional

from aiogram import Bot

from fastmcp.client import Client as FastMCPClient
from database.repository import Database


class Container:
    bot: Optional[Bot] = None
    db: Optional[Database] = None
    mcp: Optional[FastMCPClient] = None
    report_service: Optional[object] = None
    config: Optional[dict] = None
    scheduler: Optional[object] = None


container = Container()
