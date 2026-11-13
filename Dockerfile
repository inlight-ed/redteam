# ============================================================================
# Multi-stage Dockerfile для Red Team Swarm
# Этап 1: Сборка зависимостей
# Этап 2: Финальный образ с минимальным размером
# ============================================================================

FROM python:3.11-slim-bookworm AS builder

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Создаем виртуальное окружение
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Устанавливаем Python зависимости
COPY twitch-redteam/requirements.txt /tmp/requirements.txt 2>/dev/null || echo "camoufox\nwebsockets\npandas\nscikit-learn\nnumpy\nplaywright" > /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ============================================================================
# Этап 2: Финальный образ
# ============================================================================
FROM python:3.11-slim-bookworm

# Метаданные
LABEL maintainer="redteam-project"
LABEL description="Red Team Swarm - Camoufox + Twitch IRC + Humanizer"

# Систменные зависимости для Camoufox (Firefox)
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Базовые утилиты
    curl \
    wget \
    ca-certificates \
    # Зависимости Firefox/Camoufox
    libgtk-3-0 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libnss3 \
    libnspr4 \
    libxshmfence1 \
    fonts-liberation \
    xdg-utils \
    && rm -rf /var/lib/apt/lists/*

# Копируем виртуальное окружение из builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Устанавливаем Playwright и скачиваем браузеры
RUN playwright install firefox && \
    playwright install-deps firefox

# Скачиваем Camoufox браузер
RUN python -m camoufox fetch

# Создаем рабочую директорию
WORKDIR /app

# Копируем код проекта
COPY twitch-redteam/ ./twitch-redteam/
COPY twitch-antifraud/ ./twitch-antifraud/

# Устанавливаем права
RUN chmod -R 755 /app

# Создаем директорию для логов
RUN mkdir -p /app/logs && chmod 777 /app/logs

# Переменные окружения
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
ENV HEADLESS=true

# Точка входа
ENTRYPOINT ["python"]
CMD ["twitch-redteam/run_swarm_ultimate.py"]
