"""Tests de migraciones de Alembic."""

from sqlalchemy import text

EXPECTED_TABLES = {
    "users",
    "subjects",
    "tasks",
    "task_history",
    "commitments",
    "resources",
    "alembic_version",
}


async def test_migration_applied_and_version(session) -> None:
    rows = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalars().all()
    assert rows == ["0007"]


async def test_all_tables_exist(session) -> None:
    rows = (
        await session.execute(
            text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public'"
            )
        )
    ).scalars().all()
    assert EXPECTED_TABLES <= set(rows)


async def test_check_constraints_present(session) -> None:
    rows = (
        await session.execute(
            text(
                "SELECT conname FROM pg_constraint WHERE contype = 'c' "
                "AND connamespace = 'public'::regnamespace"
            )
        )
    ).scalars().all()
    names = set(rows)
    for name in (
        "ck_tasks_status",
        "ck_tasks_priority",
        "ck_tasks_source",
        "ck_task_history_event_type",
        "ck_commitments_status",
        "ck_resources_resource_type",
    ):
        assert name in names


async def test_unique_constraints_present(session) -> None:
    rows = (
        await session.execute(
            text(
                "SELECT conname FROM pg_constraint WHERE contype = 'u' "
                "AND connamespace = 'public'::regnamespace"
            )
        )
    ).scalars().all()
    names = set(rows)
    for name in ("uq_users_telegram_id", "uq_subjects_user_name", "uq_tasks_source_event"):
        assert name in names
