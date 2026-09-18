"""Fixtures compartidas por los tests.

Incluye la infraestructura para levantar un cluster PostgreSQL temporal
(real, no simulado) y ejecutar las migraciones de Alembic sobre él.
"""

import asyncio
import shutil
import socket
import subprocess
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings

PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clear_settings_cache() -> None:
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _run_migrations(database_url: str) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(PROJECT_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(cfg, "head")


@pytest.fixture(scope="session")
def postgres_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    """Levanta un PostgreSQL temporal y devuelve la URL async de conexión."""
    initdb = shutil.which("initdb")
    pg_ctl = shutil.which("pg_ctl")
    createdb = shutil.which("createdb")
    if not (initdb and pg_ctl and createdb):
        pytest.skip("PostgreSQL (initdb/pg_ctl/createdb) no está disponible")

    datadir = tmp_path_factory.mktemp("pgdata")
    port = _free_port()

    subprocess.run(
        [initdb, "-D", str(datadir), "-U", "postgres", "--auth=trust", "-E", "UTF8"],
        check=True,
        capture_output=True,
    )
    sockdir = datadir / "sock"
    sockdir.mkdir()
    logfile = datadir / "pg.log"
    subprocess.run(
        [
            pg_ctl,
            "-D",
            str(datadir),
            "-l",
            str(logfile),
            "-o",
            f"-p {port} -h 127.0.0.1 -k {sockdir}",
            "start",
        ],
        check=True,
        capture_output=True,
    )
    try:
        subprocess.run(
            [
                createdb,
                "-h",
                "127.0.0.1",
                "-p",
                str(port),
                "-U",
                "postgres",
                "itzamna_test",
            ],
            check=True,
            capture_output=True,
        )
        url = f"postgresql+asyncpg://postgres@127.0.0.1:{port}/itzamna_test"
        _run_migrations(url)
        yield url
    finally:
        subprocess.run(
            [pg_ctl, "-D", str(datadir), "-m", "fast", "stop"],
            check=False,
            capture_output=True,
        )


@pytest.fixture(scope="session")
def session_factory(postgres_url: str):
    """Factory de sesiones contra el PostgreSQL temporal de tests."""
    engine = create_async_engine(postgres_url, poolclass=NullPool)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    yield factory
    try:
        asyncio.run(engine.dispose())
    except RuntimeError:
        pass


@pytest.fixture
async def session(session_factory):
    """Sesión con las tablas vacías antes de cada test de base de datos."""
    async with session_factory() as s:
        await s.execute(
            text(
                "TRUNCATE users, subjects, tasks, task_history, commitments, resources, "
                "task_sources, google_credentials RESTART IDENTITY CASCADE"
            )
        )
        await s.commit()
        yield s


@pytest.fixture
def user_service(session_factory):
    from app.services.users import UserService

    return UserService(session_factory)


@pytest.fixture
def subject_service(session_factory):
    from app.services.subjects import SubjectService

    return SubjectService(session_factory)


@pytest.fixture
def task_service(session_factory):
    from app.services.tasks import TaskService

    return TaskService(session_factory)


@pytest.fixture
def commitment_service(session_factory):
    from app.services.commitments import CommitmentService

    return CommitmentService(session_factory)
