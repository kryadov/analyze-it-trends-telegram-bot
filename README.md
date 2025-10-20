# IT Trends Telegram Bot

An asynchronous Telegram bot built with aiogram 3 to analyze IT trends via an MCP server and automatically publish reports to a channel.

## Quick Start

1. Clone the repository and install dependencies (Python 3.13):

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Configure environment variables:

- Copy `.env.example` to `.env` and set the values
- TELEGRAM_BOT_TOKEN — bot token from @BotFather
- ADMIN_CHAT_ID — admin chat ID (for error notifications)

3. Adjust the `config.yaml` if needed:
- MCP server URL
- Database path (SQLite `./data/bot.db` by default)
- Scheduler and logging settings

4. Run:

```bash
python bot.py
```

The bot uses long polling. For production you can configure a webhook (see below).

## Create a Telegram bot with BotFather

- Open Telegram and start a chat with @BotFather
- Send /start
- Send /newbot and follow the prompts:
  - Bot name: any display name (can be changed later)
  - Username: must be unique and end with "bot" (e.g., it_trends_bot)
- BotFather will send you an HTTP API token — copy it and put it into your .env as:
  - TELEGRAM_BOT_TOKEN=YOUR_TOKEN
- Recommended BotFather settings (optional but useful):
  - /setuserpic — set the bot avatar
  - /setdescription — short description
  - /setabouttext — about text
  - /setcommands — register commands for better UX in clients. Example:
    start - Start the bot
    analyze - Analyze IT trends
    report - Alias for analyze
    set_channel - Set the publish channel
    get_channel - Show current channel
- Add the bot to your channel (to allow publishing):
  - Open the channel → Administrators → Add Admin → choose your bot
  - Grant at least "Post Messages" permission
  - In Telegram, run /set_channel in the bot chat and provide the channel @username or ID
- Get your admin chat ID (for ADMIN_CHAT_ID in .env):
  - Send a message to @userinfobot or @getidsbot and copy your ID, or
  - Temporarily add a handler to print chat.id (advanced)
- Security tips:
  - Keep the token secret. If compromised, go to @BotFather → /revoke to regenerate

## Commands

- /start — greeting, menu
- /analyze [--days N] [--format pdf|excel|html] — start the analysis
- /report — alias for /analyze
- /set_channel @username or id — set the channel for publishing
- /get_channel — show the current channel

Example:

```
/analyze --days 7 --format pdf
```

## MCP Server Connection

- The MCP server URL is set in `config.yaml` (mcp_server.url).
- If the MCP server is unavailable, stub data will be returned and a simple report file will be created locally.

## Scheduler

APScheduler (AsyncIOScheduler) is used. A basic skeleton is implemented; adding/managing jobs via commands will be added later.

## Database

- SQLAlchemy 2.0 + aiosqlite by default
- Tables: users, channels, schedules, reports, user_settings

## Logging

- Log rotation
- Separate error log `logs/errors.log`

## Deployment

### systemd (Linux)

Example unit file `/etc/systemd/system/it-trends-bot.service`:

```
[Unit]
Description=IT Trends Telegram Bot
After=network.target

[Service]
WorkingDirectory=/opt/it-trends-telegram-bot
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=/opt/it-trends-telegram-bot/.env
ExecStart=/opt/it-trends-telegram-bot/.venv/bin/python bot.py
Restart=always
User=bot

[Install]
WantedBy=multi-user.target
```

```
sudo systemctl daemon-reload
sudo systemctl enable it-trends-bot
sudo systemctl start it-trends-bot
```

### Docker

Dockerfile (simplified example):

```
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

Run:

```
docker build -t it-trends-bot .
docker run --env-file .env -v %cd%/data:/app/data -v %cd%/logs:/app/logs -v %cd%/reports:/app/reports it-trends-bot
```

### Webhook (alternative to polling)

Aiogram 3 supports webhooks, but this basic setup uses polling. To enable webhooks, you will need to configure an external URL and TLS/Reverse Proxy, and also adjust the startup in bot.py.

### DB Migrations

- Alembic is included in the dependencies. In the base version, migrations are not configured. You can initialize later: `alembic init migrations` and configure `sqlalchemy.url`.

## FAQ and Troubleshooting

- The bot does not publish to the channel — make sure you added the bot as a channel administrator with publishing rights.
- MCP is unavailable — stub data will be used; check the URL in the config and network connectivity.
- Startup error — make sure TELEGRAM_BOT_TOKEN is present in .env.

## Roadmap

- Add schedule management commands (/schedule, /schedule_list, etc.)
- Add a settings menu and handle inline buttons
- Expand ReportService and integration with MCP
- Add MCP health-check on a schedule and admin notifications
