"""Эндпоинты. Тонкий слой: валидация формы запроса, вызов порта, сериализация.

Правил переходов, SQL и отправки здесь нет: `InvalidTransition` приходит из ядра/репозитория
и превращается в 409 обработчиком из errors.py.
"""

from fastapi import APIRouter

from notify.channels.registry import Registry
from notify.domain.repository import NotificationRepository


def build_router(repo: NotificationRepository, registry: Registry) -> APIRouter:
    """TODO(B): собрать роутер. Эндпоинты и их порядок проверок — по openapi.yaml.

    POST /notifications (201 | 200 | 400 | 409 | 413 | 422), порядок:
      1. размер тела — уже проверил BodySizeLimitMiddleware;
      2. тело: `await request.body()` → `json.loads`, не JSON или не объект → 400 bad_request;
      3. `validate_key(request.headers.get("Idempotency-Key"))`;
      4. форма: `NotificationCreate.model_validate(...)`; ошибка → 422 invalid_params с полями
         (отсутствует, null, не строка, лишнее поле); значения в ответ НЕ возвращать;
      5. `registry.get(channel)` (UnknownChannel → 422), затем
         `channel.ensure_valid(recipient, message)` (InvalidParams → 422);
      6. `Notification.create(...)`, `request_hash(...)`, `repo.create(...)` через
         `run_in_threadpool` (repo синхронный, ADR-0004): created → 201, иначе 200.
    GET /notifications/{id}: `repo.get`; None → NotificationNotFound; ответ — уведомление +
        `attempts` (номер = позиция + 1). Любой неверный `id` → тот же 404.
    GET /notifications?status=&limit=&offset=: Query(ge/le по openapi), `status` — enum;
        ответ {items, total}; значения вне диапазона → 422 invalid_params (не 200).
    POST /notifications/{id}/cancel: `repo.cancel` (NotificationNotFound → 404,
        InvalidTransition → 409); эндпоинтов start/deliver/fail/retry НЕ добавлять (Н44).
    GET /channels: из `registry.list_channels()` (name, recipient_format, max_message_length).
    GET /health: 200 {"status": "ok", "checks": {"database": "ok"}}, при `repo.ping()` False —
        503 {"status": "unavailable", "checks": {"database": "down"}} (не формат Error).

    Синхронные эндпоинты объявляйте обычными `def` (FastAPI выполнит их в пуле потоков);
    `async def` нужен только для POST, где читается тело.
    """
    raise NotImplementedError
