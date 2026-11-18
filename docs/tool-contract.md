# Контракт Tool (Channel)

Tool в Notify — это `Channel`: исполнитель, который доставляет сообщение получателю. `Dispatcher` знает только этот контракт и не знает конкретных каналов, поэтому новый канал подключается регистрацией в `Registry` без правки `Dispatcher`.

Интерфейс живёт в доменном ядре (`src/notify/domain`) и не импортирует FastAPI, SQLAlchemy и httpx. Реализации лежат в `src/notify/channels` и тоже не импортируют фреймворки, БД и HTTP-клиенты (это проверяет `tests/test_architecture.py`). Реальный httpx-адаптер лежит вне ядра (`src/notify/adapters`, практика 6); `WebhookChannel` получает его через порт `HttpSender`.

## Интерфейс

Типы лежат в трёх файлах: `domain/failure.py` (`FailureReason`), `domain/errors.py` (`FieldError` и ошибки), `domain/channel.py` (всё остальное; `FieldError` реэкспортируется оттуда).

```python
# domain/failure.py
from enum import StrEnum


class FailureReason(StrEnum):
    TIMEOUT = "timeout"
    REJECTED_BY_RECEIVER = "rejected_by_receiver"
    RECEIVER_ERROR = "receiver_error"
    BAD_RESPONSE = "bad_response"
    INVALID_PARAMS = "invalid_params"
    INTERNAL_ERROR = "internal_error"
    INTERRUPTED = "interrupted"  # ставит восстановление после сбоя, а не Tool


# domain/errors.py
@dataclass(frozen=True)
class FieldError:
    field: str       # "recipient" или "message"
    problem: str     # короткое описание, что не так


# domain/channel.py
@dataclass(frozen=True)
class SendContext:
    notification_id: str
    correlation_id: str


@dataclass(frozen=True)
class Attempt:
    started_at: datetime
    duration_ms: int
    ok: bool
    status_code: int | None       # код ответа получателя, если он был
    reason: FailureReason | None  # None, если ok; иначе задан (иначе ValueError)


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    reason: FailureReason | None       # None, если ok
    status_code: int | None            # код последней попытки
    detail: str | None                 # краткое пояснение, до 200 символов, без тела ответа
    attempts: tuple[Attempt, ...]      # все попытки по порядку
    # __post_init__ проверяет инварианты из раздела «Что Tool возвращает»


class Channel(ABC):
    name: str                      # имя в Registry: "log", "webhook"
    recipient_format: str          # описание формата recipient для GET /channels
    max_message_length: int = 4096

    def validate(self, recipient: str, message: str) -> list[FieldError]:
        """Проверка параметров без побочных эффектов и без сети."""
        errors = []
        if not message or len(message) > self.max_message_length:
            errors.append(FieldError("message", f"must be 1..{self.max_message_length} characters"))
        errors.extend(self.validate_recipient(recipient))
        return errors

    def ensure_valid(self, recipient: str, message: str) -> None:
        """То же, что validate, но бросает InvalidParams(fields), если список непуст."""

    @abstractmethod
    def validate_recipient(self, recipient: str) -> list[FieldError]: ...

    @abstractmethod
    def send(self, recipient: str, message: str, ctx: SendContext) -> ToolResult: ...
```

## Что Tool получает

| Параметр | Что это |
|---|---|
| `recipient` | Адрес получателя; формат зависит от канала (для `webhook` это URL, для `log` метка) |
| `message` | Текст сообщения, 1–4096 символов Unicode (считаются символы, а не байты) |
| `ctx` | `notification_id` и `correlation_id`; нужны для заголовков и логов, на результат доставки не влияют |

## Что Tool возвращает

`ToolResult` в любом случае, когда отказ вызван внешним миром (получатель, сеть). Правила:

- `ok = True` означает, что `reason` равен `None`, а в `attempts` последняя попытка успешна.
- `ok = False` означает, что `reason` задан. `attempts` непуст, кроме случая `invalid_params`: сеть там не вызывалась.
- Если попыток было несколько, `reason` и `status_code` берутся из **последней**. Например, `timeout`, потом `503`, потом `503` даёт `receiver_error`.
- Все попытки, включая повторы внутри Tool, возвращаются в `attempts`, а `Dispatcher` записывает их в `delivery_attempts`.
- В `detail` и `attempts` нет тела ответа получателя: только код и краткая причина.
- Инварианты проверяются в `ToolResult.__post_init__` (и в `Attempt.__post_init__`): `ok` согласован с `reason`, при успехе последняя попытка успешна, `attempts` пусты только при `invalid_params`, причина `interrupted` от Tool не принимается. Нарушение даёт `ValueError`: это ошибка в коде Tool, `Dispatcher` перехватит её и поставит `internal_error`.

## Какими ошибками Tool отказывает

