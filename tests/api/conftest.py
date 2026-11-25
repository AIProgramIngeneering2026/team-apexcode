"""Фикстуры тестов API: репозиторий в памяти, `FakeSender`, приложение без воркера."""

import pytest
from fastapi.testclient import TestClient

from notify.api.app import create_app
from notify.channels.http_sender import FakeSender
from notify.channels.log import LogChannel
from notify.channels.registry import Registry
from notify.channels.webhook import WebhookChannel
from notify.storage.memory import InMemoryNotificationRepository


@pytest.fixture
def repo():
    return InMemoryNotificationRepository()


@pytest.fixture
def sender():
    return FakeSender([200])


@pytest.fixture
def registry(sender):
    return Registry([LogChannel(), WebhookChannel(sender)])


@pytest.fixture
def client(repo, registry):
    """`raise_server_exceptions=False`: иначе тест 500 получит исключение вместо ответа."""
    return TestClient(create_app(repo, registry), raise_server_exceptions=False)
