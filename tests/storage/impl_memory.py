"""Подключение реализации в памяти к контрактным тестам (фикстура `repo`, см. conftest.py)."""

from notify.storage.memory import InMemoryNotificationRepository

NAME = "memory"


def make(tmp_path):
    return InMemoryNotificationRepository()
