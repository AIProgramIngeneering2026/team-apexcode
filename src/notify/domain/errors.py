"""Ошибки доменного ядра.

У каждой ошибки есть машинный код (`code`); API-слой на практике 4 превращает
их в ответы единого формата (см. docs/api/openapi.yaml).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldError:
    """Проблема в одном поле параметров."""

    field: str  # "recipient" или "message"
    problem: str  # короткое описание, что не так


class NotifyError(Exception):
    """Базовая ошибка ядра."""

    code: str = "internal_error"


class InvalidTransition(NotifyError):
    """Недопустимый переход состояния. Состояние при этом не меняется."""

    code = "invalid_transition"

    def __init__(
        self,
        current_status: str,
        requested_status: str,
        notification_id: str | None = None,
    ) -> None:
        self.current_status = current_status
        self.requested_status = requested_status
        self.notification_id = notification_id
        super().__init__(
            f"Cannot move notification from '{current_status}' to '{requested_status}'"
        )


class UnknownChannel(NotifyError):
    """Канала с таким именем нет в Registry."""

    code = "unknown_channel"

    def __init__(self, channel: str, available: tuple[str, ...] = ()) -> None:
        self.channel = channel
        self.available = available
        super().__init__(f"Channel '{channel}' is not registered")


class InvalidParams(NotifyError):
    """Параметры канала неверны; `fields` указывает проблемные поля."""

    code = "invalid_params"

    def __init__(self, fields: tuple[FieldError, ...]) -> None:
        self.fields = fields
        names = ", ".join(f.field for f in fields)
        super().__init__(f"Invalid parameters: {names}")


class IdempotencyKeyConflict(NotifyError):
    """`Idempotency-Key` уже использован с другим телом запроса."""

    code = "idempotency_key_conflict"

    def __init__(self) -> None:
        super().__init__("Idempotency-Key was already used with a different request body")


class NotificationNotFound(NotifyError):
    """Уведомления с таким `id` нет (в том числе `id` неверного формата)."""

    code = "not_found"

    def __init__(self, notification_id: str) -> None:
        self.notification_id = notification_id
        super().__init__("Notification not found")
