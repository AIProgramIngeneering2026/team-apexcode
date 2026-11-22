"""Dispatcher: итог канала превращается в переход Notification; падения не выходят наружу."""

import logging

import pytest

from notify.domain.channel import Attempt, ToolResult
from notify.domain.dispatcher import Dispatcher
from notify.domain.errors import InvalidTransition
from notify.domain.failure import FailureReason
from notify.domain.notification import NotificationStatus as S
from tests.domain.fakes import (
    NOW,
    FakeChannel,
    FakeRegistry,
    ctx_for,
    failed_result,
    new_notification,
    ok_result,
)


def sending_notification(channel: str = "fake"):
    n = new_notification(channel)
    n.start()  # захват воркером: accepted → sending
    return n


# --- обычный путь ---


def test_success_moves_sending_to_delivered_and_returns_attempts():
    channel = FakeChannel(result=ok_result())
    n = sending_notification()
    result = Dispatcher(FakeRegistry(channel)).process(n, ctx_for(n))
    assert n.status is S.DELIVERED
    assert result.attempts == ok_result().attempts


def test_channel_receives_recipient_message_and_context():
    channel = FakeChannel()
    n = sending_notification()
    ctx = ctx_for(n, "corr-42")
    Dispatcher(FakeRegistry(channel)).process(n, ctx)
    assert channel.calls == [("target", "hello", ctx)]


@pytest.mark.parametrize(
    "reason",
    [
        FailureReason.TIMEOUT,
        FailureReason.REJECTED_BY_RECEIVER,
        FailureReason.RECEIVER_ERROR,
        FailureReason.BAD_RESPONSE,
    ],
)
def test_channel_failure_becomes_failed_with_same_reason(reason):
    channel = FakeChannel(result=failed_result(reason, 503, "gave up"))
    n = sending_notification()
    result = Dispatcher(FakeRegistry(channel)).process(n, ctx_for(n))
    assert (n.status, n.failure_reason, n.failure_detail) == (S.FAILED, reason, "gave up")
    assert len(result.attempts) == 1


def test_invalid_params_result_becomes_failed_without_attempts():
    channel = FakeChannel(result=ToolResult(False, FailureReason.INVALID_PARAMS, None, "bad", ()))
    n = sending_notification()
    result = Dispatcher(FakeRegistry(channel)).process(n, ctx_for(n))
    assert n.failure_reason is FailureReason.INVALID_PARAMS
    assert result.attempts == ()


def test_attempts_of_retries_are_all_returned():
    attempts = tuple(Attempt(NOW, 5, False, 503, FailureReason.RECEIVER_ERROR) for _ in range(3))
    tool_result = ToolResult(False, FailureReason.RECEIVER_ERROR, 503, None, attempts)
    n = sending_notification()
    result = Dispatcher(FakeRegistry(FakeChannel(result=tool_result))).process(n, ctx_for(n))
    assert result.attempts == attempts


def test_new_channel_works_without_changing_dispatcher():
    class BrandNewChannel(FakeChannel):
        pass

    n = sending_notification("brand-new")
    Dispatcher(FakeRegistry(BrandNewChannel(name="brand-new"))).process(n, ctx_for(n))
    assert n.status is S.DELIVERED


# --- падение Tool превращается в failed / internal_error ---


@pytest.mark.parametrize("error", [RuntimeError("boom"), KeyError("x"), ZeroDivisionError()])
def test_channel_exception_becomes_internal_error(error):
    n = sending_notification()
    result = Dispatcher(FakeRegistry(FakeChannel(error=error))).process(n, ctx_for(n))
    assert n.status is S.FAILED
    assert n.failure_reason is FailureReason.INTERNAL_ERROR
    assert type(error).__name__ in n.failure_detail
    assert result.attempts == ()


