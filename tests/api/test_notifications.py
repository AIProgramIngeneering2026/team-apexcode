"""Обычный путь через API (S1, S3, S4): создать → получить состояние → получить результат.

TODO(B): удалить `pytestmark`, когда `create_app` и маршруты готовы, и написать тела.
"""

import pytest

from tests.api.helpers import todo

pytestmark = pytest.mark.skip(reason="TODO(B): тесты API ещё не написаны")


def test_create_returns_201_with_accepted_notification(client):
    """201, id (UUID), status=accepted, failure_reason=null, заголовок X-Correlation-ID."""
    todo()


def test_get_returns_notification_with_empty_attempts(client):
    todo()


def test_full_path_create_process_get_result(client, repo, registry):
    """создать → Worker(repo, Dispatcher(registry)).run_once() (или repo.claim/finish вручную,
    если воркер A ещё не влит) → GET: delivered и одна попытка (number=1, outcome=success,
    status_code=200, reason=null)."""
    todo()


def test_get_failed_shows_reason_and_attempts(client):
    """FakeSender([503]) → failed/receiver_error, три попытки, в попытках нет тела ответа."""
    todo()


def test_list_filters_by_status_and_returns_total(client):
    todo()


def test_list_default_limit_is_50_and_newest_first(client):
    todo()


def test_cancel_accepted_returns_200_and_channel_is_not_called(client, sender):
    """cancel → cancelled; после run_once канал не вызван (`sender.calls == []`)."""
    todo()


def test_channels_lists_registered_channels(client):
    """log и webhook с recipient_format и max_message_length."""
    todo()


def test_health_ok_and_unavailable(client, repo, monkeypatch):
    """200 при ping() True; при `monkeypatch.setattr(repo, "ping", lambda: False)` — 503."""
    todo()
