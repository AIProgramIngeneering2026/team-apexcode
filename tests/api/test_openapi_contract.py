"""Контракт `docs/api/openapi.yaml` совпадает с кодом (практика 4, п. 1).

Подход на выбор: `jsonschema` (в группе `api`) + `pyyaml`, либо `openapi-core`.
TODO(B): удалить `pytestmark` и написать тела.
"""

import pytest

from tests.api.helpers import todo

pytestmark = pytest.mark.skip(reason="TODO(B): тест контракта ещё не написан")


def test_every_path_and_method_from_contract_exists_in_app(client):
    """Для каждой пары (путь, метод) из файла запрос не даёт 404/405 «не найдено»."""
    todo()


def test_app_has_no_undocumented_operations(client):
    """Пути из `app.openapi()` ⊆ путям файла (нет эндпоинтов вне контракта; Н44)."""
    todo()


def test_documented_status_codes_are_reproducible():
    """Для каждого кода ответа из файла (201, 200, 400, 404, 409, 413, 422, 500) в тестах
    есть запрос, который его даёт; ответы валидны по схемам из файла (Notification, Error ...)."""
    todo()


def test_contract_version_matches_app_version():
    """`info.version` в файле равен версии приложения."""
    todo()
