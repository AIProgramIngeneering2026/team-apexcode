"""Порт хранилища: сигнатуры зафиксированы, чтобы две реализации не разошлись."""

import dataclasses
import inspect

import pytest

from notify.domain.errors import IdempotencyKeyConflict, NotificationNotFound, NotifyError
from notify.domain.repository import CreateResult, NotificationRepository
from tests.domain.fakes import new_notification

# Метод → имена параметров без `self`. Менять только вместе с ADR-0004 и обеими реализациями.
EXPECTED = {
    "create": ["notification", "idempotency_key", "request_hash"],
    "get": ["notification_id"],
    "attempts": ["notification_id"],
    "list": ["status", "limit", "offset"],
    "cancel": ["notification_id"],
    "list_accepted": ["limit"],
    "claim": ["notification_id"],
    "finish": ["notification", "attempts"],
    "ping": [],
}


def public_methods() -> dict[str, inspect.Signature]:
    return {
        name: inspect.signature(member)
        for name, member in inspect.getmembers(NotificationRepository, inspect.isfunction)
        if not name.startswith("_")
    }


def test_port_has_exactly_the_agreed_methods():
    assert set(public_methods()) == set(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_port_method_parameters(name):
    assert list(public_methods()[name].parameters)[1:] == EXPECTED[name]


def test_create_result_is_immutable():
    result = CreateResult(new_notification(), created=True)
    assert result.created is True
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.created = False


def test_repository_errors_have_api_codes():
    assert issubclass(IdempotencyKeyConflict, NotifyError)
    assert IdempotencyKeyConflict().code == "idempotency_key_conflict"
    error = NotificationNotFound("not-a-uuid")
    assert (error.code, error.notification_id) == ("not_found", "not-a-uuid")
    assert "not-a-uuid" not in str(error)  # текст не раскрывает введённое значение
