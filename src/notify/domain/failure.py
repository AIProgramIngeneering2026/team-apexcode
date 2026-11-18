"""Причины статуса `failed` (единый список из семи значений)."""

from enum import StrEnum


class FailureReason(StrEnum):
    TIMEOUT = "timeout"
    REJECTED_BY_RECEIVER = "rejected_by_receiver"
    RECEIVER_ERROR = "receiver_error"
    BAD_RESPONSE = "bad_response"
    INVALID_PARAMS = "invalid_params"
    INTERNAL_ERROR = "internal_error"
    # Эту причину ставит восстановление после сбоя, а не Channel:
    # ToolResult с INTERRUPTED отклоняется (см. channel.py).
    INTERRUPTED = "interrupted"
