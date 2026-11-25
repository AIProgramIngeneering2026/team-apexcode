"""Единый формат ошибок: `{"error": {"code", "message", "details", "correlation_id"}}`.

Правила (практика 4, п. 3; docs/api/openapi.yaml):
- статус по смыслу, `200` с ошибкой внутри нет нигде;
- в ответе нет трасс, путей к файлам, SQL и значений из запроса (Н-«скрытое»: токен в `recipient`
  не должен вернуться эхом, в том числе в ошибках валидации FastAPI/Pydantic);
- `details` всегда объект.
"""

from typing import Any

from fastapi import FastAPI

# Код ошибки → HTTP-статус (openapi.yaml, схема Error). Коды ядра приходят из `NotifyError.code`.
STATUS_BY_CODE: dict[str, int] = {
    "bad_request": 400,
    "missing_idempotency_key": 400,
    "not_found": 404,
    "method_not_allowed": 405,
    "idempotency_key_conflict": 409,
    "invalid_transition": 409,
    "payload_too_large": 413,
    "unknown_channel": 422,
    "invalid_params": 422,
    "internal_error": 500,
}


class ApiError(Exception):
    """Ошибка уровня API (формат запроса, заголовки). Ошибки ядра переводит handler ниже."""

    def __init__(
        self, code: str, message: str, details: dict[str, Any] | None = None
    ) -> None:
        self.code = code
        self.status = STATUS_BY_CODE[code]
        self.message = message
        self.details = details or {}
        super().__init__(message)


def error_body(
    code: str, message: str, details: dict[str, Any], correlation_id: str
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "details": details,
            "correlation_id": correlation_id,
        }
    }


def register_error_handlers(app: FastAPI) -> None:
    """TODO(B): зарегистрировать обработчики, все отвечают через `error_body`:

    - `ApiError` → его статус и код;
    - ядро: `UnknownChannel` → 422, details {channel, available}; `InvalidParams` → 422,
      details {fields: [{field, problem}]}; `InvalidTransition` → 409, details {notification_id,
      current_status, requested_status}; `NotificationNotFound` → 404, details {notification_id};
      `IdempotencyKeyConflict` → 409, details {header: "Idempotency-Key"};
    - `RequestValidationError` (FastAPI: `limit`, `status`, `offset` в query) → 422 invalid_params,
      fields из `exc.errors()`: берите ТОЛЬКО `loc` (имя поля) и короткий `problem`, НЕ `input` и
      не `msg`, если в нём может оказаться значение;
    - `StarletteHTTPException`: 404 → not_found («Resource not found»), 405 → method_not_allowed,
      остальные — по статусу; `id` неверного формата даёт тот же 404, что и несуществующий;
    - `Exception` → 500 internal_error с общим текстом; стек пишется только в лог.

    Важно: ответ на `Exception` формирует `ServerErrorMiddleware`, он снаружи ваших middleware,
    поэтому заголовок `X-Correlation-ID` для 500 нужно выставить в самом обработчике.
    """
    raise NotImplementedError
