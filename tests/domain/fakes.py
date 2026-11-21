"""Заглушки для тестов ядра: настоящие каналы и Registry пишет другой участник."""

from datetime import UTC, datetime

from notify.domain.channel import Attempt, Channel, FieldError, SendContext, ToolResult
from notify.domain.errors import UnknownChannel
from notify.domain.failure import FailureReason
from notify.domain.notification import Notification

NOW = datetime(2026, 11, 18, tzinfo=UTC)


def ok_result(code: int | None = 200) -> ToolResult:
    attempt = Attempt(NOW, 5, True, code, None)
    return ToolResult(True, None, code, None, (attempt,))


def failed_result(reason: FailureReason, code: int | None = None, detail: str | None = None):
    attempt = Attempt(NOW, 5, False, code, reason)
    return ToolResult(False, reason, code, detail, (attempt,))


class FakeChannel(Channel):
    """Канал-заглушка: возвращает заданный результат или бросает заданную ошибку."""

    recipient_format = "любая строка"

    def __init__(self, name="fake", result=None, error=None):
        self.name = name
        self.result = result if result is not None else ok_result()
        self.error = error
        self.calls: list[tuple[str, str, SendContext]] = []

    def validate_recipient(self, recipient: str) -> list[FieldError]:
        return []

    def send(self, recipient: str, message: str, ctx: SendContext) -> ToolResult:
        self.calls.append((recipient, message, ctx))
        if self.error is not None:
            raise self.error
        return self.result


class FakeRegistry:
    """Минимальная замена Registry: `get` по имени, `UnknownChannel` для неизвестного."""

    def __init__(self, *channels: Channel):
        self._channels = {c.name: c for c in channels}

    def get(self, name: str) -> Channel:
        try:
            return self._channels[name]
        except KeyError:
            raise UnknownChannel(name, tuple(self._channels)) from None


def new_notification(channel: str = "fake") -> Notification:
    return Notification.create(channel, "target", "hello")


def ctx_for(notification: Notification, correlation_id: str = "corr-1") -> SendContext:
    return SendContext(notification.id, correlation_id)
