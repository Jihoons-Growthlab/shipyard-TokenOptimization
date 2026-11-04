"""계정 검증·생성. 가입과 회원관리가 공유한다."""
import re
import sqlite3

from .. import config, errors
from ..db import hasher, transaction
from .validators import is_date

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
PHONE_RE = re.compile(r"^01\d-?\d{3,4}-?\d{4}$")
EMP_NO_RE = re.compile(r"^[A-Za-z0-9._-]{4,20}$")


def normalize_phone(phone: str) -> str:
    digits = phone.replace("-", "")
    return f"{digits[:3]}-{digits[3:-4]}-{digits[-4:]}"


def validate(data: dict, *, with_password: bool = True) -> None:
    """가입 검증표 순서대로 검사한다."""
    if not data["last_name"].strip() or not data["first_name"].strip():
        raise errors.validation("name", "성과 이름을 입력하세요.")
    if not is_date(data["birth_date"]):
        raise errors.validation("birth_date", "생년월일을 입력하세요.")
    if not EMAIL_RE.match(data["email"]):
        raise errors.validation("email", "이메일 형식이 올바르지 않습니다.")
    if not PHONE_RE.match(data["phone"]):
        raise errors.validation("phone", "전화번호 형식(010-0000-0000)이 올바르지 않습니다.")
    if "emp_no" in data and not EMP_NO_RE.match(data["emp_no"]):
        raise errors.validation("emp_no", "아이디는 영문/숫자/._- 조합 4~20자입니다.")
    if with_password:
        if len(data["password"]) < 8:
            raise errors.validation("password", "비밀번호는 8자 이상 입력하세요.")
        if data["password"] != data["password_confirm"]:
            raise errors.validation("password_confirm", "비밀번호 확인이 일치하지 않습니다.")


def check_duplicates(conn: sqlite3.Connection, data: dict, *, exclude: str | None = None) -> None:
    def taken(where: str, *args) -> bool:
        sql = f"SELECT 1 FROM users WHERE {where} AND emp_no IS NOT ?"
        return conn.execute(sql, (*args, exclude)).fetchone() is not None

    if "emp_no" in data and taken("emp_no = ?", data["emp_no"]):
        raise errors.duplicate("이미 사용 중인 아이디입니다.", field="emp_no")
    if taken("lower(email) = lower(?)", data["email"]):
        raise errors.duplicate("이미 등록된 이메일입니다.", field="email")
    if taken("replace(phone,'-','') = ?", data["phone"].replace("-", "")):
        raise errors.duplicate("이미 등록된 전화번호입니다.", field="phone")


def create(conn: sqlite3.Connection, data: dict, status: str = "pending", *, extra=None) -> None:
    """extra(conn)는 같은 트랜잭션에서 실행한다(그룹 할당 등)."""
    validate(data)
    password_hash = hasher.hash(data["password"])
    last, first = data["last_name"].strip(), data["first_name"].strip()
    with transaction(conn):
        check_duplicates(conn, data)
        conn.execute(
            "INSERT INTO users (id, email, password_hash, display_name, emp_no, status, last_name, first_name,"
            " birth_date, phone, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                f"u-{data['emp_no']}", data["email"], password_hash, last + first, data["emp_no"], status,
                last, first, data["birth_date"], normalize_phone(data["phone"]), config.TODAY_ISO,
            ),
        )
        if extra:
            extra(conn)
