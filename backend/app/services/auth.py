"""로그인, OTP, 세션."""
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone

from argon2.exceptions import Argon2Error, InvalidHashError

from .. import config, errors
from ..db import hasher, transaction
from . import tokens, totp

MAX_OTP_FAILURES = 5
DUMMY_HASH = hasher.hash("timing-equalizer")
STATUS_ERRORS = {
    "pending": ("ACCOUNT_PENDING", "관리자 승인 대기 중인 계정입니다."),
    "rejected": ("ACCOUNT_REJECTED", "가입이 반려된 계정입니다."),
    "disabled": ("ACCOUNT_DISABLED", "사용이 중지된 계정입니다."),
}

# 단일 프로세스 기준 메모리 상태 (명세 허용)
otp_failures: dict[str, int] = defaultdict(int)
otp_last_step: dict[str, int] = {}


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _verify_password(password_hash: str, password: str) -> bool:
    try:
        return hasher.verify(password_hash, password)
    except (Argon2Error, InvalidHashError):
        return False


def profile(conn: sqlite3.Connection, emp_no: str) -> dict:
    user = conn.execute(
        "SELECT emp_no, display_name, email, status, totp_enabled FROM users WHERE emp_no = ?", (emp_no,)
    ).fetchone()
    groups = conn.execute(
        "SELECT g.AuthCd code, g.AuthNm name FROM TB_SYS_AuthUser u JOIN TB_SYS_AuthGroup g ON g.AuthCd = u.AuthCd"
        " WHERE u.EmpNo = ? ORDER BY g.AuthCd",
        (emp_no,),
    ).fetchall()
    return {
        **dict(user),
        "totp_enabled": bool(user["totp_enabled"]),
        "groups": [dict(g) for g in groups],
        "today": config.TODAY_ISO,
    }


def _session(conn: sqlite3.Connection, emp_no: str, ip: str | None) -> dict:
    with transaction(conn):
        cursor = conn.execute(
            "INSERT INTO TB_SYS_LogAccess (UserId, LoginDt, IpAddress) VALUES (?,?,?)", (emp_no, utc_now(), ip)
        )
    ttl = config.token_ttl()
    return {
        "otp_required": False,
        "access_token": tokens.issue(emp_no, "full", ttl, lid=cursor.lastrowid),
        "token_type": "bearer",
        "expires_in": ttl,
        "user": profile(conn, emp_no),
    }


def login(conn: sqlite3.Connection, emp_no: str, password: str, ip: str | None) -> dict:
    row = conn.execute("SELECT password_hash, status, totp_enabled FROM users WHERE emp_no = ?", (emp_no,)).fetchone()
    if not _verify_password(row["password_hash"] if row else DUMMY_HASH, password) or not row:
        raise errors.AppError(401, "INVALID_CREDENTIALS", "아이디 또는 비밀번호가 올바르지 않습니다.")
    if row["status"] in STATUS_ERRORS:
        raise errors.AppError(403, *STATUS_ERRORS[row["status"]])
    if row["totp_enabled"]:
        ttl = config.otp_token_ttl()
        return {"otp_required": True, "otp_token": tokens.issue(emp_no, "otp", ttl), "expires_in": ttl}
    return _session(conn, emp_no, ip)


def verify_otp(conn: sqlite3.Connection, otp_token: str, code: str, ip: str | None) -> dict:
    claims = tokens.decode(otp_token, "otp")
    emp_no, jti = claims["sub"], claims["jti"]
    row = conn.execute(
        "SELECT totp_secret FROM users WHERE emp_no = ? AND status = 'approved' AND totp_enabled = 1", (emp_no,)
    ).fetchone()
    if not row or not row["totp_secret"]:
        raise errors.unauthorized()
    if otp_failures[jti] >= MAX_OTP_FAILURES:
        raise errors.AppError(429, "OTP_LOCKED", "인증 시도 횟수를 초과했습니다. 다시 로그인하세요.")
    step = totp.matching_step(row["totp_secret"], code)
    if step is None or step <= otp_last_step.get(emp_no, -1):
        otp_failures[jti] += 1
        raise errors.AppError(400, "OTP_INVALID", "인증 코드가 올바르지 않습니다.")
    otp_last_step[emp_no] = step
    otp_failures.pop(jti, None)
    return _session(conn, emp_no, ip)


def logout(conn: sqlite3.Connection, log_id: int) -> None:
    with transaction(conn):
        conn.execute("UPDATE TB_SYS_LogAccess SET LogoutDt = ? WHERE LogId = ?", (utc_now(), log_id))
