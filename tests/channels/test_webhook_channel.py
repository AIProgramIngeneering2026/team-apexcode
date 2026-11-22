import pytest

from notify.channels.http_sender import FakeSender
from notify.channels.webhook import WebhookChannel
from notify.domain.channel import SendContext
from notify.domain.failure import FailureReason

CTX = SendContext(notification_id="notification-1", correlation_id="correlation-1")
URL = "https://example.org/notify"


def test_webhook_sends_payload_and_required_headers():
    sender = FakeSender([200])
    result = WebhookChannel(sender).send(URL, "Hello", CTX)

    assert result.ok is True
    assert len(result.attempts) == 1
    call = sender.calls[0]
    assert call["json"] == {"notification_id": "notification-1", "message": "Hello"}
    assert call["headers"]["X-Notification-Id"] == "notification-1"
    assert call["headers"]["X-Correlation-ID"] == "correlation-1"


@pytest.mark.parametrize(
    ("recipient", "message", "expected_field"),
    [
        ("file:///etc/passwd", "Hello", "recipient"),
        ("", "Hello", "recipient"),
        ("https://example.org", "", "message"),
        (URL, "x" * 4097, "message"),
    ],
)
def test_webhook_invalid_params_identifies_field_and_skips_sender(
    recipient, message, expected_field
):
    sender = FakeSender([200])
    result = WebhookChannel(sender).send(recipient, message, CTX)

    assert result.ok is False
    assert result.reason is FailureReason.INVALID_PARAMS
    assert result.attempts == ()
    assert expected_field in result.detail
    assert sender.calls == []


@pytest.mark.parametrize("status_code", [200, 201, 204])
def test_webhook_classifies_2xx_as_success(status_code):
    result = WebhookChannel(FakeSender([status_code])).send(URL, "Hello", CTX)

    assert result.ok is True
    assert result.status_code == status_code


@pytest.mark.parametrize("status_code", [301, 404])
def test_webhook_classifies_3xx_and_4xx_without_retry(status_code):
    sender = FakeSender([status_code, 200])
    result = WebhookChannel(sender).send(URL, "Hello", CTX)

    assert result.ok is False
    assert result.reason is FailureReason.REJECTED_BY_RECEIVER
    assert len(result.attempts) == 1


def test_webhook_retries_5xx_then_succeeds():
    sender = FakeSender([503, 200])
    result = WebhookChannel(sender).send(URL, "Hello", CTX)

    assert result.ok is True
    assert len(result.attempts) == 2


def test_webhook_retries_5xx_up_to_three_attempts():
    sender = FakeSender([503])
    result = WebhookChannel(sender).send(URL, "Hello", CTX)

    assert result.ok is False
    assert result.reason is FailureReason.RECEIVER_ERROR
    assert len(result.attempts) == 3


@pytest.mark.parametrize(
    "reason",
    [FailureReason.TIMEOUT, FailureReason.BAD_RESPONSE],
)
def test_webhook_retries_transport_errors(reason):
    sender = FakeSender([reason])
    result = WebhookChannel(sender).send(URL, "Hello", CTX)

    assert result.ok is False
    assert result.reason is reason
    assert len(result.attempts) == 3
