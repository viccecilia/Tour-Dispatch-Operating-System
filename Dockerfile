FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WX_DISPATCH_HOST=0.0.0.0 \
    WX_DISPATCH_PORT=18765 \
    WX_DISPATCH_DEMO_MODE=true \
    WX_DISPATCH_RESET_DEMO_ON_START=true \
    WX_DISPATCH_DB=/app/runtime/wx_dispatch.sqlite3 \
    WX_DISPATCH_LOG_DIR=/app/runtime/logs \
    WX_DISPATCH_BACKUP_DIR=/app/runtime/backups

WORKDIR /app

COPY backend ./backend
COPY scripts ./scripts
COPY docs ./docs
COPY wx_dispatch_platform ./wx_dispatch_platform
COPY .env.example ./.env.example

RUN mkdir -p runtime/logs runtime/backups

EXPOSE 18765

CMD ["python", "backend/main.py"]
