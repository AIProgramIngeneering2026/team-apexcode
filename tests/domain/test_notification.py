"""Notification: обычный путь и проверка всех переходов (docs/state-machine.md)."""

import pytest

from notify.domain.errors import InvalidTransition
from notify.domain.failure import FailureReason
from notify.domain.notification import ALLOWED_TRANSITIONS, Notification, NotificationStatus
from tests.domain.fakes import new_notification

S = NotificationStatus
ALL = list(S)

# Матрица из state-machine.md, записанная независимо от кода: ровно 4 разрешённые пары.
EXPECTED_ALLOWED = {
    (S.ACCEPTED, S.SENDING),
    (S.ACCEPTED, S.CANCELLED),
    (S.SENDING, S.DELIVERED),
    (S.SENDING, S.FAILED),
}


def notification_in(status: NotificationStatus) -> Notification:
    """Приводит новое уведомление в нужное состояние только законными командами."""
    n = new_notification()
    if status is S.ACCEPTED:
        return n
    if status is S.CANCELLED:
        n.cancel()
        return n
    n.start()
    if status is S.DELIVERED:
        n.deliver()
    elif status is S.FAILED:
        n.fail(FailureReason.TIMEOUT, "no response")
    return n


# --- обычный путь ---


def test_create_starts_in_accepted():
    n = Notification.create("webhook", "https://example.org/hook", "Сборка завершена")
    assert n.status is S.ACCEPTED
    assert n.failure_reason is None and n.failure_detail is None
    assert n.id and n.created_at == n.updated_at


def test_ids_are_unique():
    assert new_notification().id != new_notification().id


def test_happy_path_accepted_sending_delivered():
    n = new_notification()
    n.start()
    assert n.status is S.SENDING
    n.deliver()
    assert n.status is S.DELIVERED
    assert n.failure_reason is None
    assert n.updated_at >= n.created_at


def test_failure_path_keeps_reason_and_detail():
    n = new_notification()
    n.start()
    n.fail(FailureReason.RECEIVER_ERROR, "503 on 3 attempts")
    assert n.status is S.FAILED
    assert n.failure_reason is FailureReason.RECEIVER_ERROR
    assert n.failure_detail == "503 on 3 attempts"


def test_cancel_path():
    n = new_notification()
    n.cancel()
    assert n.status is S.CANCELLED


def test_interrupt_sets_interrupted_reason():
    n = notification_in(S.SENDING)
    n.interrupt()
    assert n.status is S.FAILED
    assert n.failure_reason is FailureReason.INTERRUPTED


def test_failure_detail_is_cut_to_200_characters():
    n = notification_in(S.SENDING)
    n.fail(FailureReason.BAD_RESPONSE, "x" * 500)
    assert len(n.failure_detail) == 200


# --- таблица переходов: все 25 пар ---


def test_transition_table_matches_state_machine_doc():
    actual = {(a, b) for a, targets in ALLOWED_TRANSITIONS.items() for b in targets}
    assert actual == EXPECTED_ALLOWED
    assert len(ALL) ** 2 - len(actual) == 21  # запрещено 21 из 25


@pytest.mark.parametrize("source", ALL)
@pytest.mark.parametrize("target", ALL)
def test_every_pair_is_allowed_or_rejected_as_documented(source, target):
    n = notification_in(source)
    allowed = (source, target) in EXPECTED_ALLOWED
    assert n.can_move_to(target) is allowed
    if allowed:
        n.check_transition(target)
    else:
        with pytest.raises(InvalidTransition):
            n.check_transition(target)
    assert n.status is source  # проверка ничего не меняет


# --- все команды из всех состояний ---

COMMANDS = {
    "start": (lambda n: n.start(), S.SENDING),
    "cancel": (lambda n: n.cancel(), S.CANCELLED),
    "deliver": (lambda n: n.deliver(), S.DELIVERED),
    "fail": (lambda n: n.fail(FailureReason.TIMEOUT, "late"), S.FAILED),
    "interrupt": (lambda n: n.interrupt(), S.FAILED),
}


@pytest.mark.parametrize("source", ALL)
@pytest.mark.parametrize("command", list(COMMANDS))
def test_command_either_moves_as_documented_or_is_rejected_without_change(source, command):
    run, target = COMMANDS[command]
    n = notification_in(source)
    reason_before, detail_before = n.failure_reason, n.failure_detail
    if (source, target) in EXPECTED_ALLOWED:
        run(n)
        assert n.status is target
    else:
        with pytest.raises(InvalidTransition) as error:
            run(n)
        assert error.value.current_status == source.value
        assert error.value.requested_status == target.value
        assert error.value.notification_id == n.id
        assert n.status is source
        assert (n.failure_reason, n.failure_detail) == (reason_before, detail_before)


# --- правило живёт в Notification ---


@pytest.mark.parametrize("status", ALL)
def test_status_cannot_be_assigned_from_outside(status):
    n = new_notification()
    with pytest.raises(AttributeError):
        n.status = status


def test_failure_reason_exists_only_for_failed():
    with pytest.raises(ValueError):
        Notification(
            id="1", channel="log", recipient="r", message="m",
            status=S.DELIVERED, failure_reason=FailureReason.TIMEOUT,
        )  # fmt: skip
    with pytest.raises(ValueError):
        Notification(id="1", channel="log", recipient="r", message="m", status=S.FAILED)


@pytest.mark.parametrize("status", [S.ACCEPTED, S.SENDING, S.DELIVERED, S.CANCELLED])
def test_reason_is_cleared_for_non_failed_states(status):
    assert notification_in(status).failure_reason is None
