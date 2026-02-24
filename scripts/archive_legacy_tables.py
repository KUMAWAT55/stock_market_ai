#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import re
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

DEFAULT_ACTIVE_TABLES = {
    "realtime_ticks",
    "ohlcv_candles",
    "model_registry",
    "prediction_events",
    "risk_events",
    "compliance_audit_trail",
    "simulated_backtest_metrics",
    "engine_heartbeat",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Move legacy public tables into a backup schema while keeping active realtime tables in public."
        )
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("DATABASE_URL", ""),
        help="PostgreSQL SQLAlchemy URL. Defaults to DATABASE_URL env var.",
    )
    parser.add_argument(
        "--backup-schema",
        default=f"backup_archive_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}",
        help="Target backup schema name.",
    )
    parser.add_argument(
        "--schema",
        default="public",
        help="Source schema to inspect. Default: public",
    )
    parser.add_argument(
        "--keep-table",
        action="append",
        default=[],
        help="Extra table name to keep in source schema. Can be repeated.",
    )
    parser.add_argument(
        "--include-table",
        action="append",
        default=[],
        help=(
            "Optional explicit table allowlist to archive. If set, only these tables are moved (intersection with detected tables)."
        ),
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions only (default behavior if --execute is not passed).",
    )
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply schema move changes.",
    )
    return parser.parse_args()


def load_active_tables_from_schema_file() -> set[str]:
    schema_path = Path(__file__).resolve().parents[1] / "database" / "schema.sql"
    if not schema_path.exists():
        return set(DEFAULT_ACTIVE_TABLES)

    content = schema_path.read_text(encoding="utf-8")
    found = set(
        match.group(1)
        for match in re.finditer(
            r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            content,
            flags=re.IGNORECASE,
        )
    )
    return found or set(DEFAULT_ACTIVE_TABLES)


def list_tables(engine: Engine, schema: str) -> list[str]:
    query = text(
        """
        SELECT tablename
        FROM pg_tables
        WHERE schemaname = :schema
        ORDER BY tablename
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(query, {"schema": schema}).fetchall()
    return [row[0] for row in rows]


def list_owned_sequences(engine: Engine, schema: str, table: str) -> list[tuple[str, str]]:
    query = text(
        """
        SELECT seq_ns.nspname AS sequence_schema, seq.relname AS sequence_name
        FROM pg_class AS seq
        JOIN pg_depend AS dep
          ON dep.objid = seq.oid
         AND dep.classid = 'pg_class'::regclass
         AND dep.refclassid = 'pg_class'::regclass
        JOIN pg_class AS tbl
          ON tbl.oid = dep.refobjid
        JOIN pg_namespace AS tbl_ns
          ON tbl_ns.oid = tbl.relnamespace
        JOIN pg_namespace AS seq_ns
          ON seq_ns.oid = seq.relnamespace
        WHERE seq.relkind = 'S'
          AND tbl_ns.nspname = :schema
          AND tbl.relname = :table
        ORDER BY seq.relname
        """
    )
    with engine.begin() as conn:
        rows = conn.execute(query, {"schema": schema, "table": table}).fetchall()
    return [(row[0], row[1]) for row in rows]


def move_tables(
    engine: Engine,
    source_schema: str,
    backup_schema: str,
    tables: list[str],
) -> None:
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{backup_schema}"'))
        for table in tables:
            conn.execute(text(f'ALTER TABLE "{source_schema}"."{table}" SET SCHEMA "{backup_schema}"'))


def move_sequences(
    engine: Engine,
    backup_schema: str,
    owned_sequences: list[tuple[str, str]],
) -> None:
    if not owned_sequences:
        return
    with engine.begin() as conn:
        for schema, sequence in owned_sequences:
            if schema == backup_schema:
                continue
            conn.execute(text(f'ALTER SEQUENCE IF EXISTS "{schema}"."{sequence}" SET SCHEMA "{backup_schema}"'))


def main() -> int:
    args = parse_args()
    if not args.database_url:
        print("Error: missing database URL. Pass --database-url or set DATABASE_URL.")
        return 1

    active_tables = load_active_tables_from_schema_file()
    active_tables.update({name.strip() for name in args.keep_table if name.strip()})

    engine = create_engine(args.database_url, pool_pre_ping=True, future=True)
    source_tables = list_tables(engine, args.schema)

    include_tables = {name.strip() for name in args.include_table if name.strip()}
    candidates = [table for table in source_tables if table not in active_tables]
    if include_tables:
        candidates = [table for table in candidates if table in include_tables]

    print("Source schema:", args.schema)
    print("Backup schema:", args.backup_schema)
    print("Active tables (kept in source):", ", ".join(sorted(active_tables)))
    print("Detected tables in source:", ", ".join(source_tables) if source_tables else "(none)")
    print("Archive candidates:", ", ".join(candidates) if candidates else "(none)")

    if not candidates:
        print("Nothing to archive.")
        return 0

    seqs: list[tuple[str, str]] = []
    for table in candidates:
        seqs.extend(list_owned_sequences(engine, args.schema, table))

    if args.dry_run or not args.execute:
        print("\nDry run mode. Planned SQL:")
        print(f'CREATE SCHEMA IF NOT EXISTS "{args.backup_schema}";')
        for table in candidates:
            print(f'ALTER TABLE "{args.schema}"."{table}" SET SCHEMA "{args.backup_schema}";')
        for schema, sequence in seqs:
            print(f'ALTER SEQUENCE "{schema}"."{sequence}" SET SCHEMA "{args.backup_schema}";')
        print("\nRun with --execute to apply.")
        return 0

    move_tables(engine, args.schema, args.backup_schema, candidates)
    move_sequences(engine, args.backup_schema, seqs)
    print(f"Archived {len(candidates)} tables into schema '{args.backup_schema}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
