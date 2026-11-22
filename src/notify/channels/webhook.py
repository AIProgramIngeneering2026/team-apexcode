"""Webhook-канал: валидация и преобразование результата HttpSender."""

from urllib.parse import urlsplit

from notify.domain.channel import Channel, SendContext, ToolResult
from notify.domain.errors import FieldError
from notify.domain.failure import FailureReason
from notify.channels.http_sender import HttpSender


class WebhookChannel(Channel):
    name = "webhook"
    recipient_format = "абсолютный HTTP(S) URL до 2048 символов"

    def __init__(self, sender: HttpSender) -> None:
        self._sender = sender

    def validate_recipient(self, recipient: str) -> list[FieldError]:
        if not isinstance(recipient, str) or not 1 <= len(recipient) <= 2048:
            return [FieldError("recipient", "must be an HTTP(S) URL of 1..2048 characters")]

        try:
            parsed = urlsplit(recipient)
            valid = (
                parsed.scheme in {"http", "https"}
                and bool(parsed.hostname)
                and parsed.port != 0
            )
        except ValueError:
            valid = False

        if not valid:
            return [FieldError("recipient", "must be an absolute http or https URL")]
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

        result = self._sender.send(
            url=recipient,
            json_body={
                "notification_id": ctx.notification_id,
                "message": message,
            },
            headers={
                "Content-Type": "application/json",
                "X-Notification-Id": ctx.notification_id,
                "X-Correlation-ID": ctx.correlation_id,
            },
        )
        return ToolResult(
            ok=result.ok,
            reason=result.reason,
            status_code=result.status_code,
            detail=result.detail[:200] if result.detail else None,
            attempts=result.attempts,
        )
