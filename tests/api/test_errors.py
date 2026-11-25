"""Единый формат и статусы ошибок (S5): минимум три разные, фактически все ниже.

TODO(B): удалить `pytestmark` и написать тела; везде проверять `assert_error` и что в БД
(репозитории) ничего не создано.
"""

import pytest

from tests.api.helpers import todo

pytestmark = pytest.mark.skip(reason="TODO(B): тесты ошибок ещё не написаны")


def test_not_json_returns_400_bad_request(client):
    todo()


def test_missing_idempotency_key_returns_400(client):
    todo()


def test_body_over_64_kib_returns_413_before_parsing(client):
    """И по Content-Length, и тело без него (потоком)."""
    todo()


def test_message_of_4096_unicode_chars_escaped_is_accepted(client):
    """4096 символов кириллицы и эмодзи в формате \\uXXXX (json.dumps по умолчанию): 201."""
    todo()


def test_unknown_channel_returns_422_with_available_list(client):
    """details: channel и available (log, webhook)."""
    todo()


@pytest.mark.parametrize(
    ("changes", "field"),
    [
        ({"recipient": ""}, "recipient"),
        ({"recipient": "ftp://example.org"}, "recipient"),
        ({"message": ""}, "message"),
        ({"message": "x" * 4097}, "message"),
    ],
)
def test_invalid_params_return_422_with_field(client, changes, field):
    todo()


def test_idempotency_key_with_bad_format_returns_422_naming_header(client):
    """Длина 256, пробел, не-ASCII → 422, в details.fields поле Idempotency-Key."""
    todo()


def test_not_found_is_identical_for_missing_and_malformed_id(client):
    """GET и cancel: UUID, которого нет, и строка «не-uuid» дают одинаковые статус и тело
    (кроме correlation_id и notification_id)."""
    todo()


def test_cancel_from_sending_returns_409_invalid_transition(client, repo):
    """details: notification_id, current_status=sending, requested_status=cancelled."""
    todo()


def test_unknown_path_returns_404_and_wrong_method_405_in_unified_format(client):
    todo()


def test_unexpected_exception_returns_500_without_traceback(client, repo, monkeypatch):
    """repo.get бросает RuntimeError('secret path /srv/app SELECT ...'): 500 internal_error,
    в теле нет трассы, путей, SQL и текста исключения; X-Correlation-ID на месте."""
    todo()


def test_client_correlation_id_is_echoed_and_invalid_one_is_replaced(client):
    todo()
