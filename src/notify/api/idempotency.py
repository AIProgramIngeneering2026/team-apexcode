"""`Idempotency-Key` и отпечаток тела (ADR-0002, п. 1–2)."""

# TODO(B): `from notify.api.errors import ApiError` понадобится в `validate_key`.


def validate_key(raw: str | None) -> str:
    """TODO(B): отсутствует или пустой → ApiError("missing_idempotency_key", 400);
    длина > 255 или символы вне видимых ASCII (0x21–0x7E) → ApiError("invalid_params", 422)
    с details {"fields": [{"field": "Idempotency-Key", "problem": "..."}]}."""
    raise NotImplementedError


def request_hash(channel: str, recipient: str, message: str) -> str:
    """TODO(B): SHA-256 (hex) от канонического JSON {"channel","recipient","message"}:
    `json.dumps(..., sort_keys=True, separators=(",", ":"), ensure_ascii=False)`, кодировка UTF-8.
    Порядок полей и форматирование исходного JSON на хэш не влияют (Н49)."""
    raise NotImplementedError
