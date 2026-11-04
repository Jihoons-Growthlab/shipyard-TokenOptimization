"""호선·일정·블록."""
import re
import sqlite3

from .. import config, errors
from ..db import transaction
from . import files, rules
from .validators import blank_to_none, check_code, check_date, check_non_negative

HULL_NO_RE = re.compile(r"^[A-Za-z0-9._-]{1,20}$")
MILESTONES = ("CUT", "KEEL", "LAUNCH", "TRIAL", "DELIVER")
HULL_COLUMNS = {
    "hull_no": "HullNo", "hull_nm": "HullNm", "ship_type": "ShipType", "hull_status": "HullStatus",
    "owner_nm": "OwnerNm", "class_society": "ClassSociety", "length_m": "LengthM", "breadth_m": "BreadthM",
    "depth_m": "DepthM", "dead_weight": "DeadWeight", "dock_no": "DockNo", "contract_dt": "ContractDt",
    "delivery_dt": "DeliveryDt", "remark": "Remark", "use_yn": "UseYN", "create_user_id": "CreateUserId",
    "create_dt": "CreateDt", "modify_user_id": "ModifyUserId", "modify_dt": "ModifyDt",
}
WRITABLE = set(HULL_COLUMNS) - {"hull_no", "create_user_id", "create_dt", "modify_user_id", "modify_dt"}


def _not_found() -> errors.AppError:
    return errors.not_found("HULL_NOT_FOUND", "호선을 찾을 수 없습니다.")


def ensure(conn: sqlite3.Connection, hull_no: str) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone()
    if not row:
        raise _not_found()
    return row


def _hull_view(row: sqlite3.Row, counts: dict, progress: dict) -> dict:
    data = {api: row[db] for api, db in HULL_COLUMNS.items()}
    data["use_yn"] = bool(data["use_yn"])
    count = counts.get(row["HullNo"], (0, 0))
    return {**data, "plan_count": count[0], "delay_count": count[1], "progress": progress.get(row["HullNo"])}


def _counts(conn: sqlite3.Connection) -> dict:
    rows = conn.execute(
        "SELECT HullNo, COUNT(*) c, SUM(PlanStatus = 'DELAY') d FROM TB_PRC_Plan GROUP BY HullNo"
    )
    return {r["HullNo"]: (r["c"], r["d"]) for r in rows}


def list_hulls(conn: sqlite3.Connection, status: str = "", ship_type: str = "", q: str = "") -> list[dict]:
    clauses, args = ["1=1"], []
    if status:
        clauses.append("HullStatus = ?")
        args.append(status)
    if ship_type:
        clauses.append("ShipType = ?")
        args.append(ship_type)
    if q:
        clauses.append("instr(lower(HullNo || char(10) || HullNm || char(10) || coalesce(OwnerNm,'')), lower(?)) > 0")
        args.append(q)
    rows = conn.execute(f"SELECT * FROM TB_MST_Hull WHERE {' AND '.join(clauses)} ORDER BY HullNo", args).fetchall()
    counts, progress = _counts(conn), rules.progress_by(conn, "HullNo")
    return [_hull_view(r, counts, progress) for r in rows]


def get_hull(conn: sqlite3.Connection, hull_no: str) -> dict:
    return _hull_view(ensure(conn, hull_no), _counts(conn), rules.progress_by(conn, "HullNo"))


def _validate(conn: sqlite3.Connection, data: dict) -> None:
    check_code(conn, "SHIPTYPE", data.get("ship_type"), "ship_type")
    if not data.get("hull_status"):
        raise errors.validation("hull_status", "상태를 선택하세요.")
    check_code(conn, "HULLSTAT", data["hull_status"], "hull_status")
    check_date(data.get("contract_dt"), "contract_dt")
    check_date(data.get("delivery_dt"), "delivery_dt")
    if data.get("contract_dt") and data.get("delivery_dt") and data["delivery_dt"] < data["contract_dt"]:
        raise errors.validation("delivery_dt", "인도 예정일이 계약일보다 빠릅니다.")
    for field in ("length_m", "breadth_m", "depth_m", "dead_weight"):
        check_non_negative(data.get(field), field)


