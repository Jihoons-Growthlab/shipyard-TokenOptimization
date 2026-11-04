"""인증·권한 의존성. 권한은 요청마다 DB에서 읽는다."""
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Depends, Header

from . import errors
from .db import get_db
from .services import tokens

LEVELS = {"View": 1, "Write": 2, "Admin": 3}


@dataclass
class Principal:
    emp_no: str
    display_name: str
    log_id: int


def bearer(authorization: str = Header(default="")) -> str:
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise errors.unauthorized()
    return token


def current_user(token: str = Depends(bearer), conn: sqlite3.Connection = Depends(get_db)) -> Principal:
    claims = tokens.decode(token, "full")
    row = conn.execute(
        "SELECT u.emp_no, u.display_name FROM users u"
        " JOIN TB_SYS_LogAccess l ON l.UserId = u.emp_no AND l.LogId = ? AND l.LogoutDt IS NULL"
        " WHERE u.emp_no = ? AND u.status = 'approved'",
        (claims.get("lid"), claims["sub"]),
    ).fetchone()
    if not row:
        raise errors.unauthorized()
    return Principal(row["emp_no"], row["display_name"], claims["lid"])


def menu_level(conn: sqlite3.Connection, emp_no: str, menu_id: str) -> int:
    rows = conn.execute(
        "SELECT m.AuthGbn FROM TB_SYS_AuthMenu m JOIN TB_SYS_AuthUser u ON u.AuthCd = m.AuthCd"
        " WHERE u.EmpNo = ? AND m.MenuId = ?",
        (emp_no, menu_id),
    ).fetchall()
    return max((LEVELS[r["AuthGbn"]] for r in rows), default=0)


def require(menu_id: str, level: str = "View") -> Callable[..., Principal]:
    def check(user: Principal = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)) -> Principal:
        if menu_level(conn, user.emp_no, menu_id) < LEVELS[level]:
            raise errors.AppError(403, "FORBIDDEN", "접근 권한이 없습니다.", {"menu_id": menu_id})
        return user

    return check
