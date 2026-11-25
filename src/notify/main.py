"""Сборка сервиса: SQL-репозиторий, реестр каналов, воркер, API.

Запуск: `uvicorn notify.main:create --factory --port 8000`. Схему БД создают миграции
(`alembic upgrade head`), приложение таблиц не создаёт. Реальный httpx-адаптер — практика 6,
пока webhook работает на `FakeSender`.
"""

import os

from fastapi import FastAPI


def create() -> FastAPI:
    """TODO(B): после влития работы A проверить, что сборка запускается.

    Импорты внутри функции, чтобы модуль импортировался и до того, как A влил `sql.py`/`worker.py`;
    когда оба влиты, перенесите импорты наверх.
    """
    from notify.api.app import create_app
    from notify.channels.http_sender import FakeSender
    from notify.channels.log import LogChannel
    from notify.channels.registry import Registry
    from notify.channels.webhook import WebhookChannel
    from notify.domain.dispatcher import Dispatcher
    from notify.storage.sql import SqlNotificationRepository, create_sqlite_engine
    from notify.worker import Worker

    url = os.environ.get("NOTIFY_DATABASE_URL", "sqlite:///notify.db")
    repo = SqlNotificationRepository(create_sqlite_engine(url))
    registry = Registry([LogChannel(), WebhookChannel(FakeSender([200]))])
    worker = Worker(
        repo,
        Dispatcher(registry),
        poll_interval=float(os.environ.get("WORKER_POLL_INTERVAL_SECONDS", "1")),
        concurrency=int(os.environ.get("WORKER_CONCURRENCY", "4")),
    )
    return create_app(repo, registry, background=worker)
