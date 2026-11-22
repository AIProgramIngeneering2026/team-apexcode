"""Ядро целиком: Registry + Dispatcher + настоящие каналы (log, webhook с FakeSender).

Проверяет, что части двух участников работают вместе и что `Dispatcher` не знает
конкретных каналов: новый канал подключается регистрацией в `Registry`.
"""

import logging

import pytest

from notify.channels.http_sender import FakeSender
from notify.channels.log import LogChannel
from notify.channels.registry import Registry
from notify.channels.webhook import WebhookChannel
from notify.domain.channel import SendContext
from notify.domain.dispatcher import Dispatcher
from notify.domain.errors import InvalidParams, InvalidTransition, UnknownChannel
from notify.domain.failure import FailureReason as R
from notify.domain.notification import Notification
from notify.domain.notification import NotificationStatus as S
from tests.domain.fakes import FakeChannel

URL = "https://example.org/hook"


class LogCollector(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def make_log_channel() -> tuple[LogChannel, LogCollector]:
    logger = logging.getLogger("test.core_integration.log")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    collector = LogCollector()
    logger.handlers = [collector]
    return LogChannel(logger), collector


def process(registry: Registry, channel: str, recipient: str, message: str = "Hello"):
    """Путь воркера: создать, захватить (`accepted → sending`), отдать Dispatcher."""
    notification = Notification.create(channel, recipient, message)
    notification.start()
    ctx = SendContext(notification.id, "corr-1")
    result = Dispatcher(registry).process(notification, ctx)
    return notification, result


# --- обычный путь через реальные каналы ---


def test_log_channel_delivers_through_registry_and_dispatcher():
    log_channel, collector = make_log_channel()
    notification, result = process(Registry([log_channel]), "log", "ops-team", "Сборка готова")
    assert notification.status is S.DELIVERED
    assert len(result.attempts) == 1
    record = collector.records[0]
    assert record.getMessage() == "Сборка готова"
    assert record.notification_id == notification.id
    assert record.correlation_id == "corr-1"


def test_webhook_delivers_and_sends_ids_in_headers():
    sender = FakeSender([200])
    notification, _ = process(Registry([WebhookChannel(sender)]), "webhook", URL)
    assert notification.status is S.DELIVERED
    headers = sender.calls[0]["headers"]
    assert headers["X-Notification-Id"] == notification.id
    assert headers["X-Correlation-ID"] == "corr-1"


@pytest.mark.parametrize(
    ("outcomes", "status", "reason", "attempts"),
    [
        ([200], S.DELIVERED, None, 1),
        ([503, 200], S.DELIVERED, None, 2),
        ([503], S.FAILED, R.RECEIVER_ERROR, 3),
        ([404], S.FAILED, R.REJECTED_BY_RECEIVER, 1),
        ([301], S.FAILED, R.REJECTED_BY_RECEIVER, 1),
        ([R.TIMEOUT], S.FAILED, R.TIMEOUT, 3),
        ([R.BAD_RESPONSE], S.FAILED, R.BAD_RESPONSE, 3),
        ([R.TIMEOUT, 503, 503], S.FAILED, R.RECEIVER_ERROR, 3),
    ],
)
def test_webhook_outcomes_become_notification_states(outcomes, status, reason, attempts):
    registry = Registry([WebhookChannel(FakeSender(outcomes))])
    notification, result = process(registry, "webhook", URL)
    assert notification.status is status
    assert notification.failure_reason is reason
    assert len(result.attempts) == attempts


# --- падение Tool и пропавший канал ---


def test_sender_crash_becomes_internal_error_and_next_notification_is_processed():
    class CrashingSender:
        def send(self, url, json_body, headers):
            raise ConnectionError("socket exploded")

    log_channel, _ = make_log_channel()
    registry = Registry([WebhookChannel(CrashingSender()), log_channel])
    crashed, _ = process(registry, "webhook", URL)
    after, _ = process(registry, "log", "ops-team")
    assert (crashed.status, crashed.failure_reason) == (S.FAILED, R.INTERNAL_ERROR)
    assert after.status is S.DELIVERED


def test_channel_missing_from_registry_fails_with_internal_error():
    log_channel, collector = make_log_channel()
    notification, result = process(Registry([log_channel]), "telegram", "@ivan")
    assert notification.status is S.FAILED
    assert notification.failure_reason is R.INTERNAL_ERROR
    assert notification.failure_detail == "channel not registered"
    assert result.attempts == ()
    assert collector.records == []


def test_invalid_params_at_send_time_become_failed_invalid_params():
    # защитная проверка в send: API такой запрос отклонил бы ещё при создании
    log_channel, collector = make_log_channel()
    notification, result = process(Registry([log_channel]), "log", "")
    assert (notification.status, notification.failure_reason) == (S.FAILED, R.INVALID_PARAMS)
    assert result.attempts == ()
    assert collector.records == []


def test_second_processing_does_not_send_again():
    log_channel, collector = make_log_channel()
    registry = Registry([log_channel])
    notification, _ = process(registry, "log", "ops-team")
    with pytest.raises(InvalidTransition):
        Dispatcher(registry).process(notification, SendContext(notification.id, "corr-2"))
    assert len(collector.records) == 1


# --- новый канал без правки Dispatcher ---


def test_new_channel_is_added_by_registration_only():
    sms = FakeChannel(name="sms")
    notification, _ = process(Registry([sms]), "sms", "+37060000000")
    assert notification.status is S.DELIVERED
    assert len(sms.calls) == 1


# --- ошибки при создании: неизвестный канал и неверные параметры с указанием поля ---


def test_unknown_channel_error_lists_available_channels():
    log_channel, _ = make_log_channel()
    registry = Registry([log_channel, WebhookChannel(FakeSender())])
    with pytest.raises(UnknownChannel) as error:
        registry.get("fax")
    assert error.value.code == "unknown_channel"
    assert error.value.channel == "fax"
    assert error.value.available == ("log", "webhook")


@pytest.mark.parametrize(
    ("channel", "recipient", "message", "fields"),
    [
        ("log", "", "Hello", {"recipient"}),
        ("log", "x" * 256, "Hello", {"recipient"}),
        ("log", "ops-team", "", {"message"}),
        ("log", "", "", {"recipient", "message"}),
        ("webhook", "ftp://example.org", "Hello", {"recipient"}),
        ("webhook", "", "Hello", {"recipient"}),
        ("webhook", URL, "x" * 4097, {"message"}),
        ("webhook", "not a url", "", {"recipient", "message"}),
    ],
)
def test_invalid_params_error_names_the_bad_fields(channel, recipient, message, fields):
    log_channel, _ = make_log_channel()
    registry = Registry([log_channel, WebhookChannel(FakeSender())])
    with pytest.raises(InvalidParams) as error:
        registry.get(channel).ensure_valid(recipient, message)
    assert error.value.code == "invalid_params"
    assert {item.field for item in error.value.fields} == fields
