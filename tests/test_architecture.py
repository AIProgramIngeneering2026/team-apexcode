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
    # HTTP-клиенты: реальный адаптер живёт вне ядра, за портом HttpSender
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


def imported_notify_modules(path: Path) -> set[str]:
    """Полные имена модулей notify.*, которые импортирует файл."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names if a.name.startswith("notify"))
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            if node.module.startswith("notify"):
                names.add(node.module)
                names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


@pytest.mark.parametrize(
    "path", sorted((SRC / "domain").rglob("*.py")), ids=lambda p: str(p.relative_to(SRC))
)
def test_domain_does_not_know_concrete_channels(path):
    """Dispatcher и остальное ядро не импортируют notify.channels: каналы подключаются снаружи."""
    imports = imported_notify_modules(path)
    assert not {m for m in imports if m.startswith("notify.channels")}
