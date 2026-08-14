"""One-time, idempotent SQLite to PostgreSQL import for Aurora HR."""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from sqlalchemy import MetaData, inspect, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings
from app.database import async_database_url
from app.models import Base, Employee

ROOT = Path(__file__).resolve().parents[1]
SQLITE_URL = "sqlite+aiosqlite:///./aurora.db"
BACKUP_DIR = ROOT / "migration_backups"


def json_value(value):
    if isinstance(value, (UUID, Decimal)):
        return str(value)
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_value(item) for item in value]
    return value


async def table_names(engine) -> list[str]:
    async with engine.connect() as connection:
        return await connection.run_sync(lambda sync: inspect(sync).get_table_names())


async def read_rows(engine, table) -> list[dict]:
    async with engine.connect() as connection:
        result = await connection.execute(select(table))
        return [dict(row._mapping) for row in result]


async def real_counts(engine, names: list[str]) -> dict[str, int]:
    from sqlalchemy import func

    async with engine.connect() as connection:
        result = {}
        for name in names:
            table = Base.metadata.tables[name]
            result[name] = await connection.scalar(select(func.count()).select_from(table))
        return result


async def verify_schema(destination, names: list[str]) -> None:
    async with destination.connect() as connection:
        for name in names:
            expected = {column.name for column in Base.metadata.tables[name].columns}
            actual = await connection.run_sync(
                lambda sync, name=name: {column["name"] for column in inspect(sync).get_columns(name)}
            )
            if expected != actual:
                raise RuntimeError(f"Schema mismatch for {name}: missing={sorted(expected - actual)}, extra={sorted(actual - expected)}")


def natural_id_map(source_rows: list[dict], destination_rows: list[dict], key_functions) -> dict:
    destination_by_key = {}
    for row in destination_rows:
        for key_function in key_functions:
            key = key_function(row)
            if key is not None:
                destination_by_key.setdefault(key, row["id"])
    mapping = {}
    for row in source_rows:
        matches = {destination_by_key[key_function(row)] for key_function in key_functions if key_function(row) in destination_by_key}
        if len(matches) > 1:
            raise RuntimeError(f"Conflicting natural-key matches for {row.get('id')}")
        if matches:
            mapping[row["id"]] = matches.pop()
    return mapping


def apply_id(row: dict, field: str, mapping: dict) -> None:
    if row.get(field) in mapping:
        row[field] = mapping[row[field]]


async def backup_destination(destination, names: list[str]) -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    path = BACKUP_DIR / f"postgres-pre-migration-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}.json"
    snapshot = {name: [json_value(row) for row in await read_rows(destination, Base.metadata.tables[name])] for name in names}
    path.write_text(json.dumps(snapshot, indent=2, sort_keys=True), encoding="utf-8")
    return path


