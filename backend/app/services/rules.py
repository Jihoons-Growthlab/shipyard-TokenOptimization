"""교차 업무 규칙 BR-01(가중 진척률), BR-02(도면 게이트), BR-03(공정 상태)."""
import math
import sqlite3
from collections import defaultdict
from datetime import date, timedelta

from .. import config

DAYS_SQL = "(julianday(PlanEndDt) - julianday(PlanStartDt) + 1)"
DONE = 100


def weighted(numerator: float, denominator: float) -> int:
    return math.floor(numerator / denominator + 0.5)


def progress_by(conn: sqlite3.Connection, column: str, where: str = "1=1", args: tuple = ()) -> dict:
    """BR-01. column별 가중 진척률. 공정이 없는 키는 결과에 없다."""
    rows = conn.execute(
        f"SELECT {column} key, SUM(ProgressRate * {DAYS_SQL}) n, SUM({DAYS_SQL}) d"
        f" FROM TB_PRC_Plan WHERE {where} GROUP BY {column}",
        args,
    )
    return {r["key"]: weighted(r["n"], r["d"]) for r in rows}


def blockers(conn: sqlite3.Connection, where: str = "1=1", args: tuple = ()) -> dict[int, list[dict]]:
    """BR-02. 공정별 blocker 도면(도면번호순). where의 별칭: l=연계, d=도면."""
    rows = conn.execute(
        "SELECT l.PlanId, d.DrawingId, d.DrawingNo, d.DwgStatus FROM TB_DWG_PlanLink l"
        " JOIN TB_DWG_Drawing d ON d.DrawingId = l.DrawingId"
        " WHERE l.RequiredYN = 1 AND d.DwgStatus <> 'OBSOLETE' AND NOT EXISTS ("
        "   SELECT 1 FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId AND r.RevStatus = 'ISSUED')"
        f" AND {where} ORDER BY d.DrawingNo",
        args,
    )
    result: dict[int, list[dict]] = defaultdict(list)
    for row in rows:
        result[row["PlanId"]].append(
            {"drawing_id": row["DrawingId"], "drawing_no": row["DrawingNo"], "dwg_status": row["DwgStatus"]}
        )
    return result


def plan_status(plan: sqlite3.Row, preds_done: bool, blocked: bool, today: str = config.TODAY_ISO) -> str:
    """BR-03 판정."""
    rate, late = plan["ProgressRate"], plan["PlanEndDt"] < today
    if rate >= DONE:
        return "DONE"
    if rate > 0 or plan["ActualStartDt"]:
        return "DELAY" if late else "WORK"
    if late:
        return "DELAY"
    return "READY" if preds_done and not blocked else "PLAN"


def recalc_hull(conn: sqlite3.Connection, hull_no: str) -> None:
    """BR-03. 호선의 모든 공정 상태와 호선 자동 전이. 호출자의 트랜잭션 안에서 실행한다."""
    plans = conn.execute("SELECT * FROM TB_PRC_Plan WHERE HullNo = ?", (hull_no,)).fetchall()
    rates = {p["PlanId"]: p["ProgressRate"] for p in plans}
    preds: dict[int, list[int]] = defaultdict(list)
    for row in conn.execute(
        "SELECT d.PlanId, d.PredPlanId FROM TB_PRC_PlanDep d JOIN TB_PRC_Plan p ON p.PlanId = d.PlanId WHERE p.HullNo = ?",
        (hull_no,),
    ):
        preds[row["PlanId"]].append(row["PredPlanId"])
    blocked = blockers(conn, "l.PlanId IN (SELECT PlanId FROM TB_PRC_Plan WHERE HullNo = ?)", (hull_no,))

    statuses = {}
    for plan in plans:
        preds_done = all(rates.get(pred, 0) >= DONE for pred in preds[plan["PlanId"]])
        status = plan_status(plan, preds_done, plan["PlanId"] in blocked)
        statuses[plan["PlanId"]] = status
        if status != plan["PlanStatus"]:
            conn.execute("UPDATE TB_PRC_Plan SET PlanStatus = ? WHERE PlanId = ?", (status, plan["PlanId"]))

    hull = conn.execute("SELECT HullStatus FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone()
    if not hull:
        return
    current = next_status = hull["HullStatus"]
    if next_status == "DESIGN" and "WORK" in statuses.values():
        next_status = "BUILD"
    if next_status == "BUILD" and any(p["ProcCd"] == "LAUNCH" and statuses[p["PlanId"]] == "DONE" for p in plans):
        next_status = "LAUNCH"
    if next_status != current:
        conn.execute("UPDATE TB_MST_Hull SET HullStatus = ? WHERE HullNo = ?", (next_status, hull_no))


def revision_impacts(conn: sqlite3.Connection, where: str = "1=1", args: tuple = ()) -> list[dict]:
    """BR-07. where의 별칭: d=도면. 배포일 최신순."""
    since = (config.TODAY - timedelta(days=30)).isoformat()
    rows = conn.execute(
        "SELECT d.DrawingId, d.DrawingNo, d.HullNo, r.RevNo, r.IssueDt, r.ChangeDesc, p.PlanId, p.PlanStatus,"
        " b.BlockCd, c.ProcNm FROM TB_DWG_Drawing d"
        " JOIN TB_DWG_Revision r ON r.DrawingId = d.DrawingId AND r.RevNo = ("
        "   SELECT MAX(x.RevNo) FROM TB_DWG_Revision x WHERE x.DrawingId = d.DrawingId AND x.RevNo >= 1"
        "   AND x.RevStatus = 'ISSUED' AND x.IssueDt BETWEEN ? AND ?)"
        " JOIN TB_DWG_PlanLink l ON l.DrawingId = d.DrawingId"
        " JOIN TB_PRC_Plan p ON p.PlanId = l.PlanId AND p.PlanStatus IN ('WORK','DONE','DELAY')"
        " JOIN TB_PRC_Proc c ON c.ProcCd = p.ProcCd"
        " LEFT JOIN TB_MST_Block b ON b.BlockId = p.BlockId"
        f" WHERE {where} ORDER BY r.IssueDt DESC, d.DrawingNo, p.PlanId",
        (since, config.TODAY_ISO, *args),
    )
    return [
        {
            "drawing_id": r["DrawingId"], "drawing_no": r["DrawingNo"], "rev_no": r["RevNo"], "issue_dt": r["IssueDt"],
            "plan_id": r["PlanId"], "plan_label": f"[{r['BlockCd'] or '호선'}] {r['ProcNm']}", "plan_status": r["PlanStatus"],
            "hull_no": r["HullNo"], "change_desc": r["ChangeDesc"],
        }
        for r in rows
    ]


def days_between(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days
