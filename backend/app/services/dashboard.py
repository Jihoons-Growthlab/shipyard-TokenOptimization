"""대시보드 집계. 규칙은 rules를 재사용한다."""
import sqlite3
from collections import defaultdict

from .. import config
from . import plans, rules

ACTIVE = ("DESIGN", "BUILD", "LAUNCH", "TRIAL")
PLAN_STATUSES = ("PLAN", "READY", "WORK", "DONE", "DELAY")
DRAWING_STATUSES = ("ISSUED", "APPROVED", "REVIEW", "DRAFT")
LIMIT = 6
USED_HULL = "HullNo IN (SELECT HullNo FROM TB_MST_Hull WHERE UseYN = 1)"


def _bundle(items: list[dict]) -> dict:
    return {"count": len(items), "items": items[:LIMIT]}


def _plan_item(view: dict) -> dict:
    return {
        "plan_id": view["plan_id"], "hull_no": view["hull_no"], "label": view["label"], "plan_status": view["plan_status"],
        "progress_rate": view["progress_rate"], "plan_start_dt": view["plan_start_dt"], "plan_end_dt": view["plan_end_dt"],
        "blockers": [b["drawing_no"] for b in view["blockers"]],
        "link": {"screen": "plan-gantt", "param": view["hull_no"]},
    }


def summary(conn: sqlite3.Connection) -> dict:
    hulls = conn.execute("SELECT HullNo, HullNm, HullStatus, DeliveryDt FROM TB_MST_Hull WHERE UseYN = 1 ORDER BY HullNo").fetchall()
    views = plans.plan_views(conn, f"p.{USED_HULL}", ())
    progress = rules.progress_by(conn, "HullNo", USED_HULL)

    status_counts = dict.fromkeys(PLAN_STATUSES, 0)
    for view in views:
        status_counts[view["plan_status"]] += 1

    by_start = sorted(views, key=lambda v: (v["plan_start_dt"], v["plan_id"]))
    delayed = [_plan_item(v) for v in by_start if v["plan_status"] == "DELAY"]
    waiting = [_plan_item(v) for v in by_start if v["drawing_wait"]]

    rows = conn.execute(
        f"SELECT Discipline, DwgStatus, COUNT(*) c FROM TB_DWG_Drawing WHERE {USED_HULL} GROUP BY 1, 2"
    ).fetchall()
    counts: dict = defaultdict(lambda: dict.fromkeys(DRAWING_STATUSES, 0))
    totals: dict = defaultdict(int)
    pending = 0
    for row in rows:
        totals[row["Discipline"]] += row["c"]
        if row["DwgStatus"] in DRAWING_STATUSES:
            counts[row["Discipline"]][row["DwgStatus"]] = row["c"]
        if row["DwgStatus"] in ("REVIEW", "APPROVED"):
            pending += row["c"]
    disciplines = [
        {"discipline": r["Code"], "name": r["CodeName"], "total": totals[r["Code"]], "counts": counts[r["Code"]]}
        for r in conn.execute("SELECT Code, CodeName FROM TB_SYS_Code WHERE CodeGroup = 'DWGDISC' ORDER BY Seq")
        if totals[r["Code"]]
    ]

    months: dict[str, list[str]] = defaultdict(list)
    for hull in hulls:
        if hull["DeliveryDt"]:
            months[hull["DeliveryDt"][:7]].append(hull["HullNo"])

    impacts = [
        {**item, "link": {"screen": "drawing", "param": item["drawing_id"]}}
        for item in rules.revision_impacts(conn, f"d.{USED_HULL}")
    ]
    return {
        "today": config.TODAY_ISO,
        "kpi": {
            "active_hulls": {"value": sum(h["HullStatus"] in ACTIVE for h in hulls), "link": {"screen": "hull-list"}},
            "delay_plans": {"value": status_counts["DELAY"], "link": {"screen": "plan-gantt"}},
            "waiting_plans": {"value": len(waiting), "link": {"screen": "plan-gantt"}},
            "pending_drawings": {"value": pending, "link": {"screen": "dwg-approval"}},
        },
        "hull_progress": [
            {
                "hull_no": h["HullNo"], "hull_nm": h["HullNm"], "progress": progress.get(h["HullNo"], 0),
                "link": {"screen": "plan-gantt", "param": h["HullNo"]},
            }
            for h in hulls
        ],
        "plan_status": [{"status": s, "count": status_counts[s]} for s in PLAN_STATUSES],
        "drawing_disciplines": disciplines,
        "deliveries": [{"month": m, "count": len(months[m]), "hull_nos": months[m]} for m in sorted(months)],
        "delay_list": _bundle(delayed),
        "waiting_list": _bundle(waiting),
        "impact_list": _bundle(impacts),
    }
