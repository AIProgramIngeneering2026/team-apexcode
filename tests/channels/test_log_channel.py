import logging

import pytest

from notify.channels.log import LogChannel
from notify.domain.channel import SendContext
from notify.domain.failure import FailureReason

CTX = SendContext(notification_id="notification-1", correlation_id="correlation-1")


def test_log_channel_sends_and_logs_context(caplog):
    channel = LogChannel()

    with caplog.at_level(logging.INFO, logger="notify.channels.log"):
        result = channel.send("ops-team", "Hello", CTX)

    assert result.ok is True
    assert result.reason is None
    assert len(result.attempts) == 1
    record = caplog.records[0]
    assert record.notification_id == "notification-1"
    assert record.correlation_id == "correlation-1"
    assert record.recipient == "ops-team"
    assert record.getMessage() == "Hello"


@pytest.mark.parametrize(
    ("recipient", "message", "expected_field"),
    [
        ("", "Hello", "recipient"),
        ("x" * 256, "Hello", "recipient"),
        ("ops-team", "", "message"),
        ("ops-team", "x" * 4097, "message"),
    ],
)
def test_log_channel_invalid_params_identifies_field(recipient, message, expected_field):
    result = LogChannel().send(recipient, message, CTX)

    assert result.ok is False
    assert result.reason is FailureReason.INVALID_PARAMS
    assert result.attempts == ()
    assert expected_field in result.detail
