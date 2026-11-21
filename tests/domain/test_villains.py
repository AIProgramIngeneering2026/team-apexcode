"""Злодейства З1–З6 из «Взлом Job» (p3_job.md), применённые к Notification и Dispatcher.

Соответствие терминам: Tool работает, пока уведомление в `sending`; `start` — захват
воркером; `finish` / `fail` — итог канала (`deliver` / `fail`); `restart` — восстановление
после сбоя (`interrupt`); `cancel` — отмена клиентом. Команд `retry`, `rerun` и `delete`
в Notify нет (ручного повтора и удаления в первой версии нет).

Каждое злодейство: явная цепочка и, в конце файла, перебор всех цепочек команд.
"""

from itertools import product

import pytest

from notify.domain.dispatcher import Dispatcher
from notify.domain.errors import InvalidTransition
from notify.domain.failure import FailureReason
from notify.domain.notification import ALLOWED_TRANSITIONS, Notification
from notify.domain.notification import NotificationStatus as S
from tests.domain.fakes import FakeChannel, FakeRegistry, ctx_for, new_notification


def rejected(command) -> None:
    """Команда должна быть отклонена явной ошибкой."""
    with pytest.raises(InvalidTransition):
        command()


# --- З1. Двойная работа: в одном Job одновременно два Tool ---
# create → accepted, Tool: 0 / start → sending, Tool: 1 / start → отказ, sending, Tool: 1


def test_z1_second_start_is_rejected_while_sending():
    n = new_notification()
    n.start()
    rejected(n.start)
    assert n.status is S.SENDING


def test_z1_dispatcher_does_not_run_a_second_tool_for_the_same_notification():
    channel = FakeChannel()
    dispatcher = Dispatcher(FakeRegistry(channel))
    n = new_notification()
    n.start()
    dispatcher.process(n, ctx_for(n))
    rejected(lambda: dispatcher.process(n, ctx_for(n)))
    assert len(channel.calls) == 1


# --- З2. Вечная работа: сервер перезапустился, Job остался в sending ---
# create / start → sending, Tool: 1 / restart → failed (interrupted), Tool: 0


def test_z2_restart_moves_sending_to_failed_interrupted():
    n = new_notification()
    n.start()
    n.interrupt()
    assert n.status is S.FAILED
    assert n.failure_reason is FailureReason.INTERRUPTED


def test_z2_restart_does_not_touch_accepted():
    # accepted без Tool переживает перезапуск: воркер подберёт его после старта
    n = new_notification()
    rejected(n.interrupt)
    assert n.status is S.ACCEPTED


# --- З3. Отменённое стало готовым ---
# create / cancel → cancelled / finish → отказ / start → отказ


def test_z3_cancelled_cannot_become_delivered_or_start():
    n = new_notification()
    n.cancel()
    rejected(n.deliver)
    rejected(n.start)
    rejected(lambda: n.fail(FailureReason.TIMEOUT))
    assert n.status is S.CANCELLED


def test_z3_cancel_is_impossible_while_a_tool_is_working():
    # отмена не останавливает Tool, поэтому из sending её нет: «осиротевшего» Tool не бывает
    n = new_notification()
    n.start()
    rejected(n.cancel)
    assert n.status is S.SENDING


def test_z3_dispatcher_never_calls_channel_for_cancelled_notification():
    channel = FakeChannel()
    n = new_notification()
    n.cancel()
    rejected(lambda: Dispatcher(FakeRegistry(channel)).process(n, ctx_for(n)))
    assert channel.calls == []


# --- З4. Два итога: был в ошибке, потом стал готовым ---
# create / start / restart → failed (interrupted) / finish (поздний ответ) → отказ


def test_z4_late_success_after_interrupted_is_rejected():
    n = new_notification()
    n.start()
    n.interrupt()
    rejected(n.deliver)
    assert (n.status, n.failure_reason) == (S.FAILED, FailureReason.INTERRUPTED)


def test_z4_late_failure_after_delivered_is_rejected():
    n = new_notification()
    n.start()
    n.deliver()
    rejected(lambda: n.fail(FailureReason.TIMEOUT))
    rejected(n.interrupt)
    assert (n.status, n.failure_reason) == (S.DELIVERED, None)


