"""Реализация порта `NotificationRepository` в памяти: модульные тесты API и воркера.

Семантика обязана совпадать с SQL-реализацией (ADR-0004): те же исключения, те же условные
переходы, одни и те же контрактные тесты (tests/storage/test_repository_contract.py).
"""

# Нужен из-за метода `list`: он затеняет встроенный `list` внутри класса (как в порте).
from __future__ import annotations

from notify.domain.channel import Attempt
from notify.domain.notification import Notification, NotificationStatus
from notify.domain.repository import CreateResult


class InMemoryNotificationRepository:
    """TODO(B): состояние в словарях, ВСЕ методы под одним `threading.Lock` (потоки воркера и
    эндпоинтов). Предложение по хранению:
      - `_by_id: dict[str, Notification]` — в порядке создания (dict помнит порядок вставки);
      - `_by_key: dict[str, tuple[str, str]]` — idempotency_key → (id, request_hash);
      - `_attempts: dict[str, list[Attempt]]`.
    Отдавайте КОПИИ или восстановленные объекты, а не внутренние: внешний код не должен менять
    хранимое состояние в обход методов (в SQL так и есть). Копию уведомления делайте через
    полный конструктор `Notification(...)`, а не обходом приватных полей.
    """

    def __init__(self) -> None:
        # TODO(B): lock, словари
        raise NotImplementedError

    def create(
        self, notification: Notification, idempotency_key: str, request_hash: str
    ) -> CreateResult:
        """TODO(B): ключа нет → сохранить, CreateResult(копия, created=True). Ключ есть и хэш тот
        же → CreateResult(ТЕКУЩЕЕ состояние, created=False). Хэш другой → IdempotencyKeyConflict."""
        raise NotImplementedError

    def get(self, notification_id: str) -> Notification | None:
        """TODO(B): None, если нет (в том числе неверный формат id)."""
        raise NotImplementedError

    def attempts(self, notification_id: str) -> tuple[Attempt, ...]:
        """TODO(B): попытки в порядке выполнения; для неизвестного id — пустой кортеж."""
        raise NotImplementedError

    def list(
        self, status: NotificationStatus | None, limit: int, offset: int
    ) -> tuple[list[Notification], int]:
        """TODO(B): новые первыми, фильтр по статусу, срез offset:offset+limit, total по фильтру.
        Порядок при равных created_at — тот же, что в SQL (обратный порядку создания)."""
        raise NotImplementedError

    def cancel(self, notification_id: str) -> Notification:
        """TODO(B): нет записи → NotificationNotFound(notification_id). Иначе `cancel()` на
        копии: при недопустимом переходе исключение InvalidTransition приходит из ядра,
        состояние не меняется. Проверка и запись — под одним lock."""
        raise NotImplementedError

    def list_accepted(self, limit: int) -> list[Notification]:
        """TODO(B): accepted в порядке создания, не больше limit."""
        raise NotImplementedError

    def claim(self, notification_id: str) -> Notification | None:
        """TODO(B): accepted → sending под lock; иначе (нет, взято, отменено) → None."""
        raise NotImplementedError

    def finish(self, notification: Notification, attempts: tuple[Attempt, ...]) -> bool:
        """TODO(B): в хранилище запись должна быть в sending, иначе False и ничего не менять.
        Иначе записать статус, причину, пояснение, updated_at и попытки ОДНОЙ операцией под lock
        (при ошибке на полпути не должно остаться частичной записи)."""
        raise NotImplementedError

    def ping(self) -> bool:
        return True
