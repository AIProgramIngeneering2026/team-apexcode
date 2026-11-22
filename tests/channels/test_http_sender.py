import pytest

from notify.channels.http_sender import FakeSender, HttpSendResult
from notify.domain.failure import FailureReason


def test_http_send_result_requires_at_least_one_attempt():
    with pytest.raises(ValueError):
        HttpSendResult(())


def test_fake_sender_requires_outcomes():
    with pytest.raises(ValueError):
        FakeSender([])


def test_fake_sender_takes_reason_and_status_from_last_attempt():
    result = FakeSender([FailureReason.TIMEOUT, 503, 503]).send("https://x.org", {}, {})

    assert result.reason is FailureReason.RECEIVER_ERROR
    assert result.status_code == 503
    assert len(result.attempts) == 3
