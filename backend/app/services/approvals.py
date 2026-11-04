"""결재함과 결재 처리."""
import sqlite3
from datetime import datetime

from .. import config, errors
from ..db import transaction
from ..deps import menu_level
from . import drawings, plans, rules

WAITING_SQL = (
    "SELECT a.ApprovalId, a.DrawingId, d.DrawingNo, d.DrawingNm, a.RevNo, a.StepNo, r.ChangeDesc"
    " FROM TB_DWG_Approval a JOIN TB_DWG_Drawing d ON d.DrawingId = a.DrawingId"
    " JOIN TB_DWG_Revision r ON r.DrawingId = a.DrawingId AND r.RevNo = a.RevNo"
    " WHERE a.ApproverEmpNo = ? AND a.Result = 'WAIT' AND r.RevStatus = 'REVIEW'"
    " AND r.RevNo = (SELECT MAX(x.RevNo) FROM TB_DWG_Revision x WHERE x.DrawingId = a.DrawingId)"
    " AND NOT EXISTS (SELECT 1 FROM TB_DWG_Approval p WHERE p.DrawingId = a.DrawingId AND p.RevNo = a.RevNo"
    "   AND p.StepNo < a.StepNo AND p.Result <> 'APPROVE')"
    " ORDER BY a.ApprovalId"
)


def waiting(conn: sqlite3.Connection, emp_no: str) -> list[dict]:
    return [
        {
            "approval_id": r["ApprovalId"], "drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"],
            "drawing_nm": r["DrawingNm"], "rev_no": r["RevNo"], "step_no": r["StepNo"], "change_desc": r["ChangeDesc"],
        }
        for r in conn.execute(WAITING_SQL, (emp_no,))
    ]


def ready(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT d.DrawingId, d.DrawingNo, d.DrawingNm, r.RevNo FROM TB_DWG_Drawing d JOIN TB_DWG_Revision r"
        " ON r.DrawingId = d.DrawingId AND r.RevNo = (SELECT MAX(x.RevNo) FROM TB_DWG_Revision x WHERE x.DrawingId = d.DrawingId)"
        " WHERE r.RevStatus = 'APPROVED' ORDER BY d.DrawingId"
    ).fetchall()
    result = []
    for row in rows:
        linked = conn.execute(
            f"{plans.PLAN_SELECT} JOIN TB_DWG_PlanLink l ON l.PlanId = p.PlanId"
            " WHERE l.DrawingId = ? AND p.PlanStatus = 'PLAN'",
            (row["DrawingId"],),
        ).fetchall()
        result.append({
            "drawing_id": row["DrawingId"], "drawing_no": row["DrawingNo"], "drawing_nm": row["DrawingNm"], "rev_no": row["RevNo"],
            "effect_plans": [plans.label(p["BlockCd"], p["ProcNm"]) for p in sorted(linked, key=plans.sort_key)],
        })
    return result


def inbox(conn: sqlite3.Connection, emp_no: str) -> dict:
    return {"waiting": waiting(conn, emp_no), "ready": ready(conn), "can_issue": menu_level(conn, emp_no, "M31") >= 2}


def decide(conn: sqlite3.Connection, approval_id: int, result: str, comment: str | None, emp_no: str) -> dict:
    if result not in ("APPROVE", "REJECT"):
        raise errors.validation("result", "결재 결과는 APPROVE 또는 REJECT 이어야 합니다.")
    comment = (comment or "").strip()
    if result == "REJECT" and not comment:
        raise errors.validation("comment", "반려 시 의견을 입력하세요.")
    with transaction(conn):
        row = conn.execute("SELECT * FROM TB_DWG_Approval WHERE ApprovalId = ?", (approval_id,)).fetchone()
        if not row:
            raise errors.not_found("APPROVAL_NOT_FOUND", "결재 건을 찾을 수 없습니다.")
        if row["ApproverEmpNo"] != emp_no:
            raise errors.AppError(403, "NOT_ASSIGNED_APPROVER", "본인에게 지정된 결재 건이 아닙니다.")
        if row["Result"] != "WAIT":
            raise errors.AppError(409, "ALREADY_DECIDED", "이미 처리된 결재 건입니다.")
        if approval_id not in {w["approval_id"] for w in waiting(conn, emp_no)}:
            raise errors.AppError(409, "NOT_CURRENT_STEP", "결재 순서가 아니거나 최신 검토중 리비전이 아닙니다.")
        drawing_id, rev_no = row["DrawingId"], row["RevNo"]
        act_dt = f"{config.TODAY_ISO} {datetime.now().strftime('%H:%M')}"
        conn.execute(
            "UPDATE TB_DWG_Approval SET Result = ?, Comment = ?, ActDt = ? WHERE ApprovalId = ?",
            (result, comment or "승인", act_dt, approval_id),
        )
        if result == "REJECT":
            conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ? AND Result = 'WAIT'", (drawing_id, rev_no))
            drawings.set_status(conn, drawing_id, rev_no, "DRAFT")
        elif not conn.execute(
            "SELECT 1 FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ? AND Result <> 'APPROVE'", (drawing_id, rev_no)
        ).fetchone():
            drawings.set_status(conn, drawing_id, rev_no, "APPROVED")
        hull = conn.execute("SELECT HullNo FROM TB_DWG_Drawing WHERE DrawingId = ?", (drawing_id,)).fetchone()
        rules.recalc_hull(conn, hull["HullNo"])
    return {"approval_id": approval_id, "result": result, "waiting": waiting(conn, emp_no), "ready": ready(conn)}


def history(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT a.*, d.DrawingNo, u.display_name ApproverNm FROM TB_DWG_Approval a"
        " JOIN TB_DWG_Drawing d ON d.DrawingId = a.DrawingId LEFT JOIN users u ON u.emp_no = a.ApproverEmpNo"
        " WHERE a.Result <> 'WAIT' ORDER BY a.ActDt DESC, a.ApprovalId DESC LIMIT 10"
    )
    return [
        {
            "approval_id": r["ApprovalId"], "act_dt": r["ActDt"], "drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"],
            "rev_no": r["RevNo"], "step_no": r["StepNo"], "approver_emp_no": r["ApproverEmpNo"], "approver_nm": r["ApproverNm"],
            "result": r["Result"], "comment": r["Comment"],
        }
        for r in rows
    ]
