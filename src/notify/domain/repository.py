"""Порт хранилища уведомлений (ADR-0004).

Интерфейс живёт в ядре и не знает о БД: SQL-реализация лежит в `notify.storage.sql`,
реализация в памяти для модульных тестов — в `notify.storage.memory`. Обе обязаны
проходить одни и те же контрактные тесты (`tests/storage/`).

Правила, общие для всех реализаций:

- один метод — одна транзакция: применяется целиком или не применяется вовсе;
- переходы из `accepted` и итоговый переход из `sending` условные (compare-and-set по
  статусу): при гонке применяется ровно одна операция, остальные получают отказ;
- таблицу разрешённых переходов хранилище не дублирует, её знает только `Notification`.
"""

# Без этого импорта аннотации `list[...]` в теле класса не вычислились бы:
# метод `list` ниже затеняет встроенный `list` внутри класса.
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from notify.domain.channel import Attempt
from notify.domain.notification import Notification, NotificationStatus


@dataclass(frozen=True)
class CreateResult:
    """Итог `create`: само уведомление и признак, что оно только что создано."""

    notification: Notification
    created: bool  # True → API отвечает 201; False → идемпотентный повтор → 200


@runtime_checkable
class NotificationRepository(Protocol):
    def create(
        self, notification: Notification, idempotency_key: str, request_hash: str
    ) -> CreateResult:
        """Один `INSERT` без предварительного `SELECT` (ADR-0002, п. 6).

        Ключ уже есть и `request_hash` тот же → `CreateResult(существующее, created=False)`.
        Ключ уже есть, `request_hash` другой → `IdempotencyKeyConflict`, ничего не меняется.
        """

    def get(self, notification_id: str) -> Notification | None:
        """`None`, если такого `id` нет (в том числе `id` неверного формата)."""

    def attempts(self, notification_id: str) -> tuple[Attempt, ...]:
        """Попытки доставки по порядку; номер попытки в API равен позиции плюс один."""

    def list(
        self, status: NotificationStatus | None, limit: int, offset: int
    ) -> tuple[list[Notification], int]:
        """Новые первыми; второй элемент — общее число записей по фильтру (`total`)."""

    def cancel(self, notification_id: str) -> Notification:
        """Условный `accepted → cancelled`.

        `NotificationNotFound`, если `id` нет; `InvalidTransition`, если уведомление
        не в `accepted` (в том числе проиграло гонку воркеру).
        """

    def list_accepted(self, limit: int) -> list[Notification]:
        """Уведомления в `accepted` в порядке создания, не больше `limit`."""

    def claim(self, notification_id: str) -> Notification | None:
        """Условный `accepted → sending`.

        Возвращает захваченное уведомление в `sending` или `None`, если оно уже взято
        другим воркером или отменено.
        """

    def finish(self, notification: Notification, attempts: tuple[Attempt, ...]) -> bool:
        """Сохраняет итог отправки; `notification` уже в `delivered` или `failed`.

        В одной транзакции: условный `UPDATE ... WHERE id = ? AND status = 'sending'`
        (статус, причина, пояснение, время) и вставка `attempts`. Если затронуто 0 строк
        (например, восстановление уже перевело уведомление в `failed`), ничего не
        записывается и возвращается `False`.
        """

    def ping(self) -> bool:
        """`True`, если хранилище отвечает (для `GET /health`)."""
