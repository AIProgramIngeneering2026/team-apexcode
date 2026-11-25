"""Фикстура `repo` для контрактных тестов хранилища.

Контрактные тесты (`test_repository_contract.py`) принимают фикстуру `repo` и идут по
каждой реализации порта `NotificationRepository`. Реализации подключаются отдельными
модулями, чтобы два участника не правили один файл:

- `tests/storage/impl_memory.py` — реализация в памяти;
- `tests/storage/impl_sql.py` — SQL-реализация на SQLite.

Каждый модуль задаёт `NAME: str` и `make(tmp_path) -> NotificationRepository`
(SQL-реализация создаёт файл БД в `tmp_path` и применяет к нему миграции).
Модуля ещё нет — реализация пропускается. Модуль есть, но падает при импорте — ошибка видна.
"""

from importlib import import_module

import pytest

IMPLEMENTATIONS = ("impl_memory", "impl_sql")


def _load() -> list:
    modules = []
    for name in IMPLEMENTATIONS:
        full_name = f"tests.storage.{name}"
        try:
            modules.append(import_module(full_name))
        except ModuleNotFoundError as error:
            if error.name != full_name:
                raise
    return modules


@pytest.fixture(params=_load(), ids=lambda module: module.NAME)
def repo(request, tmp_path):
    return request.param.make(tmp_path)
