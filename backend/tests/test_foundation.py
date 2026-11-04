import sqlite3

import pytest
from argon2 import PasswordHasher

from app import db


def count(conn, table, where="1=1"):
    return conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0]


def test_seed_counts(conn):
    expected = {
        "users": 6, "TB_MST_Hull": 5, "TB_MST_Block": 17, "TB_PRC_Plan": 83, "TB_PRC_PlanDep": 79,
        "TB_PRC_Progress": 60, "TB_DWG_Drawing": 47, "TB_DWG_Revision": 79, "TB_DWG_Approval": 72,
        "TB_DWG_PlanLink": 45,
    }
    assert {t: count(conn, t) for t in expected} == expected


def test_seed_plan_status(conn):
    rows = conn.execute("SELECT PlanStatus s, COUNT(*) c FROM TB_PRC_Plan GROUP BY 1").fetchall()
    assert {r["s"]: r["c"] for r in rows} == {"PLAN": 39, "WORK": 7, "DONE": 36, "DELAY": 1}


def test_passwords_are_hashed(conn):
    row = conn.execute("SELECT password_hash FROM users WHERE emp_no='admin'").fetchone()
    assert PasswordHasher().verify(row[0], "admin1234")


def test_init_is_repeatable(conn):
    assert db.migrate(conn) == []
    conn.execute("DELETE FROM TB_MST_Hull WHERE HullNo='8001'")
    assert db.seed(conn) is False
    assert count(conn, "TB_MST_Hull") == 4
    assert count(conn, "schema_migrations") == 1


def test_connection_pragmas(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_cascade_delete_hull(conn):
    conn.execute("DELETE FROM TB_MST_Hull WHERE HullNo='8001'")
    assert count(conn, "TB_PRC_Plan", "HullNo='8001'") == 0
    assert count(conn, "TB_DWG_Drawing", "HullNo='8001'") == 0
    assert count(conn, "TB_DWG_Approval", "DrawingId NOT IN (SELECT DrawingId FROM TB_DWG_Drawing)") == 0


def test_phone_unique_ignores_hyphen(conn):
    conn.execute("UPDATE users SET phone='01011110001' WHERE emp_no='admin'")
    phone = conn.execute("SELECT phone FROM users WHERE emp_no='park.pm'").fetchone()[0]
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE users SET phone=? WHERE emp_no='admin'", (phone.replace("-", ""),))


def test_transaction_rolls_back(conn):
    with pytest.raises(RuntimeError):
        with db.transaction(conn):
            conn.execute("DELETE FROM TB_MST_Hull")
            raise RuntimeError
    assert count(conn, "TB_MST_Hull") == 5
