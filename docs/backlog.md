# Backlog

Список задач для создания issues в репозитории (по одному issue на пункт). Исполнители: **Участник 1** и **Участник 2** — замените на GitHub-логины.

Метки: `scenario` — по сценарию, `infra` — инфраструктура, `docs` — документация, `practice-N` — к какой практике нужно.

| # | Задача | Метки | Исполнитель |
|---|---|---|---|
| 1 | Скелет репозитория, структура пакетов, линтер, README | infra, practice-1 | Участник 1 |
| 2 | Доменное ядро: `Notification`, состояния, проверка переходов | infra, practice-3 | Участник 1 |
| 3 | `Registry`, `LogChannel`, `WebhookChannel` (с портом `HttpSender`) | infra, practice-3 | Участник 2 |
| 4 | S1: создание уведомления и отправка воркером (webhook) | scenario, practice-4 | Участник 2 |
| 5 | S2: идемпотентное создание (`Idempotency-Key`) | scenario, practice-4 | Участник 2 |
| 6 | S3: отмена уведомления | scenario, practice-4 | Участник 1 |
| 7 | S4: просмотр статуса, истории попыток и списка | scenario, practice-4 | Участник 2 |
| 8 | S5: валидация запроса и единый формат ошибок | scenario, practice-4 | Участник 2 |
| 9 | S6: адаптер HTTP (timeout, retry, мусорный ответ) и fake-получатель | scenario, practice-6 | Участник 1 |
| 10 | Хранилище и миграции (Alembic, SQLite) | infra, practice-4 | Участник 2 |
| 11 | CI (GitHub Actions): линтер и тесты на каждый PR | infra, practice-5 | Участник 1 |
| 12 | Логи с correlation ID, `/health`, конфигурация из окружения | infra, practice-7 | Участник 2 |
| 13 | `docker compose`: app + PostgreSQL + fake-webhook, переход на PostgreSQL | infra, practice-7 | Участник 1 |
| 14 | S6: восстановление зависших `sending` (`interrupted`) и устойчивость воркера к сбоям БД | scenario, practice-6 | Участник 2 |
| 15 | Документы практики 2: `architecture.md`, `api/openapi.yaml` | docs, practice-2 | Участник 2 |
| 16 | Документы практики 2: `state-machine.md`, `tool-contract.md`, ADR-0001–0003, `contract-check.md` | docs, practice-2 | Участник 1 |
| 17 | `Dispatcher`: переходы по `ToolResult`, падение Tool и пропавший канал → `failed` | infra, practice-3 | Участник 1 |
| 18 | Общие контракты ядра и скелет проекта (PR 0) | infra, practice-3 | Участник 1 |

## Описание задач

### 1. Скелет репозитория
Структура: `src/notify/domain`, `src/notify/api`, `src/notify/channels`, `tests/`, `docs/`. Настроен менеджер зависимостей, линтер, `.gitignore`, `.env.example`.
**Готово, когда:** проект ставится по README, пустой тест запускается командой `pytest`.

### 2. Доменное ядро
Класс `Notification` с состояниями и таблицей разрешённых переходов; недопустимый переход приводит к `InvalidTransition`. Ядро не импортирует FastAPI и SQLAlchemy.
**Готово, когда:** тесты проверяют все разрешённые и все запрещённые переходы (параметризованно).

### 3. Registry и каналы
`Registry.register/get`, ошибка «неизвестный канал» (`UnknownChannel`, в ней имя канала и список доступных); `LogChannel`; `WebhookChannel` с внедряемым портом `HttpSender` (Protocol в ядре): `validate_recipient`, классификация ответов по таблице из `docs/tool-contract.md`, повторы, заголовки `X-Notification-Id` и `X-Correlation-ID`. Реальный httpx-адаптер делается в задаче №9, в тестах подставляется fake-sender. Контракт `Channel` и общие типы приходят из задачи №18.
**Готово, когда:** новый тестовый канал регистрируется без правки остального кода; тесты на неизвестный канал, неверные параметры с указанием поля у обоих каналов и классификацию ответов webhook.

### 4. S1: создание и отправка
`POST /notifications`, сохранение в `accepted`, воркер берёт уведомление и вызывает `Dispatcher`. Захват условным `UPDATE ... WHERE status = 'accepted'`, итоговый переход тоже условный (`WHERE status = 'sending'`), опрос и параллельность из настроек (`WORKER_POLL_INTERVAL_SECONDS`, `WORKER_CONCURRENCY`); результат и попытки сохраняет воркер (ADR-0001).
**Готово, когда:** выполнены критерии приёмки S1; тест полного пути с fake-получателем.

### 5. S2: идемпотентность
Ключ хранится с уведомлением (колонки `idempotency_key` UNIQUE и `request_hash`, ADR-0002), повтор возвращает то же уведомление, другое тело даёт `409 idempotency_key_conflict`.
**Готово, когда:** выполнены критерии S2, есть тест на одновременные запросы и на формат ключа (пустой — `400`, недопустимый — `422`).

