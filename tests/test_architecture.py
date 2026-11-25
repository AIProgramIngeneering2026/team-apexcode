"""Ядро не зависит от веб-фреймворка, БД и HTTP-клиента (CONTRIBUTING, практика 3, п. 5)."""

import ast
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parent.parent / "src" / "notify"
CORE_DIRS = ("domain", "channels")

FORBIDDEN = {
    # веб-фреймворки
    "fastapi", "starlette", "flask", "django", "aiohttp", "uvicorn",
    # БД и ORM
    "sqlalchemy", "alembic", "sqlite3", "psycopg", "psycopg2", "asyncpg", "pymysql",
    # HTTP-клиенты: реальный адаптер живчёт вне ядра, за портом HttpSender
    "httpx", "requests", "urllib3",
}  # fmt: skip


def core_files() -> list[Path]:
    return sorted(p for d in CORE_DIRS for p in (SRC / d).rglob("*.py"))


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


@pytest.mark.parametrize("path", core_files(), ids=lambda p: str(p.relative_to(SRC)))
def test_core_does_not_import_frameworks_or_db(path):
    assert imported_modules(path) & FORBIDDEN == set()


# --- Зависимости между слоями самого проекта ---

# Что слою импортировать нельзя. Направление зависимостей:
#   domain ← channels, storage ← api, worker ← main (main собирает всё).
# Внешние слои подключаются к ядру снаружи: через порты `HttpSender`, `NotificationRepository`.
OUTER_LAYERS = (
    "notify.adapters",
    "notify.api",
    "notify.storage",
    "notify.worker",
    "notify.main",
)
DOMAIN_FORBIDDEN = ("notify.channels", *OUTER_LAYERS)
CHANNELS_FORBIDDEN = OUTER_LAYERS
STORAGE_FORBIDDEN = ("notify.api", "notify.worker", "notify.main")
API_FORBIDDEN = ("notify.storage", "notify.worker", "notify.main")  # репозиторий внедряется
WORKER_FORBIDDEN = ("notify.api", "notify.storage", "notify.main")  # только порты ядра


def module_of(path: Path) -> tuple[str, bool]:
    """Имя модуля по пути файла и признак, что это `__init__.py` пакета."""
    parts = list(path.relative_to(SRC.parent).with_suffix("").parts)
    is_package = parts[-1] == "__init__"
    if is_package:
        parts.pop()
    return ".".join(parts), is_package


def notify_imports(source: str, module: str, is_package: bool = False) -> set[str]:
    """Полные имена модулей `notify.*`, которые импортирует код.

    Относительные импорты (`from .. import channels`) разворачиваются в полное имя
    относительно пакета файла, иначе они обходили бы проверку.
    """
    package = module if is_package else module.rpartition(".")[0]
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = package.split(".")
                up = node.level - 1
                if up >= len(parts):
                    raise ValueError(f"relative import goes beyond top-level package: {module}")
                base = ".".join(parts[: len(parts) - up])
            else:
                base = ""
            full = ".".join(part for part in (base, node.module) if part)
            found.add(full)
            found.update(f"{full}.{alias.name}" for alias in node.names)
    return {name for name in found if name == "notify" or name.startswith("notify.")}


def forbidden_imports(imports: set[str], forbidden: tuple[str, ...]) -> set[str]:
    return {
        name
        for name in imports
        if any(name == prefix or name.startswith(prefix + ".") for prefix in forbidden)
    }


def layer_violations(path: Path, forbidden: tuple[str, ...]) -> set[str]:
    module, is_package = module_of(path)
    source = path.read_text(encoding="utf-8")
    return forbidden_imports(notify_imports(source, module, is_package), forbidden)


@pytest.mark.parametrize(
    "path", sorted((SRC / "domain").rglob("*.py")), ids=lambda p: str(p.relative_to(SRC))
)
def test_domain_does_not_depend_on_outer_layers(path):
    """Ядро не знает конкретных каналов, адаптеров и API: они подключаются снаружи."""
    assert layer_violations(path, DOMAIN_FORBIDDEN) == set()


@pytest.mark.parametrize(
    "path", sorted((SRC / "channels").rglob("*.py")), ids=lambda p: str(p.relative_to(SRC))
)
def test_channels_do_not_depend_on_adapters_or_api(path):
    assert layer_violations(path, CHANNELS_FORBIDDEN) == set()


@pytest.mark.parametrize(
    "path", sorted((SRC / "storage").rglob("*.py")), ids=lambda p: str(p.relative_to(SRC))
)
def test_storage_does_not_depend_on_api_or_worker(path):
    assert layer_violations(path, STORAGE_FORBIDDEN) == set()


@pytest.mark.parametrize(
    "path", sorted((SRC / "api").rglob("*.py")), ids=lambda p: str(p.relative_to(SRC))
)
def test_api_does_not_import_concrete_storage_or_worker(path):
    """API получает репозиторий и воркер снаружи (`create_app(repo, ...)`), а не импортирует."""
    assert layer_violations(path, API_FORBIDDEN) == set()


def test_worker_depends_only_on_domain_ports():
    path = SRC / "worker.py"
    if path.exists():  # воркер появляется в практике 4
        assert layer_violations(path, WORKER_FORBIDDEN) == set()


# --- Сама проверка должна ловить нарушения, включая относительные импорты ---

DISPATCHER = ("notify.domain.dispatcher", False)
DOMAIN_INIT = ("notify.domain", True)

VIOLATIONS = [
    ("import notify.channels", DISPATCHER),
    ("import notify.channels.log as log", DISPATCHER),
    ("from notify import channels", DISPATCHER),
    ("from notify.channels import LogChannel", DISPATCHER),
    ("from notify.channels.webhook import WebhookChannel", DISPATCHER),
    # относительные импорты: именно их пропускала прежняя проверка
    ("from .. import channels", DISPATCHER),
    ("from ..channels import LogChannel", DISPATCHER),
    ("from ..channels.webhook import WebhookChannel", DISPATCHER),
    ("from notify.storage.sql import SqlNotificationRepository", DISPATCHER),
    ("from ..storage import sql", DISPATCHER),
    ("import notify.worker", DISPATCHER),
    ("from .. import channels", DOMAIN_INIT),
    ("from ..channels import LogChannel", DOMAIN_INIT),
]

ALLOWED = [
    ("from notify.domain.channel import Channel", DISPATCHER),
    ("from .channel import Channel", DISPATCHER),
    ("from . import notification", DISPATCHER),
    ("from .. import domain", DISPATCHER),
    ("from . import channel", DOMAIN_INIT),
    ("import logging", DISPATCHER),
]


@pytest.mark.parametrize(("source", "where"), VIOLATIONS)
def test_checker_detects_forbidden_import(source, where):
    imports = notify_imports(source, *where)
    assert forbidden_imports(imports, DOMAIN_FORBIDDEN), source


@pytest.mark.parametrize(("source", "where"), ALLOWED)
def test_checker_allows_legal_import(source, where):
    imports = notify_imports(source, *where)
    assert forbidden_imports(imports, DOMAIN_FORBIDDEN) == set(), source


def test_checker_detects_api_importing_storage():
    imports = notify_imports("from notify.storage.memory import InMemory", "notify.api.app", False)
    assert "notify.storage.memory" in forbidden_imports(imports, API_FORBIDDEN)


def test_relative_import_resolves_to_full_name():
    assert "notify.channels" in notify_imports("from .. import channels", *DISPATCHER)
    assert "notify.domain.notification" in notify_imports("from . import notification", *DISPATCHER)
    assert "notify.domain.channel" in notify_imports("from . import channel", *DOMAIN_INIT)