| Ситуация | Как выглядит | Кто и что делает дальше |
|---|---|---|
| Получатель недоступен, медленный, отвечает не так | `ToolResult(ok=False, reason=...)`, исключения нет | `Dispatcher` переводит уведомление в `failed` с этой причиной |
| `send` вызван с некорректными параметрами | `ToolResult(ok=False, reason=INVALID_PARAMS)`, сеть не вызывается | То же; на практике не случается, потому что параметры проверены раньше |
| Ошибка в коде Tool (неожиданное исключение) | Исключение | `Dispatcher` его перехватывает, пишет в лог и ставит `failed` с `internal_error`; воркер не останавливается |
| Канала нет в `Registry` при создании | `Registry.get` выбрасывает `UnknownChannel` | API отвечает `422 unknown_channel` (до сохранения) |
| Канала нет в `Registry` при отправке (уведомление сохранено, а канал потом убрали из конфигурации) | `Registry.get` выбрасывает `UnknownChannel` внутри `Dispatcher` | `Dispatcher` перехватывает, канал не вызывается, ставит `failed` с `internal_error` и `detail = "channel not registered"`; воркер не останавливается |

Правило: **Tool не бросает исключений из-за поведения получателя**. Исключение означает ошибку в нашем коде.

## Кто проверяет параметры

| Что проверяется | Кто | Когда |
|---|---|---|
| Канал существует | `Registry` (`UnknownChannel`) | При создании уведомления, до сохранения |
| Формат `recipient` и длина `message` | **Tool**, метод `validate` (список `FieldError`) или `ensure_valid` (исключение `InvalidParams` с теми же полями); вызывает **API-слой** | При создании, до сохранения: `422 invalid_params`, поля в `details` |
| То же ещё раз | Tool, в начале `send` | Защитная проверка; при ошибке `INVALID_PARAMS` |
| Наличие и формат `Idempotency-Key`, валидность JSON | API-слой | Не касается Tool |

Правила формата знает только Tool, потому что только он понимает, что такое корректный получатель. Вызывающий (API) не копирует эти правила, а вызывает `channel.validate(...)` или `channel.ensure_valid(...)`. `Dispatcher` параметры не проверяет.

## Общие требования к реализациям

- Tool не хранит состояние между вызовами и не зависит от БД.
- Один и тот же вызов может произойти повторно (гарантия «хотя бы один раз»), поэтому побочный эффект на стороне получателя должен отсекаться по `X-Notification-Id`.
- Время одного `send` ограничено: для сетевых Tool это число попыток × timeout + паузы.
- Конфигурация (timeout, число повторов, пауза) берётся из окружения, а не из аргументов `send`.

---

## Tool 1: `LogChannel` (`name = "log"`)

Пишет сообщение в лог приложения. Сети нет, поэтому это самый простой канал; он нужен для разработки и тестов `Dispatcher`.

| | |
|---|---|
| `recipient` | Непустая строка до 255 символов, метка записи в лог (например, `ops-team`). Другие значения `validate` отклоняет |
| `message` | 1–4096 символов |
| Что делает | Пишет одну запись уровня INFO с полями `notification_id`, `correlation_id`, `recipient`, `message` |
| Успех | `ToolResult(ok=True, attempts=(одна попытка, status_code=None))` |
| Отказ | Только `INVALID_PARAMS` при неверных параметрах. Других отказов у канала нет |
| Повторы | Нет |

## Tool 2: `WebhookChannel` (`name = "webhook"`)

Отправляет HTTP POST на URL получателя. HTTP-детали (httpx, timeout, повторы, разбор ответа) спрятаны в адаптере `HttpSender` внутри этого Tool; снаружи видны только `ToolResult` и `attempts`.

| | |
|---|---|
| `recipient` | Абсолютный URL со схемой `http` или `https`, с хостом, до 2048 символов |
| `message` | 1–4096 символов |
| Запрос | `POST` с `Content-Type: application/json`, тело `{"notification_id": "...", "message": "..."}`, заголовки `X-Notification-Id` и `X-Correlation-ID` |
| Ограничения | Timeout 5 с на попытку, включая чтение ответа; читается не более 64 КиБ ответа, тело отбрасывается; редиректы не выполняются |
| Повторы | До 2 после первой попытки (всего 3), с паузой 1 с |

Классификация ответов:

| Что произошло | Повтор | Итоговая причина, если попытки кончились |
|---|---|---|
| `2xx` | нет, успех | `ok = True` |
| `3xx` (редирект не выполняется) | нет | `rejected_by_receiver` |
| `4xx` | нет | `rejected_by_receiver` |
| `5xx` | да | `receiver_error` |
| Timeout (подключение, ответ или общий) | да | `timeout` |
| Соединение разорвано, ответ не HTTP, ответ больше лимита | да | `bad_response` |

Известное ограничение: адреса внутренней сети (SSRF) не блокируются, см. раздел «Чего в системе нет» в README.

## Как контракт расширяется

Третий Tool (`TelegramChannel`, если хватит времени) подключается так же: реализует `validate_recipient` и `send`, регистрируется в `Registry`. Правки `Dispatcher`, API и этого контракта не требуются, кроме строки в таблице каналов.
