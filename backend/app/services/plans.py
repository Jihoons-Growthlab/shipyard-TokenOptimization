"""공정 계획, 선후행(BR-04), 도면 연계."""
import sqlite3
from collections import defaultdict

from .. import config, errors
from ..db import transaction
from . import hulls, rules
from .validators import blank_to_none, check_date

PLAN_SELECT = (
    "SELECT p.*, b.BlockCd, b.BlockNm, c.ProcNm, c.Seq ProcSeq, u.display_name ManagerNm FROM TB_PRC_Plan p"
    " JOIN TB_PRC_Proc c ON c.ProcCd = p.ProcCd"
    " LEFT JOIN TB_MST_Block b ON b.BlockId = p.BlockId"
    " LEFT JOIN users u ON u.emp_no = p.ManagerEmpNo"
)
LATE_MESSAGE = "선행 공정 종료일이 이 공정의 시작일보다 늦습니다. 그대로 저장할까요?"


def label(block_cd: str | None, proc_nm: str) -> str:
    return f"[{block_cd or '호선'}] {proc_nm}"


def sort_key(row: sqlite3.Row) -> tuple:
    code = row["BlockCd"]
    if code is None:
        block = (2, 0, "")
    elif code.isdigit():
        block = (0, int(code), "")
    else:
        block = (1, 0, code)
    return (*block, row["ProcSeq"], row["PlanId"])


def base_view(row: sqlite3.Row) -> dict:
    """공정 응답의 기본 필드. 실적 화면과 공유한다."""
    return {
        "plan_id": row["PlanId"], "hull_no": row["HullNo"], "block_id": row["BlockId"], "block_cd": row["BlockCd"],
        "block_nm": row["BlockNm"], "proc_cd": row["ProcCd"], "proc_nm": row["ProcNm"],
        "label": label(row["BlockCd"], row["ProcNm"]), "plan_start_dt": row["PlanStartDt"],
        "plan_end_dt": row["PlanEndDt"], "actual_start_dt": row["ActualStartDt"], "actual_end_dt": row["ActualEndDt"],
        "progress_rate": row["ProgressRate"], "plan_status": row["PlanStatus"], "manager_emp_no": row["ManagerEmpNo"],
        "manager_nm": row["ManagerNm"], "remark": row["Remark"], "create_user_id": row["CreateUserId"],
        "create_dt": row["CreateDt"],
    }


def plan_views(conn: sqlite3.Connection, where: str, args: tuple) -> list[dict]:
    rows = sorted(conn.execute(f"{PLAN_SELECT} WHERE {where}", args).fetchall(), key=sort_key)
    ids = [r["PlanId"] for r in rows]
    marks = ",".join("?" * len(ids))
    preds: dict[int, list[int]] = defaultdict(list)
    for dep in conn.execute(f"SELECT PlanId, PredPlanId FROM TB_PRC_PlanDep WHERE PlanId IN ({marks})", ids):
        preds[dep["PlanId"]].append(dep["PredPlanId"])
    blocked = rules.blockers(conn, f"l.PlanId IN ({marks})", tuple(ids))
    views = []
    for row in rows:
        blockers = blocked.get(row["PlanId"], [])
        views.append({
            **base_view(row), "pred_plan_ids": sorted(preds[row["PlanId"]]), "gate_ok": not blockers,
            "blockers": blockers, "drawing_wait": row["PlanStatus"] == "PLAN" and bool(blockers),
        })
    return views


