"""공정 실적. BR-05 집계 후 BR-03 재계산."""
import sqlite3

from .. import config, errors
from ..db import transaction
from . import hulls, plans, rules
from .validators import is_date

TARGET_STATUSES = ("READY", "WORK", "DELAY")
TARGET_FIELDS = (
    "plan_id", "label", "plan_start_dt", "plan_end_dt", "actual_start_dt", "actual_end_dt", "progress_rate",
    "plan_status", "manager_emp_no", "manager_nm", "drawing_wait",
)


def progress_hulls(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT HullNo, HullNm, HullStatus FROM TB_MST_Hull h WHERE EXISTS"
        " (SELECT 1 FROM TB_PRC_Plan p WHERE p.HullNo = h.HullNo) ORDER BY HullNo"
    ).fetchall()
    default = next((r["HullNo"] for r in rows if r["HullStatus"] == "BUILD"), None)
    return {
        "hulls": [{"hull_no": r["HullNo"], "hull_nm": r["HullNm"], "hull_status": r["HullStatus"]} for r in rows],
        "default_hull_no": default,
    }


def targets(conn: sqlite3.Connection, hull_no: str, include_done: bool) -> dict:
    hulls.ensure(conn, hull_no)
    views = plans.plan_views(conn, "p.HullNo = ?", (hull_no,))
    selected = [p for p in views if include_done or p["plan_status"] in TARGET_STATUSES]
    return {
        "hull_no": hull_no, "today": config.TODAY_ISO,
        "plans": [{field: plan[field] for field in TARGET_FIELDS} for plan in selected],
    }


def detail(conn: sqlite3.Connection, plan_id: int) -> dict:
    plan = plans.get_plan(conn, plan_id)
    rows = conn.execute(
        "SELECT g.*, u.display_name WorkerNm FROM TB_PRC_Progress g LEFT JOIN users u ON u.emp_no = g.WorkerEmpNo"
        " WHERE g.PlanId = ? ORDER BY g.WorkDt DESC",
        (plan_id,),
    )
    history = [
        {
            "progress_id": r["ProgressId"], "plan_id": r["PlanId"], "work_dt": r["WorkDt"], "progress_rate": r["ProgressRate"],
            "man_hour": r["ManHour"], "worker_cnt": r["WorkerCnt"], "worker_emp_no": r["WorkerEmpNo"],
            "worker_nm": r["WorkerNm"], "remark": r["Remark"], "create_dt": r["CreateDt"],
        }
        for r in rows
    ]
    return {"plan": plan, "history": history}


def _sync_plan(conn: sqlite3.Connection, plan_id: int, hull_no: str) -> None:
    """BR-05 후 BR-03. 호출자의 트랜잭션 안에서 실행한다."""
    rows = conn.execute(
        "SELECT WorkDt, ProgressRate FROM TB_PRC_Progress WHERE PlanId = ? ORDER BY WorkDt", (plan_id,)
    ).fetchall()
    rate, start, end = 0, None, None
    if rows:
        rate, start = rows[-1]["ProgressRate"], rows[0]["WorkDt"]
        end = rows[-1]["WorkDt"] if rate >= rules.DONE else None
    conn.execute(
        "UPDATE TB_PRC_Plan SET ProgressRate = ?, ActualStartDt = ?, ActualEndDt = ? WHERE PlanId = ?",
        (rate, start, end, plan_id),
    )
    rules.recalc_hull(conn, hull_no)


def save(conn: sqlite3.Connection, plan_id: int, work_dt: str, data: dict) -> dict:
    plan = plans.ensure(conn, plan_id)
    if not is_date(work_dt):
        raise errors.validation("work_dt", "작업일을 입력하세요.")
    if work_dt > config.TODAY_ISO:
        raise errors.validation("work_dt", "미래 일자의 실적은 입력할 수 없습니다.")
    rate = data.get("progress_rate")
    if rate is None or not 0 <= rate <= 100:
        raise errors.validation("progress_rate", "진척률은 0~100 사이로 입력하세요.")
    worker = data.get("worker_emp_no") or None
    if worker and not conn.execute("SELECT 1 FROM users WHERE emp_no = ? AND status = 'approved'", (worker,)).fetchone():
        raise errors.validation("worker_emp_no", "승인된 회원만 작업자로 지정할 수 있습니다.")
    with transaction(conn):
        conn.execute(
            "INSERT INTO TB_PRC_Progress (PlanId, WorkDt, ProgressRate, ManHour, WorkerCnt, WorkerEmpNo, Remark, CreateDt)"
            " VALUES (?,?,?,?,?,?,?,?) ON CONFLICT (PlanId, WorkDt) DO UPDATE SET ProgressRate = excluded.ProgressRate,"
            " ManHour = excluded.ManHour, WorkerCnt = excluded.WorkerCnt, WorkerEmpNo = excluded.WorkerEmpNo,"
            " Remark = excluded.Remark",
            (plan_id, work_dt, rate, data.get("man_hour"), data.get("worker_cnt"), worker, data.get("remark") or None, config.TODAY_ISO),
        )
        _sync_plan(conn, plan_id, plan["HullNo"])
    return detail(conn, plan_id)


def delete(conn: sqlite3.Connection, progress_id: int) -> dict:
    row = conn.execute(
        "SELECT g.PlanId, p.HullNo FROM TB_PRC_Progress g JOIN TB_PRC_Plan p ON p.PlanId = g.PlanId WHERE g.ProgressId = ?",
        (progress_id,),
    ).fetchone()
    if not row:
        raise errors.not_found("PROGRESS_NOT_FOUND", "실적을 찾을 수 없습니다.")
    with transaction(conn):
        conn.execute("DELETE FROM TB_PRC_Progress WHERE ProgressId = ?", (progress_id,))
        _sync_plan(conn, row["PlanId"], row["HullNo"])
    return detail(conn, row["PlanId"])
