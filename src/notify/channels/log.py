"""Канал доставки в структурированный лог."""

import logging
from datetime import UTC, datetime

from notify.domain.channel import Attempt, Channel, SendContext, ToolResult
from notify.domain.errors import FieldError
from notify.domain.failure import FailureReason


class LogChannel(Channel):
    name = "log"
    recipient_format = "непустая метка до 255 символов"

    def __init__(self, logger: logging.Logger | None = None) -> None:
        self._logger = logger or logging.getLogger("notify.channels.log")

    def validate_recipient(self, recipient: str) -> list[FieldError]:
        if not isinstance(recipient, str) or not 1 <= len(recipient) <= 255:
            return [FieldError("recipient", "must be 1..255 characters")]
        return []

    def send(self, recipient: str, message: str, ctx: SendContext) -> ToolResult:
        errors = self.validate(recipient, message)
        if errors:
            return ToolResult(
                ok=False,
                reason=FailureReason.INVALID_PARAMS,
                status_code=None,
                detail="; ".join(f"{error.field}: {error.problem}" for error in errors)[:200],
                attempts=(),
            )

        started_at = datetime.now(UTC)
        self._logger.info(
            "%s",
            message,
            extra={
                "notification_id": ctx.notification_id,
                "correlation_id": ctx.correlation_id,
                "recipient": recipient,
            },
        )
        attempt = Attempt(
            started_at=started_at,
            duration_ms=0,
            ok=True,
            status_code=None,
            reason=None,
        )
        return ToolResult(
            ok=True,
            reason=None,
            status_code=None,
            detail=None,
            attempts=(attempt,),
        )
