"""Notification (Job): состояния и проверка переходов в одном месте.

Диаграмма и причины: docs/state-machine.md. Состояние меняется только методами
этого класса; недопустимый переход отклоняется `InvalidTransition`, состояние
при этом не меняется. Класс ничего не знает о БД: условные `UPDATE` при захвате
и отмене делает хранилище (практика 4), а здесь живёт только таблица переходов.
"""

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Self
from uuid import uuid4

from notify.domain.errors import InvalidTransition
from notify.domain.failure import FailureReason

MAX_FAILURE_DETAIL_LENGTH = 200


class NotificationStatus(StrEnum):
    ACCEPTED = "accepted"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


_S = NotificationStatus

# Разрешённые переходы: 4 из 25 пар. Всё, чего здесь нет, запрещено.
ALLOWED_TRANSITIONS: Mapping[NotificationStatus, frozenset[NotificationStatus]] = MappingProxyType(
    {
        _S.ACCEPTED: frozenset({_S.SENDING, _S.CANCELLED}),
        _S.SENDING: frozenset({_S.DELIVERED, _S.FAILED}),
        _S.DELIVERED: frozenset(),
        _S.FAILED: frozenset(),
        _S.CANCELLED: frozenset(),
    }
)


def _now() -> datetime:
    return datetime.now(UTC)


class Notification:
    """Единица работы. Новое уведомление создаётся через `Notification.create`."""

    def __init__(
        self,
        *,
        id: str,
        channel: str,
        recipient: str,
        message: str,
        status: NotificationStatus = NotificationStatus.ACCEPTED,
        failure_reason: FailureReason | None = None,
        failure_detail: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ) -> None:
        """Полный конструктор нужен хранилищу, чтобы восстановить запись из БД."""
        if status is _S.FAILED and failure_reason is None:
            raise ValueError("failed notification must have a failure reason")
        if status is not _S.FAILED and (failure_reason is not None or failure_detail is not None):
            raise ValueError("failure reason is allowed only for failed notification")
        self.id = id
        self.channel = channel
        self.recipient = recipient
        self.message = message
        self._status = status
        self._failure_reason = failure_reason
        self._failure_detail = failure_detail
        self._created_at = created_at or _now()
        self._updated_at = updated_at or self._created_at

    @classmethod
    def create(cls, channel: str, recipient: str, message: str) -> Self:
        """Новое уведомление в состоянии `accepted` (`[*] → accepted`)."""
        return cls(id=str(uuid4()), channel=channel, recipient=recipient, message=message)

    # --- состояние: только для чтения, менять можно лишь командами ниже ---

    @property
    def status(self) -> NotificationStatus:
        return self._status

    @property
    def failure_reason(self) -> FailureReason | None:
        return self._failure_reason

    @property
    def failure_detail(self) -> str | None:
        return self._failure_detail

    @property
    def created_at(self) -> datetime:
        return self._created_at

    @property
    def updated_at(self) -> datetime:
        return self._updated_at

    # --- проверка переходов ---

    def can_move_to(self, target: NotificationStatus) -> bool:
        return target in ALLOWED_TRANSITIONS[self._status]

    def check_transition(self, target: NotificationStatus) -> None:
        """Бросает `InvalidTransition`, если перехода в `target` из текущего состояния нет."""
        if not self.can_move_to(target):
            raise InvalidTransition(self._status.value, target.value, self.id)

    # --- команды ---

    def start(self) -> None:
        """Воркер берёт в работу: `accepted → sending`."""
        self._move(_S.SENDING)

    def cancel(self) -> None:
        """Клиент отменяет: `accepted → cancelled`. Из `sending` отмены нет."""
        self._move(_S.CANCELLED)

    def deliver(self) -> None:
        """Канал вернул успех: `sending → delivered`."""
        self._move(_S.DELIVERED)

    def fail(self, reason: FailureReason, detail: str | None = None) -> None:
        """Попытки исчерпаны или отказ: `sending → failed` с причиной."""
        self._move(_S.FAILED, reason, detail)

    def interrupt(self) -> None:
        """Восстановление после сбоя: `sending → failed`, причина `interrupted`."""
        self._move(_S.FAILED, FailureReason.INTERRUPTED, "interrupted by restart")

    def _move(
        self,
        target: NotificationStatus,
        reason: FailureReason | None = None,
        detail: str | None = None,
    ) -> None:
        self.check_transition(target)  # при отказе ничего ниже не выполняется
        self._status = target
        self._failure_reason = reason
        self._failure_detail = detail[:MAX_FAILURE_DETAIL_LENGTH] if detail else None
        self._updated_at = _now()

    def __repr__(self) -> str:
        return f"Notification(id={self.id!r}, status={self._status.value!r})"
