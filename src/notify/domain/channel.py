"""Контракт Tool (Channel). Подробности: docs/tool-contract.md."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime

from notify.domain.errors import FieldError, InvalidParams
from notify.domain.failure import FailureReason

__all__ = [
    "Attempt",
    "Channel",
    "FieldError",
    "SendContext",
    "ToolResult",
]


@dataclass(frozen=True)
class SendContext:
    notification_id: str
    correlation_id: str


@dataclass(frozen=True)
class Attempt:
    started_at: datetime
    duration_ms: int
    ok: bool
    status_code: int | None  # код ответа получателя, если он был
    reason: FailureReason | None  # None, если ok

    def __post_init__(self) -> None:
        if self.ok and self.reason is not None:
            raise ValueError("successful attempt must not have a reason")
        if not self.ok and self.reason is None:
            raise ValueError("failed attempt must have a reason")
        if self.reason is FailureReason.INTERRUPTED:
            raise ValueError("'interrupted' is set by recovery, not by a Channel")


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    reason: FailureReason | None  # None, если ok
    status_code: int | None  # код последней попытки
    detail: str | None  # краткое пояснение, до 200 символов, без тела ответа
    attempts: tuple[Attempt, ...]  # все попытки по порядку

    def __post_init__(self) -> None:
        """Проверяет инварианты из раздела «Что Tool возвращает»."""
        if self.ok:
            if self.reason is not None:
                raise ValueError("ok result must not have a reason")
            if not self.attempts or not self.attempts[-1].ok:
                raise ValueError("ok result needs attempts ending with a successful one")
            return
        if self.reason is None:
            raise ValueError("failed result must have a reason")
        if self.reason is FailureReason.INTERRUPTED:
            raise ValueError("'interrupted' is set by recovery, not by a Channel")
        if not self.attempts:
            if self.reason is not FailureReason.INVALID_PARAMS:
                raise ValueError("attempts may be empty only for invalid_params")
        elif self.attempts[-1].ok:
            raise ValueError("failed result cannot end with a successful attempt")
        # Attempt гарантирует отсутствие INTERRUPTED в reason (см. Attempt.__post_init__)


class Channel(ABC):
    """Исполнитель доставки. Не хранит состояние, не зависит от БД и фреймворков."""

    name: str  # имя в Registry: "log", "webhook"
    recipient_format: str  # описание формата recipient для GET /channels
    max_message_length: int = 4096

    def validate(self, recipient: str, message: str) -> list[FieldError]:
        """Проверка параметров без побочных эффектов и без сети."""
        errors: list[FieldError] = []
        if not message or len(message) > self.max_message_length:
            errors.append(FieldError("message", f"must be 1..{self.max_message_length} characters"))
        errors.extend(self.validate_recipient(recipient))
        return errors

    def ensure_valid(self, recipient: str, message: str) -> None:
        """То же, что `validate`, но с исключением `InvalidParams` вместо списка."""
        errors = self.validate(recipient, message)
        if errors:
            raise InvalidParams(tuple(errors))

    @abstractmethod
    def validate_recipient(self, recipient: str) -> list[FieldError]: ...

    @abstractmethod
    def send(self, recipient: str, message: str, ctx: SendContext) -> ToolResult: ...