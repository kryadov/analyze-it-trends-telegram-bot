import asyncio
import os
import re
import sys
import logging
from typing import Any, Dict

import yaml
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

from utils.logger import setup_logger
from database.repository import Database
from services.mcp_client import MCPClient
from services.report_service import ReportService
from services.scheduler import TrendsScheduler
from services import container
from handlers import commands as commands_handlers
from handlers import callbacks as callbacks_handlers
from handlers import errors as errors_handlers


def expand_env_vars(obj):
    if isinstance(obj, dict):
        return {k: expand_env_vars(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [expand_env_vars(v) for v in obj]
    if isinstance(obj, str):
        # replace ${VAR} or "${VAR}" with env
        pattern = re.compile(r"\$\{([^}]+)\}")
        def repl(m):
            return os.getenv(m.group(1), m.group(0))
        return pattern.sub(repl, obj)
    return obj


async def main():
    load_dotenv()

    # Load config
    config_path = os.path.join(os.path.dirname(__file__), 'config.yaml')
    with open(config_path, 'r', encoding='utf-8') as f:
        raw_cfg = yaml.safe_load(f)
    cfg = expand_env_vars(raw_cfg)

    # Setup logger
    log_cfg = cfg.get('logging', {})
    setup_logger(level=log_cfg.get('level', 'INFO'), log_file=log_cfg.get('file', './logs/bot.log'), max_size_mb=int(log_cfg.get('max_size_mb', 10)), backup_count=int(log_cfg.get('backup_count', 5)))
    logger = logging.getLogger(__name__)

    # Prepare DB
    db_cfg = cfg.get('database', {})
    if db_cfg.get('type') == 'sqlite':
        db_path = db_cfg.get('path', './data/bot.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        dsn = f"sqlite+aiosqlite:///{os.path.abspath(db_path)}"
    else:
        dsn = os.getenv('DATABASE_URL') or db_cfg.get('connection_string')
        if not dsn:
            raise RuntimeError('DATABASE_URL is not set for PostgreSQL configuration')
    db = Database(dsn)
    await db.init_models()

    # Bot
    bot_token = cfg.get('bot', {}).get('token')
    if not bot_token or bot_token.startswith("$"):
        raise RuntimeError('TELEGRAM_BOT_TOKEN is not set')
    bot = Bot(token=bot_token, parse_mode='HTML')
    dp = Dispatcher()

    # MCP client
    mcp_cfg = cfg.get('mcp_server', {})
    mcp = MCPClient(server_url=mcp_cfg.get('url', 'http://localhost:8080'), timeout=int(mcp_cfg.get('timeout', 300)), retry_attempts=int(mcp_cfg.get('retry_attempts', 3)), retry_delay=int(mcp_cfg.get('retry_delay', 5)))
    await mcp.connect()
    healthy = await mcp.health_check()
    if healthy:
        logging.info('MCP server is healthy')
    else:
        logging.warning('MCP server is not reachable; will use fallback stubs')

    # Report service
    reports_cfg = cfg.get('reports', {})
    report_service = ReportService(
        bot=bot,
        db=db,
        mcp=mcp,
        storage_path=reports_cfg.get('storage_path', './reports'),
        caption_template=reports_cfg.get('caption_template', 'IT Trends Report - {date}')
    )

    # Scheduler
    scheduler_cfg = cfg.get('scheduler', {})
    trends_scheduler = TrendsScheduler(timezone=scheduler_cfg.get('timezone', 'UTC'))
    trends_scheduler.start()

    # Container
    container.bot = bot
    container.db = db
    container.mcp = mcp
    container.report_service = report_service
    container.config = cfg
    container.scheduler = trends_scheduler

    # Routers
    dp.include_router(commands_handlers.router)
    dp.include_router(callbacks_handlers.router)
    dp.include_router(errors_handlers.router)

    # Run polling
    try:
        await dp.start_polling(bot)
    finally:
        logging.info('Shutting down...')
        try:
            trends_scheduler.shutdown()
        except Exception:
            pass
        await mcp.close()
        await db.dispose()
        await bot.session.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print('Bot stopped')
