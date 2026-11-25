"""Наш API против нарушений: API. Имена тестов идут в отчёт p4.md.

TODO(B): удалить `pytestmark` и написать тела. Н42 неприменимо (в Notify нет пользователей
и паролей) — в отчёт одна строка.
"""

import pytest

from tests.api.helpers import todo

pytestmark = pytest.mark.skip(reason="TODO(B): тесты нарушений ещё не написаны")


def test_n40_unknown_and_malformed_id_give_same_404_and_ids_are_uuid4(client):
    """Разделения клиентов нет сознательно (ADR-0003): одинаковый 404, id — UUIDv4."""
    todo()


def test_n41_extra_fields_in_create_are_rejected(client, repo):
    """`status`, `failure_reason`, `id`, `created_at` в теле → 422, ничего не создано."""
    todo()


@pytest.mark.parametrize("method", ["put", "patch", "delete"])
def test_n41_no_way_to_change_status_by_other_methods(client, method):
    """/notifications и /notifications/{id}: 404/405 в едином формате, состояние не меняется."""
    todo()


@pytest.mark.parametrize("value", ["201", "1000", "0", "-1", "abc"])
def test_n43_limit_out_of_range_is_422(client, value):
    todo()


def test_n43_default_limit_50_and_max_200_return_exact_counts(client, repo):
    """250 записей: без limit ровно 50, limit=200 ровно 200; offset=-1 → 422."""
    todo()


@pytest.mark.parametrize("action", ["start", "deliver", "fail", "retry", "interrupt"])
def test_n44_internal_transitions_are_not_exposed(client, repo, action):
    """POST /notifications/{id}/{action} → 404 в едином формате, статус не меняется."""
    todo()


@pytest.mark.parametrize(
    "changes",
    [
        {"message": ""},
        {"message": "x" * 4097},
        {"message": None},
        {"message": 123},
        {"recipient": ""},
        {"recipient": "x" * 2049},
        {"recipient": "not a url"},
    ],
)
def test_n45_values_outside_contract_are_rejected(client, changes):
    """422 invalid_params, поле в details.fields. Граница: message из 4096 символов принимается."""
    todo()


def test_n47_parallel_double_click_creates_one_notification(client, repo):
    todo()


def test_n48_repeat_after_delivery_does_not_send_again(client, sender):
    """После delivered повтор POST с тем же ключом → 200 и `len(sender.calls) == 1`;
    повторная отмена → 409 invalid_transition."""
    todo()


def test_n49_same_key_other_body_conflicts(client):
    todo()


def test_hidden_token_in_recipient_is_not_echoed_in_errors_or_logs(client, repo, caplog):
    """recipient с `?token=SECRET`: строки SECRET нет в ответах 422/404/409/500 и в caplog.
    В GET токен виден — это ограничение ADR-0003, п. 4: в отчёте как известное, не закрытое."""
    todo()
