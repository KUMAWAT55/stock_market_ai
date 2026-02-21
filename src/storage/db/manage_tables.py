import sys

from src.storage.db.connection import engine
from src.storage.db.models import Base


def _resolve_tables(table_names):
    all_tables = Base.metadata.tables
    if not table_names or table_names == ["all"]:
        return [table for _, table in all_tables.items()]

    missing = [name for name in table_names if name not in all_tables]
    if missing:
        available = ", ".join(sorted(all_tables.keys()))
        raise ValueError(
            f"Unknown table(s): {', '.join(missing)}. Available: {available}"
        )

    return [all_tables[name] for name in table_names]


if __name__ == "__main__":
    # Usage:
    # python -m src.storage.db.manage_tables create
    # python -m src.storage.db.manage_tables delete
    # python -m src.storage.db.manage_tables create market_data market_news
    # python -m src.storage.db.manage_tables delete symbols_master
    action = "create"
    table_args = ["all"]

    if len(sys.argv) > 1:
        action = sys.argv[1].lower()
    if len(sys.argv) > 2:
        table_args = [t.strip() for t in sys.argv[2:] if t.strip()]

    if action == "create":
        try:
            tables = _resolve_tables(table_args)
            Base.metadata.create_all(engine, tables=tables)
            print(f"Created table(s): {', '.join([t.name for t in tables])}")
        except ValueError as e:
            print(e)
    elif action == "delete":
        try:
            tables = _resolve_tables(table_args)
            Base.metadata.drop_all(engine, tables=tables)
            print(f"Deleted table(s): {', '.join([t.name for t in tables])}")
        except ValueError as e:
            print(e)
    else:
        print("Unknown action. Use 'create' or 'delete'.")
