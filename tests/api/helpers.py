"""Помощники тестов API."""

from typing import Any

from fastapi.testclient import TestClient

KEY = "3f0c9a52-6f5e-4c53-9d3c-0a8f1b2c7d11"


def todo() -> None:
    """Тело ещё не написанного теста: после снятия `skip` тест падает, а не «проходит»."""
    raise NotImplementedError("TODO(B): написать тест по описанию в docstring")


def valid_body(**changes: Any) -> dict[str, Any]:
    body = {"channel": "webhook", "recipient": "https://example.org/hook", "message": "Готово"}
    body.update(changes)
    return body


def post_notification(client: TestClient, body: Any = None, key: str | None = KEY, **kwargs: Any):
    """POST /notifications; `key=None` — без заголовка. Остальное уходит в `client.post`."""
    headers = dict(kwargs.pop("headers", {}))
    if key is not None:
        headers["Idempotency-Key"] = key
    payload = valid_body() if body is None else body
    return client.post("/notifications", json=payload, headers=headers, **kwargs)


def assert_error(response, status: int, code: str) -> dict[str, Any]:
    """Единый формат ошибки: статус, код, `message`, `details` (объект), `correlation_id`."""
    assert response.status_code == status, response.text
    error = response.json()["error"]
    assert set(error) == {"code", "message", "details", "correlation_id"}
    assert error["code"] == code
    assert isinstance(error["details"], dict)
    assert error["correlation_id"]
    assert response.headers["X-Correlation-ID"] == error["correlation_id"]
    return error
