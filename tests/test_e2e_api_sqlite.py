"""Сквозной тест: API + SQLite + миграции + воркер + `FakeSender`. Делается последним PR,
после влития работы A (`notify.storage.sql`, `notify.worker`, миграции).

TODO(B): удалить `pytestmark` после влития A и написать тело.
"""

import pytest

from tests.api.helpers import todo

pytestmark = pytest.mark.skip(reason="TODO(B): ждёт влития SQL-хранилища и воркера (участник A)")


def test_create_wait_delivered_get_attempts_and_repeat_does_not_resend(tmp_path):
    """upgrade(url) на tmp_path → SqlNotificationRepository → create_app → POST (201) →
    Worker.run_once() → GET: delivered, одна попытка → повтор POST с тем же ключом: 200, тот же id,
    `len(sender.calls) == 1`. Затем новый репозиторий на том же файле («перезапуск»): GET даёт то
    же уведомление, повтор POST с тем же ключом всё ещё 200 (ключ в БД, не в памяти)."""
    todo()
