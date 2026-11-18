"""Тесты общих контрактов ядра: ToolResult, Attempt, Channel.validate, ошибки."""

from datetime import UTC, datetime

import pytest

from notify.domain.channel import Attempt, Channel, FieldError, SendContext, ToolResult
from notify.domain.errors import InvalidParams, InvalidTransition, NotifyError, UnknownChannel
from notify.domain.failure import FailureReason

NOW = datetime(2026, 11, 18, tzinfo=UTC)


def attempt(ok: bool, reason: FailureReason | None = None, code: int | None = None) -> Attempt:
    return Attempt(started_at=NOW, duration_ms=10, ok=ok, status_code=code, reason=reason)


class DummyChannel(Channel):
    name = "dummy"
    recipient_format = "любая непустая строка"

    def validate_recipient(self, recipient: str) -> list[FieldError]:
        return [] if recipient else [FieldError("recipient", "must not be empty")]

    def send(self, recipient: str, message: str, ctx: SendContext) -> ToolResult:
        return ToolResult(True, None, None, None, (attempt(True),))


# --- Attempt ---


def test_attempt_success_without_reason_is_valid():
    assert attempt(True).reason is None


@pytest.mark.parametrize(
    ("ok", "reason"),
    [(True, FailureReason.TIMEOUT), (False, None)],
)
def test_attempt_ok_and_reason_must_agree(ok, reason):
    with pytest.raises(ValueError):
        attempt(ok, reason)


# --- ToolResult ---


def test_tool_result_success():
    result = ToolResult(True, None, 200, None, (attempt(True, code=200),))
    assert result.ok


def test_tool_result_failure_keeps_all_attempts():
    failed = attempt(False, FailureReason.RECEIVER_ERROR, 503)
    attempts = (failed, failed, failed)
    result = ToolResult(False, FailureReason.RECEIVER_ERROR, 503, "503 x3", attempts)
    assert len(result.attempts) == 3


def test_tool_result_invalid_params_may_have_no_attempts():
    result = ToolResult(False, FailureReason.INVALID_PARAMS, None, "bad recipient", ())
    assert result.attempts == ()


@pytest.mark.parametrize(
    "kwargs",
    [
        # успех с причиной
        dict(ok=True, reason=FailureReason.TIMEOUT, attempts=(attempt(True),)),
        # успех без попыток
        dict(ok=True, reason=None, attempts=()),
        # успех, но последняя попытка неудачная
        dict(ok=True, reason=None, attempts=(attempt(False, FailureReason.TIMEOUT),)),
        # отказ без причины
        dict(ok=False, reason=None, attempts=(attempt(False, FailureReason.TIMEOUT),)),
        # отказ, но последняя попытка успешна
        dict(ok=False, reason=FailureReason.TIMEOUT, attempts=(attempt(True),)),
        # отказ без попыток не по invalid_params
        dict(ok=False, reason=FailureReason.TIMEOUT, attempts=()),
        # interrupted ставит только восстановление
        dict(
            ok=False,
            reason=FailureReason.INTERRUPTED,
            attempts=(attempt(False, FailureReason.TIMEOUT),),
        ),
    ],
    ids=[
        "ok-with-reason",
        "ok-no-attempts",
        "ok-last-attempt-failed",
        "fail-no-reason",
        "fail-last-attempt-ok",
        "fail-no-attempts",
        "interrupted-from-channel",
    ],
)
def test_tool_result_rejects_inconsistent_state(kwargs):
    with pytest.raises(ValueError):
        ToolResult(status_code=None, detail=None, **kwargs)


# --- Channel.validate / ensure_valid ---


def test_validate_returns_no_errors_for_valid_params():
    assert DummyChannel().validate("anywhere", "hello") == []


@pytest.mark.parametrize("message", ["", "x" * 4097])
def test_validate_rejects_bad_message_with_field_name(message):
    errors = DummyChannel().validate("anywhere", message)
    assert [e.field for e in errors] == ["message"]


def test_validate_accepts_message_of_max_length_in_characters():
    # длина считается в символах Unicode, а не в байтах
    assert DummyChannel().validate("anywhere", "я" * 4096) == []


def test_validate_reports_all_problem_fields():
    errors = DummyChannel().validate("", "")
    assert {e.field for e in errors} == {"message", "recipient"}


def test_ensure_valid_raises_invalid_params_with_fields():
    with pytest.raises(InvalidParams) as exc:
        DummyChannel().ensure_valid("", "hello")
    assert exc.value.code == "invalid_params"
    assert [f.field for f in exc.value.fields] == ["recipient"]


def test_ensure_valid_passes_for_valid_params():
    DummyChannel().ensure_valid("anywhere", "hello")


# --- Ошибки ---


def test_errors_are_notify_errors_with_codes():
    assert InvalidTransition("sending", "cancelled", "id-1").code == "invalid_transition"
    assert UnknownChannel("fax", ("log", "webhook")).code == "unknown_channel"
    assert issubclass(InvalidParams, NotifyError)


def test_invalid_transition_keeps_details_for_api():
    error = InvalidTransition("sending", "cancelled", "id-1")
    assert (error.current_status, error.requested_status, error.notification_id) == (
        "sending",
        "cancelled",
        "id-1",
    )


def test_unknown_channel_lists_available():
    assert UnknownChannel("fax", ("log", "webhook")).available == ("log", "webhook")
