import os
import sqlite3
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from core.config import DB_PATH
from data.database import Database


TABLES = [
    "users",
    "categories",
    "clients",
    "sessions",
    "meetings",
    "goals",
    "client_category_budgets",
    "incomes",
    "expenses",
    "expense_installments",
    "debts",
    "debt_installments",
]


def sqlite_rows(sqlite_path, table):
    conn = sqlite3.connect(sqlite_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT * FROM {table} ORDER BY id" if table != "sessions" else f"SELECT * FROM {table}").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def postgres_columns(db, table):
    rows = db.conn.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = ?
        ORDER BY ordinal_position
        """,
        (table,),
    ).fetchall()
    return {row["column_name"] for row in rows}


def copy_table(db, sqlite_path, table):
    rows = sqlite_rows(sqlite_path, table)
    if not rows:
        return 0
    columns = [column for column in rows[0].keys() if column in postgres_columns(db, table)]
    placeholders = ", ".join(["?"] * len(columns))
    column_sql = ", ".join(columns)
    for row in rows:
        values = [row[column] for column in columns]
        db.conn.execute(f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})", values)
    return len(rows)


def reset_sequence(db, table):
    if table == "sessions":
        return
    db.conn.execute(
        f"""
        SELECT setval(
            pg_get_serial_sequence('{table}', 'id'),
            COALESCE((SELECT MAX(id) FROM {table}), 1),
            (SELECT MAX(id) FROM {table}) IS NOT NULL
        )
        """
    )


def main():
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("Defina DATABASE_URL com a connection string do Supabase/Postgres.")

    sqlite_path = Path(os.environ.get("SQLITE_SOURCE_PATH", DB_PATH))
    if not sqlite_path.exists():
        raise SystemExit(f"SQLite nao encontrado: {sqlite_path}")

    db = Database(sqlite_path)
    db.conn.execute("TRUNCATE TABLE " + ", ".join(TABLES) + " RESTART IDENTITY CASCADE")

    copied = {}
    for table in TABLES:
        copied[table] = copy_table(db, sqlite_path, table)

    for table in TABLES:
        reset_sequence(db, table)

    db.conn.commit()
    print({"sqlite": str(sqlite_path), "copied": copied})


if __name__ == "__main__":
    main()