### 6. S3: отмена
`POST /notifications/{id}/cancel`, условный переход `accepted → cancelled`.
**Готово, когда:** выполнены критерии S3, включая `409` для всех остальных состояний; есть тест на гонку отмены и захвата воркером.

### 7. S4: просмотр
`GET /notifications/{id}` и `GET /notifications?status=`; в ответе по `id` история попыток и причина `failed`; `404` для несуществующего `id` и `id` неверного формата.
**Готово, когда:** выполнены критерии S4.

### 8. S5: валидация и ошибки
Единый формат ошибок во всём API, коды `unknown_channel`, `invalid_params`, `missing_idempotency_key`, `bad_request`, `payload_too_large` (тело больше 64 КиБ, проверяется до разбора JSON).
**Готово, когда:** выполнены критерии S5, каждая ошибка имеет тест.

### 9. S6: адаптер и fake
HTTP-адаптер с timeout 5 с, 2 повторами, классификацией причин (`timeout`, `rejected_by_receiver`, `receiver_error`, `bad_response`), без редиректов, лимит чтения ответа 64 КиБ, fake-получатель с режимами ответов.
**Готово, когда:** выполнены критерии S6, интеграционные тесты идут против fake.

### 10. Хранилище и миграции
Таблицы `notifications` (с `idempotency_key` UNIQUE, `request_hash`, `failure_reason`, индекс по `status` и `created_at`) и `delivery_attempts`; миграции Alembic; репозиторий-слой между API и БД.
**Готово, когда:** чистая БД поднимается миграциями, откат работает.

### 11. CI
Workflow запускает линтер и `pytest` на каждый PR и проверяет, что схема OpenAPI, которую генерирует FastAPI, совпадает с `docs/api/openapi.yaml`.
**Готово, когда:** на PR виден зелёный/красный статус; настроен запрет вливания при красном CI.

### 12. Диагностика
Middleware `X-Correlation-ID`, JSON-логи (URL получателя пишется только как схема, хост и порт), `/health` (с проверкой БД), настройки из переменных окружения.
**Готово, когда:** в логах одного запроса везде один `correlation_id`; `/health` отвечает `503` при недоступной БД.

### 13. Docker Compose и PostgreSQL
Сервисы `app`, `postgres`, `fake-webhook`; миграции применяются при старте.
**Готово, когда:** `docker compose up` из чистого клона поднимает рабочий сервис.

### 14. Восстановление и устойчивость воркера
При старте и каждые `RECOVERY_INTERVAL_SECONDS` уведомления в `sending` старше `SENDING_STALE_AFTER_SECONDS` переводятся в `failed` с причиной `interrupted`. При ошибке БД воркер повторяет запись результата до 3 раз с паузой 1 с, пишет ошибку в лог и не останавливается.
**Готово, когда:** выполнены критерии S6 про `interrupted` и сбой БД; тесты: зависшее `sending` восстанавливается, опоздавший воркер не перезаписывает `failed`, цикл воркера переживает ошибку БД.

### 15. Документы практики 2 (архитектура и API)
`docs/architecture.md` (схемы контекста и компонентов), `docs/api/openapi.yaml`.
**Готово, когда:** выполнены пункты 1 и 3 задания практики 2; документы согласованы с `state-machine.md`, `tool-contract.md` и ADR.

### 16. Документы практики 2 (состояния, Tool, ADR, проверка колодой)
`docs/state-machine.md`, `docs/tool-contract.md`, `docs/adr/0001–0003`, `docs/contract-check.md`.
**Готово, когда:** выполнены пункты 2, 4–7 задания практики 2.

### 17. Dispatcher
`Dispatcher` берёт канал из `Registry`, вызывает `send`, применяет переход `sending → delivered / failed` по `ToolResult` к доменному объекту и БД не трогает; исключение канала и `UnknownChannel` при отправке превращает в `failed` с `internal_error` (`failure_detail = "channel not registered"` для пропавшего канала); воркер при этом не останавливается. Конкретных каналов не знает.
**Готово, когда:** тесты на тестовом канале-заглушке (успех, отказ с причиной, исключение канала, канал пропал из `Registry`); новый канал подключается без правки `Dispatcher`.

### 18. Общие контракты ядра и скелет проекта (PR 0)
`pyproject.toml`, `.gitignore`, пакеты `src/notify/domain` и `src/notify/channels`; `FailureReason`, ошибки ядра (`InvalidTransition`, `UnknownChannel`, `InvalidParams`), `SendContext`, `Attempt`, `ToolResult` с проверкой инвариантов, `Channel` (`validate`, `ensure_valid`); тест на отсутствие импортов фреймворков и БД в ядре; раздел «Разработка и тесты» в README.
**Готово, когда:** `pytest` и `ruff check .` проходят в чистом окружении; `tool-contract.md` совпадает с кодом.
