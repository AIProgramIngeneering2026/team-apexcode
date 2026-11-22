import pytest

from notify.channels.log import LogChannel
from notify.channels.registry import Registry
from notify.channels.webhook import WebhookChannel
from notify.domain.errors import UnknownChannel
from notify.channels.http_sender import FakeSender


def test_registry_returns_registered_channel_instance():
    channel = LogChannel()
    registry = Registry([channel])

    assert registry.get("log") is channel


def test_registry_raises_unknown_channel_with_available_names():
    registry = Registry([LogChannel(), WebhookChannel(FakeSender())])

    with pytest.raises(UnknownChannel) as exc:
        registry.get("telegram")

    assert exc.value.code == "unknown_channel"
    assert exc.value.channel == "telegram"
    assert exc.value.available == ("log", "webhook")


def test_registry_lists_channel_names_in_stable_order():
    registry = Registry([WebhookChannel(FakeSender()), LogChannel()])

    assert registry.names() == ("log", "webhook")