def test_exception_text_does_not_leak_into_detail():
    n = sending_notification()
    channel = FakeChannel(error=RuntimeError("token=secret-123"))
    Dispatcher(FakeRegistry(channel)).process(n, ctx_for(n))
    assert "secret" not in n.failure_detail


def test_channel_exception_is_logged_with_notification_id():
    records: list[logging.LogRecord] = []

    class Collect(logging.Handler):
        def emit(self, record):
            records.append(record)

    logger = logging.getLogger("notify.domain.dispatcher")
    handler = Collect()
    logger.addHandler(handler)
    try:
        n = sending_notification()
        Dispatcher(FakeRegistry(FakeChannel(error=RuntimeError("boom")))).process(n, ctx_for(n))
    finally:
        logger.removeHandler(handler)
    assert any(n.id in r.getMessage() for r in records)


def test_channel_returning_garbage_becomes_internal_error():
    n = sending_notification()
    channel = FakeChannel()
    channel.send = lambda *args: None  # не ToolResult
    Dispatcher(FakeRegistry(channel)).process(n, ctx_for(n))
    assert (n.status, n.failure_reason) == (S.FAILED, FailureReason.INTERNAL_ERROR)


def test_dispatcher_survives_after_a_failing_channel():
    registry = FakeRegistry(FakeChannel(name="bad", error=RuntimeError()), FakeChannel(name="ok"))
    dispatcher = Dispatcher(registry)
    bad, good = sending_notification("bad"), sending_notification("ok")
    dispatcher.process(bad, ctx_for(bad))
    dispatcher.process(good, ctx_for(good))
    assert (bad.status, good.status) == (S.FAILED, S.DELIVERED)


# --- канал пропал из Registry после создания уведомления ---


def test_channel_missing_from_registry_becomes_internal_error_without_calling_anything():
    other = FakeChannel(name="other")
    n = sending_notification("telegram")  # создано, когда канал был; теперь его нет
    result = Dispatcher(FakeRegistry(other)).process(n, ctx_for(n))
    assert n.status is S.FAILED
    assert n.failure_reason is FailureReason.INTERNAL_ERROR
    assert n.failure_detail == "channel not registered"
    assert result.attempts == ()
    assert other.calls == []


def test_registry_lookup_crash_becomes_internal_error():
    class BrokenRegistry:
        def get(self, name):
            raise RuntimeError("registry broke")

    n = sending_notification()
    Dispatcher(BrokenRegistry()).process(n, ctx_for(n))
    assert (n.status, n.failure_reason) == (S.FAILED, FailureReason.INTERNAL_ERROR)


# --- ошибки вызывающего: канал не вызывается ---


@pytest.mark.parametrize("finish", ["deliver", "fail", "cancel", "none"])
def test_notification_not_in_sending_is_rejected_and_channel_not_called(finish):
    channel = FakeChannel()
    n = new_notification()
    if finish == "cancel":
        n.cancel()
    elif finish != "none":
        n.start()
        if finish == "deliver":
            n.deliver()
        else:
            n.fail(FailureReason.TIMEOUT)
    status_before = n.status
    with pytest.raises(InvalidTransition):
        Dispatcher(FakeRegistry(channel)).process(n, ctx_for(n))
    assert channel.calls == []
    assert n.status is status_before


def test_processing_the_same_notification_twice_sends_once():
    channel = FakeChannel()
    dispatcher = Dispatcher(FakeRegistry(channel))
    n = sending_notification()
    dispatcher.process(n, ctx_for(n))
    with pytest.raises(InvalidTransition):
        dispatcher.process(n, ctx_for(n))
    assert len(channel.calls) == 1
    assert n.status is S.DELIVERED


def test_context_of_another_notification_is_rejected():
    channel = FakeChannel()
    n, other = sending_notification(), sending_notification()
    with pytest.raises(ValueError):
        Dispatcher(FakeRegistry(channel)).process(n, ctx_for(other))
    assert channel.calls == []
    assert n.status is S.SENDING
