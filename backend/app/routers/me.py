import sqlite3

from fastapi import APIRouter, Depends

from .. import errors
from ..db import get_db, transaction
from ..deps import LEVELS, Principal, current_user, menu_level
from ..schemas import MenuAccessIn
from ..services import auth, weather

router = APIRouter(prefix="/api", tags=["me"])


@router.get("/me/menu")
def menu(user: Principal = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute(
        "SELECT m.MenuId, m.ParentId, m.Title, m.TokenUrl, m.Seq, MAX(CASE a.AuthGbn"
        "  WHEN 'Admin' THEN 3 WHEN 'Write' THEN 2 ELSE 1 END) level"
        " FROM TB_SYS_MenuInfo m"
        " JOIN TB_SYS_AuthMenu a ON a.MenuId = m.MenuId"
        " JOIN TB_SYS_AuthUser u ON u.AuthCd = a.AuthCd AND u.EmpNo = ?"
        " WHERE m.UseYN = 1 GROUP BY m.MenuId ORDER BY m.Seq",
        (user.emp_no,),
    ).fetchall()
    visible = {r["MenuId"]: r for r in rows}

    def parents_visible(row: sqlite3.Row) -> bool:
        parent = row["ParentId"]
        return parent is None or (parent in visible and parents_visible(visible[parent]))

    names = {value: key for key, value in LEVELS.items()}
    return [
        {
            "menu_id": r["MenuId"], "parent_id": r["ParentId"], "title": r["Title"], "token": r["TokenUrl"],
            "seq": r["Seq"], "level": r["level"], "auth_gbn": names[r["level"]], "can_write": r["level"] >= 2,
        }
        for r in rows
        if parents_visible(r)
    ]


@router.post("/me/menu-access", status_code=204)
def menu_access(
    body: MenuAccessIn, user: Principal = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)
):
    if menu_level(conn, user.emp_no, body.menu_id) < 1:
        raise errors.AppError(403, "FORBIDDEN", "접근 권한이 없습니다.", {"menu_id": body.menu_id})
    with transaction(conn):
        conn.execute(
            "INSERT INTO TB_SYS_LogMenuAccess (MenuId, LogId, InDt) VALUES (?,?,?)",
            (body.menu_id, user.log_id, auth.utc_now()),
        )


@router.get("/weather", dependencies=[Depends(current_user)])
def get_weather(region: str = "울산"):
    return weather.get(region)