def create_hull(conn: sqlite3.Connection, payload: dict, user: str) -> dict:
    hull_no = (payload.get("hull_no") or "").strip()
    if not hull_no:
        raise errors.validation("hull_no", "호선번호를 입력하세요.")
    if not HULL_NO_RE.match(hull_no):
        raise errors.validation("hull_no", "호선번호는 영문/숫자/._- 1~20자입니다.")
    status_given = "hull_status" in payload
    data = blank_to_none(payload)
    if not status_given:
        data["hull_status"] = "PLAN"
    data.setdefault("use_yn", True)
    if not data.get("hull_nm"):
        data["hull_nm"] = hull_no
    _validate(conn, data)
    columns = {HULL_COLUMNS[k]: v for k, v in data.items() if k in WRITABLE}
    columns.update(HullNo=hull_no, CreateUserId=user, CreateDt=config.TODAY_ISO)
    with transaction(conn):
        if conn.execute("SELECT 1 FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,)).fetchone():
            raise errors.duplicate("이미 존재하는 호선번호입니다.", field="hull_no")
        sql = f"INSERT INTO TB_MST_Hull ({','.join(columns)}) VALUES ({','.join('?' * len(columns))})"
        conn.execute(sql, list(columns.values()))
        conn.executemany(
            "INSERT INTO TB_MST_HullMilestone (HullNo, MilestoneCd, PlanDt) VALUES (?,?,?)",
            [(hull_no, code, data.get("delivery_dt") if code == "DELIVER" else None) for code in MILESTONES],
        )
    return get_hull(conn, hull_no)


def update_hull(conn: sqlite3.Connection, hull_no: str, payload: dict, user: str) -> dict:
    row = ensure(conn, hull_no)
    if payload.get("hull_no", hull_no) != hull_no:
        raise errors.validation("hull_no", "호선번호는 수정할 수 없습니다.")
    changes = {k: v for k, v in blank_to_none(payload).items() if k in WRITABLE}
    merged = {**{api: row[db] for api, db in HULL_COLUMNS.items()}, **changes}
    _validate(conn, merged)
    if "hull_nm" in changes and not changes["hull_nm"]:
        changes["hull_nm"] = hull_no
    assignments = {HULL_COLUMNS[k]: v for k, v in changes.items()}
    assignments.update(ModifyUserId=user, ModifyDt=config.TODAY_ISO)
    with transaction(conn):
        sql = f"UPDATE TB_MST_Hull SET {','.join(f'{c} = ?' for c in assignments)} WHERE HullNo = ?"
        conn.execute(sql, [*assignments.values(), hull_no])
    return get_hull(conn, hull_no)


def delete_hull(conn: sqlite3.Connection, hull_no: str) -> None:
    ensure(conn, hull_no)
    with transaction(conn):
        file_ids = [
            r["FileId"]
            for r in conn.execute(
                "SELECT r.FileId FROM TB_DWG_Revision r JOIN TB_DWG_Drawing d ON d.DrawingId = r.DrawingId"
                " WHERE d.HullNo = ?",
                (hull_no,),
            )
        ]
        conn.execute("DELETE FROM TB_MST_Hull WHERE HullNo = ?", (hull_no,))
    files.remove(file_ids)


def list_milestones(conn: sqlite3.Connection, hull_no: str) -> list[dict]:
    ensure(conn, hull_no)
    rows = conn.execute(
        "SELECT m.MilestoneCd, c.CodeName, m.PlanDt, m.ActualDt FROM TB_MST_HullMilestone m"
        " LEFT JOIN TB_SYS_Code c ON c.CodeGroup = 'MILESTONE' AND c.Code = m.MilestoneCd"
        " WHERE m.HullNo = ? ORDER BY c.Seq",
        (hull_no,),
    )
    return [
        {
            "milestone_cd": r["MilestoneCd"], "name": r["CodeName"], "plan_dt": r["PlanDt"], "actual_dt": r["ActualDt"],
            "diff_days": rules.days_between(r["PlanDt"], r["ActualDt"]) if r["PlanDt"] and r["ActualDt"] else None,
        }
        for r in rows
    ]


def save_milestones(conn: sqlite3.Connection, hull_no: str, items: list[dict]) -> list[dict]:
    ensure(conn, hull_no)
    allowed = {r["Code"] for r in conn.execute("SELECT Code FROM TB_SYS_Code WHERE CodeGroup = 'MILESTONE'")}
    codes = [item["milestone_cd"] for item in items]
    if len(set(codes)) != len(codes) or not set(codes) <= allowed:
        raise errors.validation("milestone_cd", "허용되지 않거나 중복된 일정 코드입니다.")
    for item in items:
        check_date(item.get("plan_dt"), "plan_dt")
        check_date(item.get("actual_dt"), "actual_dt")
    with transaction(conn):
        conn.executemany(
            "INSERT INTO TB_MST_HullMilestone (HullNo, MilestoneCd, PlanDt, ActualDt) VALUES (?,?,?,?)"
            " ON CONFLICT (HullNo, MilestoneCd) DO UPDATE SET PlanDt = excluded.PlanDt, ActualDt = excluded.ActualDt",
            [(hull_no, i["milestone_cd"], i.get("plan_dt") or None, i.get("actual_dt") or None) for i in items],
        )
    return list_milestones(conn, hull_no)


def _block_views(conn: sqlite3.Connection, where: str, args: tuple) -> list[dict]:
    rows = conn.execute(
        "SELECT b.*, (SELECT COUNT(*) FROM TB_PRC_Plan p WHERE p.BlockId = b.BlockId) plan_count,"
        " (SELECT COUNT(*) FROM TB_DWG_Drawing d WHERE d.BlockId = b.BlockId) drawing_count"
        f" FROM TB_MST_Block b WHERE {where} ORDER BY b.BlockCd",
        args,
    ).fetchall()
    progress = rules.progress_by(conn, "BlockId", "BlockId IS NOT NULL")
    return [
        {
            "block_id": r["BlockId"], "hull_no": r["HullNo"], "block_cd": r["BlockCd"], "block_nm": r["BlockNm"],
            "block_type": r["BlockType"], "parent_block_id": r["ParentBlockId"], "weight_ton": r["WeightTon"],
            "use_yn": bool(r["UseYN"]), "plan_count": r["plan_count"], "progress": progress.get(r["BlockId"]),
            "drawing_count": r["drawing_count"],
        }
        for r in rows
    ]


def list_blocks(conn: sqlite3.Connection, hull_no: str) -> list[dict]:
    ensure(conn, hull_no)
    return _block_views(conn, "b.HullNo = ?", (hull_no,))


def create_block(conn: sqlite3.Connection, hull_no: str, payload: dict) -> dict:
    ensure(conn, hull_no)
    data = blank_to_none(payload)
    block_cd = data.get("block_cd")
    if not block_cd:
        raise errors.validation("block_cd", "블록코드를 입력하세요.")
    check_code(conn, "BLOCKTYPE", data.get("block_type"), "block_type")
    check_non_negative(data.get("weight_ton"), "weight_ton")
    with transaction(conn):
        if conn.execute("SELECT 1 FROM TB_MST_Block WHERE HullNo = ? AND BlockCd = ?", (hull_no, block_cd)).fetchone():
            raise errors.duplicate("이미 존재하는 블록코드입니다.", field="block_cd")
        block_id = conn.execute(
            "INSERT INTO TB_MST_Block (HullNo, BlockCd, BlockNm, BlockType, WeightTon) VALUES (?,?,?,?,?)",
            (hull_no, block_cd, data.get("block_nm"), data.get("block_type"), data.get("weight_ton")),
        ).lastrowid
    return _block_views(conn, "b.BlockId = ?", (block_id,))[0]


def delete_block(conn: sqlite3.Connection, block_id: int) -> None:
    row = conn.execute("SELECT HullNo FROM TB_MST_Block WHERE BlockId = ?", (block_id,)).fetchone()
    if not row:
        raise errors.not_found("BLOCK_NOT_FOUND", "블록을 찾을 수 없습니다.")
    with transaction(conn):
        conn.execute("DELETE FROM TB_MST_Block WHERE BlockId = ?", (block_id,))
        rules.recalc_hull(conn, row["HullNo"])


def summary(conn: sqlite3.Connection, hull_no: str) -> dict:
    ensure(conn, hull_no)
    plan_status = dict.fromkeys(("PLAN", "READY", "WORK", "DONE", "DELAY"), 0)
    for row in conn.execute("SELECT PlanStatus s, COUNT(*) c FROM TB_PRC_Plan WHERE HullNo = ? GROUP BY 1", (hull_no,)):
        plan_status[row["s"]] = row["c"]
    drawing_status = dict.fromkeys(("ISSUED", "APPROVED", "REVIEW", "DRAFT"), 0)
    drawing_count = 0
    for row in conn.execute("SELECT DwgStatus s, COUNT(*) c FROM TB_DWG_Drawing WHERE HullNo = ? GROUP BY 1", (hull_no,)):
        drawing_count += row["c"]
        if row["s"] in drawing_status:
            drawing_status[row["s"]] = row["c"]
    return {
        "hull_no": hull_no, "plan_count": sum(plan_status.values()),
        "progress": rules.progress_by(conn, "HullNo", "HullNo = ?", (hull_no,)).get(hull_no),
        "plan_status": plan_status, "drawing_count": drawing_count, "drawing_status": drawing_status,
    }
