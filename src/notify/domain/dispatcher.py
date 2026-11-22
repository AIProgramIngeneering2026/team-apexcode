"""Dispatcher: ведёт захваченное уведомление через канал и применяет итог к Notification.

Конкретных каналов не знает: получает их из объекта с методом `get(name)` (это `Registry`).
БД не трогает: захват `accepted → sending` и сохранение результата делает воркер.
"""

import logging
from dataclasses import dataclass
from typing import Protocol

from notify.domain.channel import Attempt, Channel, SendContext, ToolResult
from notify.domain.errors import UnknownChannel
from notify.domain.failure import FailureReason
from notify.domain.notification import Notification, NotificationStatus

logger = logging.getLogger(__name__)


class ChannelProvider(Protocol):
    """То, что нужно Dispatcher от Registry: выдать канал по имени или бросить `UnknownChannel`."""

    def get(self, name: str) -> Channel: ...


@dataclass(frozen=True)
class DispatchResult:
    """Что воркер сохраняет после `process`: попытки. Итог уже применён к Notification."""

    attempts: tuple[Attempt, ...]


class Dispatcher:
    def __init__(self, channels: ChannelProvider) -> None:
        self._channels = channels

    def process(self, notification: Notification, ctx: SendContext) -> DispatchResult:
        """Отправляет уведомление, уже захваченное воркером (`sending`).

        Не бросает исключений из-за канала: падение Tool, неверный результат и пропавший
        канал превращаются в `failed` с причиной `internal_error`. Бросает только при ошибке
        вызывающего: уведомление не в `sending` (`InvalidTransition`, канал не вызывается)
        или `ctx` от другого уведомления (`ValueError`).
        """
        if ctx.notification_id != notification.id:
            raise ValueError("ctx belongs to another notification")
        # Из `sending` разрешены оба итога, поэтому проверки одного перехода достаточно.
        # Это делается до вызова канала: повторная обработка не должна слать сообщение снова.
        notification.check_transition(NotificationStatus.DELIVERED)

        try:
            channel = self._channels.get(notification.channel)
        except UnknownChannel:
            return self._fail(notification, "channel not registered")
        except Exception:
            logger.exception("channel lookup failed: notification_id=%s", notification.id)
            return self._fail(notification, "channel lookup failed")

        try:
            result = channel.send(notification.recipient, notification.message, ctx)
        except Exception as error:
            logger.exception(
                "channel raised: notification_id=%s correlation_id=%s",
                notification.id,
                ctx.correlation_id,
            )
            return self._fail(notification, f"channel raised {type(error).__name__}")

        if not isinstance(result, ToolResult):
            return self._fail(notification, "channel returned invalid result")

        if result.ok:
            notification.deliver()
        else:
            assert result.reason is not None  # гарантирует ToolResult
            notification.fail(result.reason, result.detail)
        return DispatchResult(result.attempts)

    @staticmethod
    def _fail(notification: Notification, detail: str) -> DispatchResult:
        notification.fail(FailureReason.INTERNAL_ERROR, detail)
        return DispatchResult(())