async def migrate(dry_run: bool) -> None:
    sqlite = create_async_engine(SQLITE_URL, pool_pre_ping=True)
    destination = create_async_engine(async_database_url(settings.database_url), pool_pre_ping=True)
    names = [table.name for table in Base.metadata.sorted_tables]
    try:
        sqlite_names = set(await table_names(sqlite))
        postgres_names = set(await table_names(destination))
        missing = set(names) - sqlite_names
        if missing:
            raise RuntimeError(f"SQLite is missing model tables: {sorted(missing)}")
        missing = set(names) - postgres_names
        if missing:
            raise RuntimeError(f"PostgreSQL is missing model tables: {sorted(missing)}")
        await verify_schema(destination, names)

        before_sqlite = await real_counts(sqlite, names)
        before_postgres = await real_counts(destination, names)
        print("sqlite_before=" + json.dumps(before_sqlite, sort_keys=True))
        print("postgres_before=" + json.dumps(before_postgres, sort_keys=True))
        backup = await backup_destination(destination, names)
        print(f"postgres_backup={backup}")
        if dry_run:
            print("dry_run=true")
            return

        source_rows = {name: await read_rows(sqlite, Base.metadata.tables[name]) for name in names}
        destination_rows = {name: await read_rows(destination, Base.metadata.tables[name]) for name in names}
        id_maps = {
            "departments": natural_id_map(source_rows["departments"], destination_rows["departments"], [lambda row: row["name"].casefold()]),
            "users": natural_id_map(
                source_rows["users"],
                destination_rows["users"],
                [lambda row: row["email"].casefold(), lambda row: row["login_id"].casefold()],
            ),
        }
        id_maps["employees"] = natural_id_map(
            source_rows["employees"],
            destination_rows["employees"],
            [
                lambda row: row["employee_code"].casefold(),
                lambda row: id_maps["users"].get(row["user_id"], row["user_id"]),
            ],
        )
        id_maps["documents"] = natural_id_map(source_rows["documents"], destination_rows["documents"], [lambda row: row["object_key"]])

        def attendance_key(row):
            return (id_maps["employees"].get(row["employee_id"], row["employee_id"]), row["work_date"])

        def payroll_key(row):
            return (id_maps["employees"].get(row["employee_id"], row["employee_id"]), row["period"])

        id_maps["attendance"] = natural_id_map(source_rows["attendance"], destination_rows["attendance"], [attendance_key])
        id_maps["payroll"] = natural_id_map(source_rows["payroll"], destination_rows["payroll"], [payroll_key])

        for table_name, mapping in id_maps.items():
            print(f"{table_name}_natural_key_matches={len(mapping)}")

        for row in source_rows["users"]:
            apply_id(row, "id", id_maps["users"])
        for row in source_rows["departments"]:
            apply_id(row, "id", id_maps["departments"])
        for row in source_rows["employees"]:
            apply_id(row, "id", id_maps["employees"])
            apply_id(row, "user_id", id_maps["users"])
            apply_id(row, "department_id", id_maps["departments"])
        for row in source_rows["attendance"] + source_rows["leave_requests"] + source_rows["payroll"] + source_rows["documents"]:
            apply_id(row, "employee_id", id_maps["employees"])
        for row in source_rows["notifications"]:
            apply_id(row, "user_id", id_maps["users"])
        for row in source_rows["audit_logs"] + source_rows["event_outbox"]:
            apply_id(row, "actor_id", id_maps["users"])
        for row in source_rows["leave_requests"]:
            apply_id(row, "approver_id", id_maps["users"])
        for row in source_rows["employees"]:
            apply_id(row, "manager_id", id_maps["employees"])
        for row in source_rows["documents"]:
            apply_id(row, "id", id_maps["documents"])
        for row in source_rows["attendance"]:
            apply_id(row, "id", id_maps["attendance"])
        for row in source_rows["payroll"]:
            apply_id(row, "id", id_maps["payroll"])
        async with destination.begin() as transaction:
            for name in names:
                table = Base.metadata.tables[name]
                rows = source_rows[name]
                if name == Employee.__tablename__:
                    rows = [{**row, "manager_id": None} for row in rows]
                if not rows:
                    continue
                statement = pg_insert(table).values(rows)
                primary_keys = [column.name for column in table.primary_key.columns]
                updates = {column.name: getattr(statement.excluded, column.name) for column in table.columns if column.name not in primary_keys}
                await transaction.execute(statement.on_conflict_do_update(index_elements=primary_keys, set_=updates))

            employee_table = Base.metadata.tables[Employee.__tablename__]
            for row in source_rows[Employee.__tablename__]:
                await transaction.execute(
                    update(employee_table).where(employee_table.c.id == row["id"]).values(manager_id=row["manager_id"])
                )

        after_postgres = await real_counts(destination, names)
        print("postgres_after=" + json.dumps(after_postgres, sort_keys=True))
    finally:
        await sqlite.dispose()
        await destination.dispose()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    asyncio.run(migrate(args.dry_run))


if __name__ == "__main__":
    main()
