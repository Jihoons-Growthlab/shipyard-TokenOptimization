"""SQLite 연결, 트랜잭션, 마이그레이션, 시드."""
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from argon2 import PasswordHasher

from . import config

hasher = PasswordHasher()


def connect(path: Path | None = None) -> sqlite3.Connection:
    path = path or config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False, timeout=5)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")


def migrate(conn: sqlite3.Connection) -> list[str]:
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_migrations ("
        "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    done = {r["version"] for r in conn.execute("SELECT version FROM schema_migrations")}
    applied = []
    for file in sorted(config.MIGRATIONS_DIR.glob("*.sql")):
        if file.stem in done:
            continue
        script = f"BEGIN;\n{file.read_text()}\nINSERT INTO schema_migrations(version) VALUES ('{file.stem}');\nCOMMIT;"
        try:
            conn.executescript(script)
        except sqlite3.Error:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        applied.append(file.stem)
    return applied


def seed(conn: sqlite3.Connection) -> bool:
    """시드는 한 트랜잭션으로 적재하므로 코드 그룹이 있으면 적재 완료 상태다."""
    if conn.execute("SELECT 1 FROM TB_SYS_CodeGroup LIMIT 1").fetchone():
        return False
    data = json.loads(config.SEED_PATH.read_text())
    with transaction(conn):
        conn.execute("PRAGMA defer_foreign_keys=ON")
        for table, content in data.items():
            columns, rows = content["columns"], content["rows"]
            if table == "users":
                index = columns.index("demo_password")
                columns = [c for c in columns if c != "demo_password"] + ["password_hash"]
                rows = [r[:index] + r[index + 1 :] + [hasher.hash(r[index])] for r in rows]
            sql = f"INSERT INTO {table} ({','.join(columns)}) VALUES ({','.join('?' * len(columns))})"
            conn.executemany(sql, rows)
    return True
