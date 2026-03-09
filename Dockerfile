FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*

RUN python -m pip install --no-cache-dir --upgrade pip
RUN python -m pip install --no-cache-dir \
    "aiogram>=3.26.0" \
    "python-dotenv>=1.0.1" \
    "sqlalchemy>=2.0.48" \
    "aiosqlite>=0.21.0"

COPY bot ./bot
COPY db ./db
COPY parser ./parser
COPY repository ./repository
COPY config.py ./config.py

RUN mkdir -p /app/downloads

CMD ["python", "-m", "bot.bot"]
