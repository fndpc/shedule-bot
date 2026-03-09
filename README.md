# Schedule Telegram Bot

Бот автоматически отслеживает новое расписание на сайте колледжа, парсит PDF для фиксированной группы `81/2023` и рассылает обновление всем подписанным пользователям.

## Что делает проект

1. Раз в минуту открывает страницу:
   - `https://chehtk.gosuslugi.ru/grafik-zanyatiy/`
2. Ищет `<a>` с классом `gw-document-item__collapse-link`.
3. Берет ссылку на актуальный PDF (`/netcat_files/.../*.pdf`).
4. Если ссылка изменилась:
   - скачивает PDF,
   - извлекает расписание для группы `81/2023`,
   - отправляет сообщение всем пользователям с активной подпиской.

## Куда сохраняются файлы

- Скачанные PDF сохраняются в директорию:
  - `downloads/`
- Имя файла сохраняется как в URL, например:
  - `downloads/10.03.2026_vtornik.pdf`

## Где хранятся подписки

- Таблица `subscriptions` в SQLite.
- По умолчанию используется:
  - `db.sqlite` в корне проекта.
- Поля:
  - `chat_id` — Telegram chat id
  - `is_subscribed` — активна подписка или нет

## Переменные окружения

Создай `.env` в корне проекта:

```env
BOT_TOKEN=your_telegram_bot_token
# Необязательно, по умолчанию sqlite+aiosqlite:///db.sqlite
DATABASE_URL=sqlite+aiosqlite:///db.sqlite
# Необязательно
SQLALCHEMY_ECHO=false
```

## Локальный запуск

### Требования

- Python 3.12+
- Утилита `pdftotext` (из `poppler-utils`)

Ubuntu/Debian:

```bash
sudo apt-get update
sudo apt-get install -y poppler-utils
```

### Установка зависимостей

Через `uv`:

```bash
uv sync
```

Или через `pip`:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install aiogram python-dotenv sqlalchemy aiosqlite
```

### Старт бота

```bash
python -m bot.bot
```

## Docker

В проекте есть [Dockerfile](/home/fndpc/dev/schedule/Dockerfile).

### Сборка

```bash
docker build -t schedule-bot .
```

### Запуск

```bash
mkdir -p data downloads
docker run -d \
  --name schedule-bot \
  --restart unless-stopped \
  --env-file .env \
  -e DATABASE_URL=sqlite+aiosqlite:///app/data/db.sqlite \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/downloads:/app/downloads \
  schedule-bot
```

## Как пользоваться в Telegram

1. Отправить `/start`
2. Нажать `Подписаться ✅` — включить рассылку
3. Нажать `Текущее расписание 📅` или отправить `/schedule` — получить расписание сразу
4. Нажать `Отписаться ❎` — отключить рассылку

## Структура проекта

- [bot/bot.py](/home/fndpc/dev/schedule/bot/bot.py) — Telegram бот, хендлеры, фоновый watcher.
- [bot/keyboards.py](/home/fndpc/dev/schedule/bot/keyboards.py) — кнопки подписки/отписки.
- [parser/parser.py](/home/fndpc/dev/schedule/parser/parser.py) — загрузка ссылки, скачивание PDF, формат рассылки.
- [parser/convertor.py](/home/fndpc/dev/schedule/parser/convertor.py) — извлечение расписания из PDF по группе.
- [repository/user_repository.py](/home/fndpc/dev/schedule/repository/user_repository.py) — операции с подписками.
- [db/models.py](/home/fndpc/dev/schedule/db/models.py) — ORM модель `Subscription`.
- [db/session.py](/home/fndpc/dev/schedule/db/session.py) — engine/session/init_db.

## Важные настройки по умолчанию

- Группа для рассылки зашита в коде:
  - `TARGET_GROUP = "81/2023"` в [parser/parser.py](/home/fndpc/dev/schedule/parser/parser.py)
- Интервал проверки:
  - `CHECK_INTERVAL_SECONDS = 60` в [bot/bot.py](/home/fndpc/dev/schedule/bot/bot.py)

## Примечание по безопасности

Если токен бота когда-либо попал в логи/чат/репозиторий, его нужно перевыпустить через BotFather и заменить в `.env`.
