"""Фабрика приложения. Все зависимости внедряются снаружи (ADR-0004, п. 8)."""

from typing import Protocol

from fastapi import FastAPI

from notify.channels.registry import Registry
from notify.domain.repository import NotificationRepository


class Lifecycle(Protocol):
    """Фоновый сервис с запуском и остановкой (его реализует `notify.worker.Worker`)."""

    def start(self) -> None: ...

    def stop(self) -> None: ...


def create_app(
    repo: NotificationRepository,
    registry: Registry,
    *,
    background: Lifecycle | None = None,
) -> FastAPI:
    """TODO(B): собрать `FastAPI(title="Notify API", version=...)`.

    - версия совпадает с `info.version` из docs/api/openapi.yaml (0.3.0);
    - middleware: `CorrelationIdMiddleware` снаружи, `BodySizeLimitMiddleware` внутри;
    - `register_error_handlers(app)`;
    - `app.include_router(build_router(repo, registry))`;
    - `background` (воркер): `start()` при старте, `stop()` при завершении (lifespan).
      Тесты создают приложение без него (`background=None`) и вызывают `Worker.run_once()` сами.
    """
    raise NotImplementedError
