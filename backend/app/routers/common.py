import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import current_user

router = APIRouter(prefix="/api", tags=["common"])


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/codes", dependencies=[Depends(current_user)])
def codes(conn: sqlite3.Connection = Depends(get_db)):
    result: dict[str, list[dict]] = {}
    rows = conn.execute("SELECT CodeGroup, Code, CodeName FROM TB_SYS_Code WHERE UseYN = 1 ORDER BY CodeGroup, Seq")
    for row in rows:
        result.setdefault(row["CodeGroup"], []).append({"code": row["Code"], "name": row["CodeName"]})
    return result


@router.get("/procs", dependencies=[Depends(current_user)])
def procs(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT ProcCd, ProcNm, ProcGroup, StdDays, Seq FROM TB_PRC_Proc WHERE UseYN = 1 ORDER BY Seq")
    return [
        {"proc_cd": r["ProcCd"], "proc_nm": r["ProcNm"], "proc_group": r["ProcGroup"], "std_days": r["StdDays"], "seq": r["Seq"]}
        for r in rows
    ]


@router.get("/users/options", dependencies=[Depends(current_user)])
def user_options(conn: sqlite3.Connection = Depends(get_db)):
    rows = conn.execute("SELECT emp_no, display_name FROM users WHERE status = 'approved' ORDER BY display_name, emp_no")
    return [dict(r) for r in rows]
