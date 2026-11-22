"""Порт HTTP-отправителя и fake-реализация для практики 3.

Реальный адаптер на httpx будет добавлен вне доменного ядра на последующей практике.
"""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, TypeAlias

from notify.domain.channel import Attempt
from notify.domain.failure import FailureReason


@dataclass(frozen=True)
class HttpSendResult:
    """Итог HTTP-отправки, включая все попытки в порядке выполнения."""

    attempts: tuple[Attempt, ...]

    @property
    def ok(self) -> bool:
        return bool(self.attempts) and self.attempts[-1].ok

    @property
    def reason(self) -> FailureReason | None:
        return None if self.ok else self.attempts[-1].reason

    @property
    def status_code(self) -> int | None:
        return self.attempts[-1].status_code if self.attempts else None

    @property
    def detail(self) -> str | None:
        if self.ok:
            return None
        last = self.attempts[-1]
        if last.status_code is not None:
            return f"HTTP {last.status_code}"
        return last.reason.value if last.reason is not None else "HTTP request failed"


class HttpSender(Protocol):
    """Порт: выполняет HTTP POST, timeout, классификацию и повторы."""

    def send(
        self,
        url: str,
        json_body: dict[str, str],
        headers: dict[str, str],
    ) -> HttpSendResult:
        ...


FakeOutcome: TypeAlias = int | FailureReason


class FakeSender:
    """Детерминированная подмена HttpSender без реальной сети и задержек.

    Передаваемые outcomes — результаты последовательных попыток:
    HTTP-код либо причина транспортной ошибки. Повторяет 5xx и транспортные
    ошибки максимум два раза; 2xx завершают отправку успешно, 3xx/4xx — сразу.
    """

    def __init__(
        self,
        outcomes: list[FakeOutcome] | tuple[FakeOutcome, ...] = (200,),
    ) -> None:
        if not outcomes:
            raise ValueError("FakeSender requires at least one outcome")
        self._outcomes = tuple(outcomes)
        self.calls: list[dict[str, object]] = []

    def send(
        self,
        url: str,
        json_body: dict[str, str],
        headers: dict[str, str],
    ) -> HttpSendResult:
        self.calls.append({"url": url, "json": dict(json_body), "headers": dict(headers)})
        attempts: list[Attempt] = []

        for index in range(3):
            outcome = self._outcomes[min(index, len(self._outcomes) - 1)]
            started_at = datetime.now(UTC)

            if isinstance(outcome, int):
                status_code = outcome
                if 200 <= outcome < 300:
                    attempts.append(Attempt(started_at, 0, True, outcome, None))
                    break
                if 300 <= outcome < 500:
                    reason = FailureReason.REJECTED_BY_RECEIVER
                else:
                    reason = FailureReason.RECEIVER_ERROR
            else:
                status_code = None
                reason = outcome

            attempts.append(Attempt(started_at, 0, False, status_code, reason))

            retryable = reason in {
                FailureReason.TIMEOUT,
                FailureReason.BAD_RESPONSE,
                FailureReason.RECEIVER_ERROR,
            }
            if not retryable or index == 2:
                break

        return HttpSendResult(tuple(attempts))
