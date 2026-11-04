"""회원관리. 가입 검증은 accounts를 재사용한다."""
import sqlite3

from .. import errors
from ..db import hasher, transaction
from . import accounts

STATUSES = ("pending", "approved", "rejected", "disabled")
PUBLIC = "emp_no, last_name, first_name, display_name, email, phone, birth_date, status, totp_enabled, created_at"


def _not_found() -> errors.AppError:
    return errors.not_found("USER_NOT_FOUND", "사용자를 찾을 수 없습니다.")


def _ensure(conn: sqlite3.Connection, emp_no: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM users WHERE emp_no = ?", (emp_no,)).fetchone()
    if not row:
        raise _not_found()
    return row


def _groups(conn: sqlite3.Connection, emp_no: str) -> list[dict]:
    rows = conn.execute(
        "SELECT g.AuthCd code, g.AuthNm name FROM TB_SYS_AuthUser u JOIN TB_SYS_AuthGroup g ON g.AuthCd = u.AuthCd"
        " WHERE u.EmpNo = ? ORDER BY g.AuthCd",
        (emp_no,),
    )
    return [dict(r) for r in rows]


def _view(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    return {**dict(row), "totp_enabled": bool(row["totp_enabled"]), "groups": _groups(conn, row["emp_no"])}


def get_user(conn: sqlite3.Connection, emp_no: str) -> dict:
    row = conn.execute(f"SELECT {PUBLIC} FROM users WHERE emp_no = ?", (emp_no,)).fetchone()
    if not row:
        raise _not_found()
    return _view(conn, row)


def list_users(conn: sqlite3.Connection, status: str = "", q: str = "") -> dict:
    clauses, args = ["1=1"], []
    if status:
        clauses.append("status = ?")
        args.append(status)
    if q:
        clauses.append("instr(lower(emp_no || char(10) || display_name || char(10) || email || char(10) || phone), lower(?)) > 0")
        args.append(q)
    rows = conn.execute(
        f"SELECT {PUBLIC} FROM users WHERE {' AND '.join(clauses)} ORDER BY created_at, emp_no", args
    ).fetchall()
    pending = conn.execute("SELECT COUNT(*) FROM users WHERE status = 'pending'").fetchone()[0]
    return {"users": [_view(conn, r) for r in rows], "total": len(rows), "pending": pending}


def auth_groups(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT AuthCd code, AuthNm name FROM TB_SYS_AuthGroup ORDER BY AuthCd")]


def _check_status(status: str) -> None:
    if status not in STATUSES:
        raise errors.validation("status", "허용되지 않는 상태입니다.")


def _check_groups(conn: sqlite3.Connection, groups: list[str]) -> None:
    known = {g["code"] for g in auth_groups(conn)}
    if not set(groups) <= known:
        raise errors.validation("groups", "존재하지 않는 권한 그룹입니다.")


def _set_groups(conn: sqlite3.Connection, emp_no: str, groups: list[str]) -> None:
    conn.execute("DELETE FROM TB_SYS_AuthUser WHERE EmpNo = ?", (emp_no,))
    conn.executemany("INSERT INTO TB_SYS_AuthUser (AuthCd, EmpNo) VALUES (?,?)", [(g, emp_no) for g in dict.fromkeys(groups)])


def _otp_not_enrolled() -> errors.AppError:
    return errors.AppError(409, "OTP_NOT_ENROLLED", "등록된 OTP가 없는 사용자는 2차 인증을 켤 수 없습니다.")


def create_user(conn: sqlite3.Connection, data: dict) -> dict:
    _check_status(data["status"])
    _check_groups(conn, data["groups"])
    if data["totp_enabled"]:
        raise _otp_not_enrolled()
    account = {**data, "password_confirm": data["password"] if data["password_confirm"] is None else data["password_confirm"]}
    accounts.create(conn, account, data["status"], extra=lambda c: _set_groups(c, data["emp_no"], data["groups"]))
    return get_user(conn, data["emp_no"])


def update_user(conn: sqlite3.Connection, emp_no: str, payload: dict) -> dict:
    row = _ensure(conn, emp_no)
    if payload.get("emp_no", emp_no) != emp_no:
        raise errors.validation("emp_no", "아이디는 변경할 수 없습니다.")
    fields = ("last_name", "first_name", "birth_date", "phone", "email")
    data = {field: payload[field] if payload.get(field) is not None else row[field] for field in fields}
    accounts.validate(data, with_password=False)
    password = payload.get("password")
    if password and len(password) < 8:
        raise errors.validation("password", "비밀번호는 8자 이상 입력하세요.")
    status = payload.get("status") or row["status"]
    _check_status(status)
    groups = payload.get("groups")
    if groups is not None:
        _check_groups(conn, groups)
    totp = payload.get("totp_enabled")
    totp = bool(row["totp_enabled"]) if totp is None else totp
    if totp and not row["totp_secret"]:
        raise _otp_not_enrolled()
    password_hash = hasher.hash(password) if password else row["password_hash"]
    last, first = data["last_name"].strip(), data["first_name"].strip()
    with transaction(conn):
        accounts.check_duplicates(conn, data, exclude=emp_no)
        conn.execute(
            "UPDATE users SET last_name = ?, first_name = ?, display_name = ?, birth_date = ?, phone = ?, email = ?,"
            " password_hash = ?, status = ?, totp_enabled = ? WHERE emp_no = ?",
            (
                last, first, last + first, data["birth_date"], accounts.normalize_phone(data["phone"]), data["email"],
                password_hash, status, int(totp), emp_no,
            ),
        )
        if groups is not None:
            _set_groups(conn, emp_no, groups)
    return get_user(conn, emp_no)


def _ensure_pending(conn: sqlite3.Connection, emp_no: str) -> None:
    if _ensure(conn, emp_no)["status"] != "pending":
        raise errors.AppError(409, "INVALID_STATUS", "승인 대기 상태가 아닙니다.")


def approve(conn: sqlite3.Connection, emp_no: str, groups: list[str]) -> dict:
    _ensure_pending(conn, emp_no)
    if not groups:
        raise errors.validation("groups", "승인 시 권한 그룹을 1개 이상 지정하세요.")
    _check_groups(conn, groups)
    with transaction(conn):
        conn.execute("UPDATE users SET status = 'approved' WHERE emp_no = ?", (emp_no,))
        _set_groups(conn, emp_no, groups)
    return get_user(conn, emp_no)


def reject(conn: sqlite3.Connection, emp_no: str) -> dict:
    _ensure_pending(conn, emp_no)
    with transaction(conn):
        conn.execute("UPDATE users SET status = 'rejected' WHERE emp_no = ?", (emp_no,))
    return get_user(conn, emp_no)


def delete_user(conn: sqlite3.Connection, emp_no: str, actor: str) -> None:
    _ensure(conn, emp_no)
    if emp_no == actor:
        raise errors.AppError(409, "SELF_DELETE", "로그인 중인 본인 계정은 삭제할 수 없습니다.")
    with transaction(conn):
        conn.execute("DELETE FROM users WHERE emp_no = ?", (emp_no,))
