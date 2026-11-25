"""Идемпотентность создания (S2, ADR-0002). Ключи хранятся в БД — это проверяет сквозной тест.

TODO(B): удалить `pytestmark` и написать тела.
"""

import pytest

from tests.api.helpers import todo

pytestmark = pytest.mark.skip(reason="TODO(B): тесты идемпотентности ещё не написаны")


def test_repeat_with_same_key_and_body_returns_200_same_id(client, repo):
    """Первый 201, повтор 200 с тем же id; в репозитории одно уведомление."""
    todo()


def test_repeat_returns_current_state_not_initial(client, repo):
    """После перевода уведомления в delivered повтор возвращает delivered."""
    todo()


def test_same_key_other_body_returns_409_and_creates_nothing(client, repo):
    todo()


@pytest.mark.parametrize("field", ["channel", "recipient", "message"])
def test_same_key_with_any_changed_field_returns_409(client, field):
    """Н49: меняется одно поле за раз."""
    todo()


def test_field_order_and_formatting_do_not_change_hash(client):
    """Другой порядок полей, пробелы, \\uXXXX вместо UTF-8 → 200, а не 409."""
    todo()


def test_request_hash_is_sha256_of_canonical_json():
    """Юнит-тест `request_hash`: известное значение, независимость от порядка."""
    todo()


def test_invalid_request_does_not_occupy_the_key(client, repo):
    """422 с ключом K ничего не сохранил; корректный запрос с K после него даёт 201."""
    todo()


def test_two_parallel_identical_requests_make_one_notification(client, repo):
    """Н47 на уровне API: потоки, статусы {201, 200}, одинаковый id, одна запись."""
    todo()
