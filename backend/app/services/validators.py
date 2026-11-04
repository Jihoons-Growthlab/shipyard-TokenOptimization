"""입력 검증 공통 함수."""
import re
import sqlite3
from datetime import date

from .. import errors

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
DATE_MESSAGE = "날짜 형식(YYYY-MM-DD)이 올바르지 않습니다."


def is_date(value: str | None) -> bool:
    if not value or not DATE_RE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def check_date(value: str | None, field: str) -> None:
    if value and not is_date(value):
        raise errors.validation(field, DATE_MESSAGE)


def check_code(conn: sqlite3.Connection, group: str, value: str | None, field: str) -> None:
    if value and not conn.execute(
        "SELECT 1 FROM TB_SYS_Code WHERE CodeGroup = ? AND Code = ? AND UseYN = 1", (group, value)
    ).fetchone():
        raise errors.validation(field, "허용되지 않는 코드값입니다.")


def check_non_negative(value: float | None, field: str) -> None:
    if value is not None and value < 0:
        raise errors.validation(field, "0 이상의 값을 입력하세요.")


def blank_to_none(data: dict) -> dict:
    return {key: (None if isinstance(value, str) and not value.strip() else value) for key, value in data.items()}
