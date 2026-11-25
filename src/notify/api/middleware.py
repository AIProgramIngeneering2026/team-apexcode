"""ASGI-middleware: ограничение размера тела и `X-Correlation-ID`.

Пишите чистые ASGI-классы (`__call__(scope, receive, send)`), а не `BaseHTTPMiddleware`:
тело нужно проверять до разбора JSON и без чтения всего потока в память.
"""

from starlette.types import ASGIApp, Receive, Scope, Send

MAX_BODY_BYTES = 64 * 1024  # 64 КиБ (S5, К7): рассчитано на 4096 символов в формате \uXXXX


class CorrelationIdMiddleware:
    """TODO(B): взять `X-Correlation-ID` из запроса (≤128 символов, видимые ASCII) или
    сгенерировать (uuid4 hex); положить в `scope["state"]["correlation_id"]`; добавить в заголовки
    КАЖДОГО ответа (обернуть `send` на событии `http.response.start`). Некорректное значение
    из запроса не принимать, а заменять сгенерированным."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise NotImplementedError


class BodySizeLimitMiddleware:
    """TODO(B): 413 payload_too_large (в едином формате) без разбора тела, если
    `Content-Length` > `max_bytes`, либо если поток тела (chunked, без Content-Length) превысил
    лимит. Ответ формируйте через `error_body`; детали `{"max_bytes": 65536}`."""

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        raise NotImplementedError