def ensure(conn: sqlite3.Connection, plan_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM TB_PRC_Plan WHERE PlanId = ?", (plan_id,)).fetchone()
    if not row:
        raise errors.not_found("PLAN_NOT_FOUND", "공정을 찾을 수 없습니다.")
    return row


def get_plan(conn: sqlite3.Connection, plan_id: int) -> dict:
    ensure(conn, plan_id)
    return plan_views(conn, "p.PlanId = ?", (plan_id,))[0]


def plan_hulls(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        "SELECT h.HullNo, h.HullNm, COUNT(p.PlanId) c FROM TB_MST_Hull h"
        " LEFT JOIN TB_PRC_Plan p ON p.HullNo = h.HullNo GROUP BY h.HullNo ORDER BY h.HullNo"
    )
    return [{"hull_no": r["HullNo"], "hull_nm": r["HullNm"], "plan_count": r["c"]} for r in rows]


def list_plans(conn: sqlite3.Connection, hull_no: str, block_id: int | None = None) -> dict:
    hulls.ensure(conn, hull_no)
    where, args = "p.HullNo = ?", (hull_no,)
    if block_id is not None:
        where, args = f"{where} AND p.BlockId = ?", (hull_no, block_id)
    plans = plan_views(conn, where, args)
    ids = {p["plan_id"] for p in plans}
    deps = [
        {"plan_id": p["plan_id"], "pred_plan_id": pred}
        for p in plans for pred in p["pred_plan_ids"] if pred in ids
    ]
    progress = rules.progress_by(conn, "HullNo", "HullNo = ?", (hull_no,)).get(hull_no)
    return {"hull_no": hull_no, "hull_progress": progress, "today": config.TODAY_ISO, "plans": plans, "deps": deps}


def _validate(conn: sqlite3.Connection, hull_no: str, data: dict) -> None:
    start, end = data.get("plan_start_dt"), data.get("plan_end_dt")
    if not start or not end:
        raise errors.validation("plan_start_dt", "계획 시작/종료일을 입력하세요.")
    check_date(start, "plan_start_dt")
    check_date(end, "plan_end_dt")
    if end < start:
        raise errors.validation("plan_end_dt", "계획 종료일이 시작일보다 빠릅니다.")
    block_id = data.get("block_id")
    if block_id is not None and not conn.execute(
        "SELECT 1 FROM TB_MST_Block WHERE BlockId = ? AND HullNo = ?", (block_id, hull_no)
    ).fetchone():
        raise errors.validation("block_id", "해당 호선의 블록이 아닙니다.")
    if not conn.execute("SELECT 1 FROM TB_PRC_Proc WHERE ProcCd = ? AND UseYN = 1", (data.get("proc_cd"),)).fetchone():
        raise errors.validation("proc_cd", "허용되지 않는 공정 코드입니다.")
    manager = data.get("manager_emp_no")
    if manager and not conn.execute(
        "SELECT 1 FROM users WHERE emp_no = ? AND status = 'approved'", (manager,)
    ).fetchone():
        raise errors.validation("manager_emp_no", "승인된 회원만 담당자로 지정할 수 있습니다.")


def _check_predecessors(
    conn: sqlite3.Connection, plan_id: int | None, hull_no: str, start: str, pred_ids: list[int], confirm: bool
) -> list[int]:
    pred_ids = list(dict.fromkeys(pred_ids))
    if plan_id in pred_ids:
        raise errors.AppError(400, "PLAN_DEPENDENCY_SELF", "자기 자신을 선행 공정으로 지정할 수 없습니다.", {"field": "pred_plan_ids"})
    marks = ",".join("?" * len(pred_ids))
    rows = conn.execute(f"SELECT PlanId, HullNo, PlanEndDt FROM TB_PRC_Plan WHERE PlanId IN ({marks})", pred_ids).fetchall()
    if len(rows) != len(pred_ids) or any(r["HullNo"] != hull_no for r in rows):
        raise errors.validation("pred_plan_ids", "선행 공정은 같은 호선의 공정이어야 합니다.")
    if plan_id is not None:
        graph: dict[int, list[int]] = defaultdict(list)
        for dep in conn.execute(
            "SELECT d.PlanId, d.PredPlanId FROM TB_PRC_PlanDep d JOIN TB_PRC_Plan p ON p.PlanId = d.PlanId"
            " WHERE p.HullNo = ? AND d.PlanId <> ?",
            (hull_no, plan_id),
        ):
            graph[dep["PlanId"]].append(dep["PredPlanId"])
        stack, seen = list(pred_ids), set()
        while stack:
            current = stack.pop()
            if current == plan_id:
                raise errors.AppError(400, "PLAN_DEPENDENCY_CYCLE", "선행 공정이 순환 구조를 만듭니다.", {"field": "pred_plan_ids"})
            if current not in seen:
                seen.add(current)
                stack.extend(graph[current])
    late = sorted(r["PlanId"] for r in rows if r["PlanEndDt"] > start)
    if late and not confirm:
        raise errors.AppError(409, "PRED_LATE_CONFIRM_REQUIRED", LATE_MESSAGE, {"late_pred_plan_ids": late})
    return pred_ids


def _replace_predecessors(conn: sqlite3.Connection, plan_id: int, pred_ids: list[int]) -> None:
    conn.execute("DELETE FROM TB_PRC_PlanDep WHERE PlanId = ?", (plan_id,))
    conn.executemany(
        "INSERT INTO TB_PRC_PlanDep (PlanId, PredPlanId, LagDays) VALUES (?,?,0)", [(plan_id, p) for p in pred_ids]
    )


def create_plan(conn: sqlite3.Connection, hull_no: str, payload: dict, user: str) -> dict:
    hulls.ensure(conn, hull_no)
    data = blank_to_none(payload)
    confirm = data.get("confirm_late_preds", False)
    with transaction(conn):
        _validate(conn, hull_no, data)
        preds = _check_predecessors(conn, None, hull_no, data["plan_start_dt"], data.get("pred_plan_ids") or [], confirm)
        plan_id = conn.execute(
            "INSERT INTO TB_PRC_Plan (HullNo, BlockId, ProcCd, PlanStartDt, PlanEndDt, ManagerEmpNo, Remark,"
            " CreateUserId, CreateDt) VALUES (?,?,?,?,?,?,?,?,?)",
            (
                hull_no, data.get("block_id"), data["proc_cd"], data["plan_start_dt"], data["plan_end_dt"],
                data.get("manager_emp_no"), data.get("remark"), user, config.TODAY_ISO,
            ),
        ).lastrowid
        _replace_predecessors(conn, plan_id, preds)
        rules.recalc_hull(conn, hull_no)
    return get_plan(conn, plan_id)


def update_plan(conn: sqlite3.Connection, plan_id: int, payload: dict) -> dict:
    row = ensure(conn, plan_id)
    hull_no = row["HullNo"]
    current = {
        "block_id": row["BlockId"], "proc_cd": row["ProcCd"], "plan_start_dt": row["PlanStartDt"],
        "plan_end_dt": row["PlanEndDt"], "manager_emp_no": row["ManagerEmpNo"], "remark": row["Remark"],
    }
    changes = blank_to_none(payload)
    confirm = changes.pop("confirm_late_preds", False)
    pred_ids = changes.pop("pred_plan_ids", None)
    data = {**current, **changes}
    with transaction(conn):
        _validate(conn, hull_no, data)
        start_changed = data["plan_start_dt"] != current["plan_start_dt"]
        if pred_ids is None and start_changed:
            existing = conn.execute("SELECT PredPlanId FROM TB_PRC_PlanDep WHERE PlanId = ?", (plan_id,))
            _check_predecessors(conn, plan_id, hull_no, data["plan_start_dt"], [r[0] for r in existing], confirm)
        conn.execute(
            "UPDATE TB_PRC_Plan SET BlockId = ?, ProcCd = ?, PlanStartDt = ?, PlanEndDt = ?, ManagerEmpNo = ?,"
            " Remark = ? WHERE PlanId = ?",
            (*[data[k] for k in current], plan_id),
        )
        if pred_ids is not None:
            preds = _check_predecessors(conn, plan_id, hull_no, data["plan_start_dt"], pred_ids, confirm)
            _replace_predecessors(conn, plan_id, preds)
        rules.recalc_hull(conn, hull_no)
    return get_plan(conn, plan_id)


def delete_plan(conn: sqlite3.Connection, plan_id: int) -> None:
    row = ensure(conn, plan_id)
    with transaction(conn):
        conn.execute("DELETE FROM TB_PRC_Plan WHERE PlanId = ?", (plan_id,))
        rules.recalc_hull(conn, row["HullNo"])


def set_predecessors(conn: sqlite3.Connection, plan_id: int, pred_ids: list[int], confirm: bool) -> dict:
    row = ensure(conn, plan_id)
    with transaction(conn):
        preds = _check_predecessors(conn, plan_id, row["HullNo"], row["PlanStartDt"], pred_ids, confirm)
        _replace_predecessors(conn, plan_id, preds)
        rules.recalc_hull(conn, row["HullNo"])
    return get_plan(conn, plan_id)


def plan_links(conn: sqlite3.Connection, plan_id: int) -> dict:
    row = ensure(conn, plan_id)
    links = conn.execute(
        "SELECT d.DrawingId, d.DrawingNo, d.DrawingNm, d.DwgStatus, l.RequiredYN, l.NeedDt,"
        " EXISTS (SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId AND r.RevStatus = 'ISSUED') has_issued"
        " FROM TB_DWG_PlanLink l JOIN TB_DWG_Drawing d ON d.DrawingId = l.DrawingId"
        " WHERE l.PlanId = ? ORDER BY d.DrawingNo",
        (plan_id,),
    )
    available = conn.execute(
        "SELECT DrawingId, DrawingNo, DrawingNm, DwgStatus FROM TB_DWG_Drawing WHERE HullNo = ? AND DrawingId NOT IN"
        " (SELECT DrawingId FROM TB_DWG_PlanLink WHERE PlanId = ?) ORDER BY DrawingNo",
        (row["HullNo"], plan_id),
    )
    return {
        "plan_id": plan_id,
        "blockers": rules.blockers(conn, "l.PlanId = ?", (plan_id,)).get(plan_id, []),
        "links": [
            {
                "drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "drawing_nm": r["DrawingNm"],
                "dwg_status": r["DwgStatus"], "has_issued": bool(r["has_issued"]), "required": bool(r["RequiredYN"]),
                "need_dt": r["NeedDt"],
            }
            for r in links
        ],
        "available": [
            {"drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "drawing_nm": r["DrawingNm"], "dwg_status": r["DwgStatus"]}
            for r in available
        ],
    }


def add_link(conn: sqlite3.Connection, plan_id: int, drawing_id: int, required: bool) -> dict:
    plan = ensure(conn, plan_id)
    drawing = conn.execute("SELECT HullNo FROM TB_DWG_Drawing WHERE DrawingId = ?", (drawing_id,)).fetchone()
    if not drawing:
        raise errors.not_found("DRAWING_NOT_FOUND", "도면을 찾을 수 없습니다.")
    if drawing["HullNo"] != plan["HullNo"]:
        raise errors.validation("drawing_id", "같은 호선의 도면만 연계할 수 있습니다.")
    with transaction(conn):
        if conn.execute(
            "SELECT 1 FROM TB_DWG_PlanLink WHERE PlanId = ? AND DrawingId = ?", (plan_id, drawing_id)
        ).fetchone():
            raise errors.duplicate("이미 연계된 도면입니다.", field="drawing_id")
        conn.execute(
            "INSERT INTO TB_DWG_PlanLink (DrawingId, PlanId, RequiredYN, NeedDt) VALUES (?,?,?,?)",
            (drawing_id, plan_id, int(required), plan["PlanStartDt"]),
        )
        rules.recalc_hull(conn, plan["HullNo"])
    return plan_links(conn, plan_id)


def remove_link(conn: sqlite3.Connection, plan_id: int, drawing_id: int) -> None:
    plan = ensure(conn, plan_id)
    with transaction(conn):
        cursor = conn.execute("DELETE FROM TB_DWG_PlanLink WHERE PlanId = ? AND DrawingId = ?", (plan_id, drawing_id))
        if not cursor.rowcount:
            raise errors.not_found("LINK_NOT_FOUND", "연계를 찾을 수 없습니다.")
        rules.recalc_hull(conn, plan["HullNo"])