def test_z4_failed_cannot_be_overwritten_by_another_failure():
    n = new_notification()
    n.start()
    n.fail(FailureReason.TIMEOUT, "first")
    rejected(lambda: n.fail(FailureReason.RECEIVER_ERROR, "second"))
    assert (n.failure_reason, n.failure_detail) == (FailureReason.TIMEOUT, "first")


# --- З5. Успех без работы: done, не побывав в sending ---
# create → accepted / finish → отказ


@pytest.mark.parametrize("prepare", ["none", "cancel"])
def test_z5_deliver_without_start_is_rejected(prepare):
    n = new_notification()
    if prepare == "cancel":
        n.cancel()
    rejected(n.deliver)
    rejected(lambda: n.fail(FailureReason.TIMEOUT))
    assert n.status is (S.CANCELLED if prepare == "cancel" else S.ACCEPTED)


# --- З6. Повтор успешного: готовый Job снова пошёл в работу ---
# create / start / finish → delivered / start → отказ


@pytest.mark.parametrize("final", ["deliver", "fail", "cancel"])
def test_z6_terminal_notification_cannot_start_again(final):
    n = new_notification()
    if final == "cancel":
        n.cancel()
    else:
        n.start()
        if final == "deliver":
            n.deliver()
        else:
            n.fail(FailureReason.TIMEOUT)
    status = n.status
    rejected(n.start)
    assert n.status is status


def test_z6_dispatcher_does_not_resend_delivered_notification():
    channel = FakeChannel()
    dispatcher = Dispatcher(FakeRegistry(channel))
    n = new_notification()
    n.start()
    dispatcher.process(n, ctx_for(n))
    rejected(n.start)
    rejected(lambda: dispatcher.process(n, ctx_for(n)))
    assert len(channel.calls) == 1


# --- Перебор: все цепочки команд, пока не найдём нарушение ---

COMMANDS = ("start", "finish", "fail", "restart", "cancel")
CHAIN_LENGTH = 7  # 5**7 = 78 125 цепочек


def apply(n: Notification, command: str, tools: int) -> int:
    """Применяет команду; возвращает число работающих Tool (по правилам «Взлома Job»)."""
    try:
        match command:
            case "start":
                n.start()
                tools += 1
            case "finish":
                n.deliver()
                tools -= 1
            case "fail":
                n.fail(FailureReason.TIMEOUT, "no response")
                tools -= 1
            case "cancel":
                n.cancel()
            case "restart":
                n.interrupt()
        if command == "restart":
            tools = 0
    except InvalidTransition:
        if command == "restart":
            tools = 0  # перезапуск убивает Tool при любом состоянии
    return tools


def check_invariants(n: Notification, tools: int, history: list[S], command: str) -> None:
    where = f"after {command}: {history}, tools={tools}"
    assert 0 <= tools <= 1, f"З1 {where}"  # не больше одного Tool, и не «минус один»
    assert (n.status is S.SENDING) == (tools == 1), f"З1/З2/З5 {where}"
    if command == "restart":
        assert n.status is not S.SENDING, f"З2 {where}"
    if S.CANCELLED in history:
        assert n.status is S.CANCELLED, f"З3 {where}"
    if S.FAILED in history:
        assert S.DELIVERED not in history, f"З4 {where}"
    if S.DELIVERED in history:
        assert S.SENDING in history, f"З5 {where}"
        assert n.status is S.DELIVERED, f"З6 {where}"
    assert history.count(S.SENDING) <= 1, f"З1/З6 {where}"  # в работу не возвращаются
    assert (n.failure_reason is not None) == (n.status is S.FAILED), where


def test_no_chain_of_commands_breaks_the_core():
    steps = 0
    for chain in product(COMMANDS, repeat=CHAIN_LENGTH):
        n = new_notification()
        tools = 0
        history = [n.status]
        for command in chain:
            before = n.status
            tools = apply(n, command, tools)
            if n.status is not before:
                assert n.status in ALLOWED_TRANSITIONS[before], f"{before} → {n.status}"
                history.append(n.status)
            check_invariants(n, tools, history, command)
            steps += 1
    assert steps == len(COMMANDS) ** CHAIN_LENGTH * CHAIN_LENGTH
