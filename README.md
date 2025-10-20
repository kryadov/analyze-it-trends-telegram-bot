# IT Trends Telegram Bot

Асинхронный Telegram-бот на aiogram 3 для анализа IT-трендов через MCP-сервер и автоматической публикации отчетов в канал.

## Быстрый старт

1. Клонируйте репозиторий и установите зависимости:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

2. Настройте переменные окружения:

- Скопируйте `.env.example` в `.env` и укажите значения
- TELEGRAM_BOT_TOKEN — токен бота от @BotFather
- ADMIN_CHAT_ID — ID чата админа (для уведомлений об ошибках)

3. Настройте конфиг `config.yaml` при необходимости:
- URL MCP-сервера
- Путь к БД (по умолчанию SQLite `./data/bot.db`)
- Настройки планировщика и логирования

4. Запуск:

```bash
python bot.py
```

Бот использует long polling. Для продакшена можно настроить webhook (см. ниже).

## Команды

- /start — приветствие, меню
- /analyze [--days N] [--format pdf|excel|html] — запустить анализ
- /report — алиас команды /analyze
- /set_channel <@username|id> — указать канал для публикации
- /get_channel — показать текущий канал

Пример:

```
/analyze --days 7 --format pdf
```

## Подключение к MCP-серверу

- URL MCP-сервера задается в `config.yaml` (mcp_server.url).
- При недоступности MCP возвращаются заглушки данных и создается простой файл отчета локально.

## Планировщик

Используется APScheduler (AsyncIOScheduler). Базовый скелет реализован, добавление/управление заданиями через команды будет добавлено позже.

## База данных

- SQLAlchemy 2.0 + aiosqlite по умолчанию
- Таблицы: users, channels, schedules, reports, user_settings

## Логирование

- Ротация логов
- Отдельный лог для ошибок `logs/errors.log`

## Развертывание

### systemd (Linux)

Пример unit-файла `/etc/systemd/system/it-trends-bot.service`:

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

Dockerfile (упрощенный, пример):

```
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

Запуск:

```
docker build -t it-trends-bot .
docker run --env-file .env -v %cd%/data:/app/data -v %cd%/logs:/app/logs -v %cd%/reports:/app/reports it-trends-bot
```

### Webhook (альтернатива polling)

Aiogram 3 поддерживает вебхуки, но в данном базовом варианте используется polling. Для включения вебхуков потребуется настроить внешний URL и TLS/Reverse Proxy, а также изменить запуск в bot.py.

### Миграции БД

- Alembic включен в зависимости. В базовой версии миграции не настроены. Можно инициализировать позднее: `alembic init migrations` и настроить `sqlalchemy.url`.

## FAQ и Troubleshooting

- Бот не публикует в канал — убедитесь, что добавили бота администратором канала с правами публикации.
- MCP недоступен — данные будут взяты из заглушек, проверьте URL в конфиге и сетевую доступность.
- Ошибка запуска — проверьте наличие TELEGRAM_BOT_TOKEN в .env.

## Дальнейший план

- Добавить команды управления расписаниями (/schedule, /schedule_list и пр.)
- Добавить меню настроек и обработку inline-кнопок
- Расширить ReportService и интеграцию с MCP
- Добавить health-check MCP по расписанию и уведомления админам
