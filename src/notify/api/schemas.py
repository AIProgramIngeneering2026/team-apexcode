"""Тело запроса и сериализация ответов по docs/api/openapi.yaml (схемы Notification, Attempt)."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from notify.domain.channel import Attempt
from notify.domain.notification import Notification


class NotificationCreate(BaseModel):
    """Лишние поля запрещены (Н41: `status`, `id` в теле → 422), значения только строки.

    Длину и формат `recipient`/`message` проверяет `Channel.validate`, не эта модель.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    channel: str
    recipient: str
    message: str


def notification_to_dict(notification: Notification) -> dict[str, Any]:
    """TODO(B): id, channel, recipient, message, status, failure_reason, failure_detail,
    created_at, updated_at (время в ISO 8601 с `Z`/+00:00; enum → строка; None → null)."""
    raise NotImplementedError


def attempt_to_dict(number: int, attempt: Attempt) -> dict[str, Any]:
    """TODO(B): number, started_at, duration_ms, outcome ("success"/"failure"), status_code,
    reason. Тела ответа получателя в попытках нет и быть не должно."""
    raise NotImplementedError
