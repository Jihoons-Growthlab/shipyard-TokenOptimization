"""도면·리비전(BR-06)·PDF·공정 연계."""
import re
import sqlite3
import uuid
from collections.abc import AsyncIterator

from .. import config, errors
from ..db import transaction
from . import files, hulls, plans, rules
from .validators import blank_to_none

MAX_PDF = 30 * 1024 * 1024
LIST_SELECT = (
    "SELECT d.*, b.BlockCd, b.BlockNm, u.display_name DesignerNm,"
    " (SELECT MAX(r.RevNo) FROM TB_DWG_Revision r WHERE r.DrawingId = d.DrawingId) LatestRev,"
    " (SELECT COUNT(*) FROM TB_DWG_PlanLink l WHERE l.DrawingId = d.DrawingId) LinkCount"
    " FROM TB_DWG_Drawing d LEFT JOIN TB_MST_Block b ON b.BlockId = d.BlockId"
    " LEFT JOIN users u ON u.emp_no = d.DesignerEmpNo"
)


def _not_found() -> errors.AppError:
    return errors.not_found("DRAWING_NOT_FOUND", "도면을 찾을 수 없습니다.")


def _state_error(message: str) -> errors.AppError:
    return errors.AppError(409, "INVALID_REV_STATE", message)


def ensure(conn: sqlite3.Connection, drawing_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM TB_DWG_Drawing WHERE DrawingId = ?", (drawing_id,)).fetchone()
    if not row:
        raise _not_found()
    return row


def ensure_revision(conn: sqlite3.Connection, drawing_id: int, rev_no: int) -> sqlite3.Row:
    ensure(conn, drawing_id)
    row = conn.execute(
        "SELECT * FROM TB_DWG_Revision WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no)
    ).fetchone()
    if not row:
        raise errors.not_found("REVISION_NOT_FOUND", "리비전을 찾을 수 없습니다.")
    return row


def latest_rev(conn: sqlite3.Connection, drawing_id: int) -> sqlite3.Row:
    return conn.execute(
        "SELECT * FROM TB_DWG_Revision WHERE DrawingId = ? ORDER BY RevNo DESC LIMIT 1", (drawing_id,)
    ).fetchone()


def _list_item(row: sqlite3.Row) -> dict:
    return {
        "drawing_id": row["DrawingId"], "drawing_no": row["DrawingNo"], "drawing_nm": row["DrawingNm"],
        "hull_no": row["HullNo"], "block_id": row["BlockId"], "block_cd": row["BlockCd"], "discipline": row["Discipline"],
        "dwg_status": row["DwgStatus"], "current_rev_no": row["CurrentRevNo"], "latest_rev_no": row["LatestRev"],
        "designer_emp_no": row["DesignerEmpNo"], "designer_nm": row["DesignerNm"], "link_count": row["LinkCount"],
    }


def list_drawings(conn: sqlite3.Connection, hull_no: str = "", discipline: str = "", status: str = "", q: str = "") -> list[dict]:
    clauses, args = ["1=1"], []
    for column, value in (("d.HullNo", hull_no), ("d.Discipline", discipline), ("d.DwgStatus", status)):
        if value:
            clauses.append(f"{column} = ?")
            args.append(value)
    if q:
        clauses.append("instr(lower(d.DrawingNo || char(10) || d.DrawingNm), lower(?)) > 0")
        args.append(q)
    rows = conn.execute(f"{LIST_SELECT} WHERE {' AND '.join(clauses)} ORDER BY d.DrawingId", args)
    return [_list_item(r) for r in rows]


def list_revisions(conn: sqlite3.Connection, drawing_id: int) -> list[dict]:
    ensure(conn, drawing_id)
    rows = conn.execute(
        "SELECT r.*, u.display_name AuthorNm FROM TB_DWG_Revision r LEFT JOIN users u ON u.emp_no = r.AuthorEmpNo"
        " WHERE r.DrawingId = ? ORDER BY r.RevNo DESC",
        (drawing_id,),
    )
    return [
        {
            "rev_no": r["RevNo"], "rev_status": r["RevStatus"], "change_desc": r["ChangeDesc"], "has_file": bool(r["FileId"]),
            "file_nm": r["FileNm"], "author_emp_no": r["AuthorEmpNo"], "author_nm": r["AuthorNm"], "issue_dt": r["IssueDt"],
            "create_dt": r["CreateDt"],
        }
        for r in rows
    ]


def _approvals(conn: sqlite3.Connection, drawing_id: int) -> list[dict]:
    rows = conn.execute(
        "SELECT a.*, u.display_name ApproverNm FROM TB_DWG_Approval a LEFT JOIN users u ON u.emp_no = a.ApproverEmpNo"
        " WHERE a.DrawingId = ? ORDER BY a.RevNo DESC, a.StepNo",
        (drawing_id,),
    )
    return [
        {
            "approval_id": r["ApprovalId"], "rev_no": r["RevNo"], "step_no": r["StepNo"], "approver_emp_no": r["ApproverEmpNo"],
            "approver_nm": r["ApproverNm"], "result": r["Result"], "comment": r["Comment"], "act_dt": r["ActDt"],
        }
        for r in rows
    ]


def linked_plans(conn: sqlite3.Connection, drawing_id: int) -> dict:
    row = ensure(conn, drawing_id)
    views = plans.plan_views(conn, "p.HullNo = ?", (row["HullNo"],))
    links = {
        r["PlanId"]: r
        for r in conn.execute("SELECT PlanId, RequiredYN, NeedDt FROM TB_DWG_PlanLink WHERE DrawingId = ?", (drawing_id,))
    }
    linked, available = [], []
    for view in views:
        brief = {"plan_id": view["plan_id"], "label": view["label"], "plan_status": view["plan_status"]}
        link = links.get(view["plan_id"])
        if not link:
            available.append(brief)
            continue
        linked.append({
            **brief, "required": bool(link["RequiredYN"]), "need_dt": link["NeedDt"],
            "plan_start_dt": view["plan_start_dt"], "plan_end_dt": view["plan_end_dt"],
        })
    return {"plans": linked, "available_plans": available}


def get_drawing(conn: sqlite3.Connection, drawing_id: int) -> dict:
    row = conn.execute(f"{LIST_SELECT} WHERE d.DrawingId = ?", (drawing_id,)).fetchone()
    if not row:
        raise _not_found()
    return {
        **_list_item(row), "block_nm": row["BlockNm"], "create_user_id": row["CreateUserId"], "create_dt": row["CreateDt"],
        "modify_user_id": row["ModifyUserId"], "modify_dt": row["ModifyDt"], "today": config.TODAY_ISO,
        "revisions": list_revisions(conn, drawing_id), "approvals": _approvals(conn, drawing_id),
        **linked_plans(conn, drawing_id), "impacts": rules.revision_impacts(conn, "d.DrawingId = ?", (drawing_id,)),
    }


def _check_refs(conn: sqlite3.Connection, hull_no: str, data: dict) -> None:
    discipline = data.get("discipline")
    if discipline and not conn.execute(
        "SELECT 1 FROM TB_SYS_Code WHERE CodeGroup = 'DWGDISC' AND Code = ? AND UseYN = 1", (discipline,)
    ).fetchone():
        raise errors.validation("discipline", "허용되지 않는 분야입니다.")
    block_id = data.get("block_id")
    if block_id is not None and not conn.execute(
        "SELECT 1 FROM TB_MST_Block WHERE BlockId = ? AND HullNo = ?", (block_id, hull_no)
    ).fetchone():
        raise errors.validation("block_id", "해당 호선의 블록이 아닙니다.")
    check_member(conn, data.get("designer_emp_no"), "designer_emp_no")


def check_member(conn: sqlite3.Connection, emp_no: str | None, field: str) -> None:
    if emp_no and not conn.execute("SELECT 1 FROM users WHERE emp_no = ? AND status = 'approved'", (emp_no,)).fetchone():
        raise errors.validation(field, "승인된 회원만 지정할 수 있습니다.")


def create_drawing(conn: sqlite3.Connection, payload: dict, user: str) -> dict:
    data = blank_to_none(payload)
    if not data.get("drawing_no"):
        raise errors.validation("drawing_no", "도면번호를 입력하세요.")
    if not data.get("hull_no"):
        raise errors.validation("hull_no", "호선을 선택하세요.")
    if not data.get("drawing_nm"):
        raise errors.validation("drawing_nm", "도면명을 입력하세요.")
    hulls.ensure(conn, data["hull_no"])
    _check_refs(conn, data["hull_no"], data)
    with transaction(conn):
        if conn.execute("SELECT 1 FROM TB_DWG_Drawing WHERE DrawingNo = ?", (data["drawing_no"],)).fetchone():
            raise errors.duplicate("이미 존재하는 도면번호입니다.", field="drawing_no")
        drawing_id = conn.execute(
            "INSERT INTO TB_DWG_Drawing (DrawingNo, DrawingNm, HullNo, BlockId, Discipline, DesignerEmpNo, CreateUserId, CreateDt)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                data["drawing_no"], data["drawing_nm"], data["hull_no"], data.get("block_id"), data.get("discipline"),
                data.get("designer_emp_no"), user, config.TODAY_ISO,
            ),
        ).lastrowid
        conn.execute(
            "INSERT INTO TB_DWG_Revision (DrawingId, RevNo, RevStatus, ChangeDesc, AuthorEmpNo, CreateDt)"
            " VALUES (?,0,'DRAFT','최초 작성',?,?)",
            (drawing_id, user, config.TODAY_ISO),
        )
    return get_drawing(conn, drawing_id)


def update_drawing(conn: sqlite3.Connection, drawing_id: int, payload: dict, user: str) -> dict:
    row = ensure(conn, drawing_id)
    if payload.get("hull_no", row["HullNo"]) != row["HullNo"]:
        raise errors.validation("hull_no", "호선은 변경할 수 없습니다.")
    if payload.get("drawing_no", row["DrawingNo"]) != row["DrawingNo"]:
        raise errors.validation("drawing_no", "도면번호는 변경할 수 없습니다.")
    columns = {"drawing_nm": "DrawingNm", "discipline": "Discipline", "block_id": "BlockId", "designer_emp_no": "DesignerEmpNo"}
    changes = {k: v for k, v in blank_to_none(payload).items() if k in columns}
    if "drawing_nm" in changes and not changes["drawing_nm"]:
        raise errors.validation("drawing_nm", "도면명을 입력하세요.")
    _check_refs(conn, row["HullNo"], changes)
    assignments = {columns[k]: v for k, v in changes.items()}
    assignments.update(ModifyUserId=user, ModifyDt=config.TODAY_ISO)
    with transaction(conn):
        sql = f"UPDATE TB_DWG_Drawing SET {','.join(f'{c} = ?' for c in assignments)} WHERE DrawingId = ?"
        conn.execute(sql, [*assignments.values(), drawing_id])
    return get_drawing(conn, drawing_id)


def delete_drawing(conn: sqlite3.Connection, drawing_id: int) -> None:
    row = ensure(conn, drawing_id)
    with transaction(conn):
        file_ids = [r["FileId"] for r in conn.execute("SELECT FileId FROM TB_DWG_Revision WHERE DrawingId = ?", (drawing_id,))]
        conn.execute("DELETE FROM TB_DWG_Drawing WHERE DrawingId = ?", (drawing_id,))
        rules.recalc_hull(conn, row["HullNo"])
    files.remove(file_ids)


def set_status(conn: sqlite3.Connection, drawing_id: int, rev_no: int, status: str) -> None:
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus = ? WHERE DrawingId = ? AND RevNo = ?", (status, drawing_id, rev_no))
    conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = ? WHERE DrawingId = ?", (status, drawing_id))


def create_revision(conn: sqlite3.Connection, drawing_id: int, change_desc: str, user: str) -> dict:
    row = ensure(conn, drawing_id)
    if not change_desc.strip():
        raise errors.validation("change_desc", "개정 사유를 입력하세요.")
    with transaction(conn):
        latest = latest_rev(conn, drawing_id)
        if latest["RevStatus"] not in ("ISSUED", "OBSOLETE"):
            raise _state_error("최신 리비전이 배포/폐기 상태일 때만 신규 리비전을 작성할 수 있습니다.")
        rev_no = latest["RevNo"] + 1
        conn.execute(
            "INSERT INTO TB_DWG_Revision (DrawingId, RevNo, RevStatus, ChangeDesc, AuthorEmpNo, CreateDt)"
            " VALUES (?,?,'DRAFT',?,?,?)",
            (drawing_id, rev_no, change_desc.strip(), user, config.TODAY_ISO),
        )
        conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus = 'DRAFT' WHERE DrawingId = ?", (drawing_id,))
        rules.recalc_hull(conn, row["HullNo"])
    return get_drawing(conn, drawing_id)


def request_approval(conn: sqlite3.Connection, drawing_id: int, rev_no: int, reviewer: str | None, approver: str | None) -> dict:
    row = ensure(conn, drawing_id)
    ensure_revision(conn, drawing_id, rev_no)
    if not reviewer or not approver:
        raise errors.validation("reviewer_emp_no", "검토자와 승인자를 선택하세요.")
    if reviewer == approver:
        raise errors.validation("approver_emp_no", "검토자와 승인자는 서로 다른 사람이어야 합니다.")
    check_member(conn, reviewer, "reviewer_emp_no")
    check_member(conn, approver, "approver_emp_no")
    with transaction(conn):
        latest = latest_rev(conn, drawing_id)
        if latest["RevNo"] != rev_no or latest["RevStatus"] != "DRAFT":
            raise _state_error("최신 작성중(DRAFT) 리비전만 결재 요청할 수 있습니다.")
        conn.execute("DELETE FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no))
        conn.executemany(
            "INSERT INTO TB_DWG_Approval (DrawingId, RevNo, StepNo, ApproverEmpNo) VALUES (?,?,?,?)",
            [(drawing_id, rev_no, 1, reviewer), (drawing_id, rev_no, 2, approver)],
        )
        set_status(conn, drawing_id, rev_no, "REVIEW")
        rules.recalc_hull(conn, row["HullNo"])
    return get_drawing(conn, drawing_id)


def issue(conn: sqlite3.Connection, drawing_id: int, rev_no: int) -> dict:
    row = ensure(conn, drawing_id)
    with transaction(conn):
        revision = ensure_revision(conn, drawing_id, rev_no)
        if revision["RevStatus"] != "APPROVED":
            raise _state_error("승인(APPROVED)된 리비전만 배포할 수 있습니다.")
        results = conn.execute(
            "SELECT Result FROM TB_DWG_Approval WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no)
        ).fetchall()
        if not results or any(r["Result"] != "APPROVE" for r in results):
            raise errors.AppError(409, "APPROVAL_INCOMPLETE", "결재가 완료된 리비전만 배포할 수 있습니다.")
        conn.execute("UPDATE TB_DWG_Revision SET RevStatus = 'OBSOLETE' WHERE DrawingId = ? AND RevStatus = 'ISSUED'", (drawing_id,))
        conn.execute(
            "UPDATE TB_DWG_Revision SET IssueDt = ? WHERE DrawingId = ? AND RevNo = ?", (config.TODAY_ISO, drawing_id, rev_no)
        )
        set_status(conn, drawing_id, rev_no, "ISSUED")
        conn.execute("UPDATE TB_DWG_Drawing SET CurrentRevNo = ? WHERE DrawingId = ?", (rev_no, drawing_id))
        rules.recalc_hull(conn, row["HullNo"])
    return get_drawing(conn, drawing_id)


def clean_filename(name: str) -> str:
    base = re.split(r"[\\/]", name or "")[-1]
    return re.sub(r"[\x00-\x1f\x7f]", "", base).strip()[:200]


def _invalid_type() -> errors.AppError:
    return errors.AppError(400, "INVALID_FILE_TYPE", "PDF 파일만 업로드할 수 있습니다.")


def _too_large() -> errors.AppError:
    return errors.AppError(413, "FILE_TOO_LARGE", "파일 크기는 30MB 이하여야 합니다.")


async def upload_pdf(
    conn: sqlite3.Connection, drawing_id: int, rev_no: int, filename: str, content_type: str,
    declared_size: int | None, stream: AsyncIterator[bytes],
) -> dict:
    revision = ensure_revision(conn, drawing_id, rev_no)
    if revision["RevStatus"] != "DRAFT":
        raise _state_error("작성중(DRAFT) 리비전만 업로드할 수 있습니다.")
    name = clean_filename(filename)
    if not name or not (name.lower().endswith(".pdf") or content_type.split(";")[0].strip().lower() == "application/pdf"):
        raise _invalid_type()
    if declared_size is not None and declared_size > MAX_PDF:
        raise _too_large()

    file_id = uuid.uuid4().hex
    path = files.path_of(file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    size, head = 0, b""
    try:
        with path.open("wb") as output:
            async for chunk in stream:
                size += len(chunk)
                if size > MAX_PDF:
                    raise _too_large()
                if len(head) < 5:
                    head += chunk[:5 - len(head)]
                    if not b"%PDF-".startswith(head):
                        raise _invalid_type()
                output.write(chunk)
        if head != b"%PDF-":
            raise _invalid_type()
        with transaction(conn):
            current = ensure_revision(conn, drawing_id, rev_no)
            if current["RevStatus"] != "DRAFT":
                raise _state_error("작성중(DRAFT) 리비전만 업로드할 수 있습니다.")
            conn.execute(
                "UPDATE TB_DWG_Revision SET FileId = ?, FileNm = ? WHERE DrawingId = ? AND RevNo = ?",
                (file_id, name, drawing_id, rev_no),
            )
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    files.remove([current["FileId"]])
    return {"rev_no": rev_no, "has_file": True, "file_nm": name}


def pdf_info(conn: sqlite3.Connection, drawing_id: int, rev_no: int) -> tuple:
    revision = ensure_revision(conn, drawing_id, rev_no)
    if not revision["FileId"]:
        raise errors.not_found("NO_FILE", "업로드된 파일이 없습니다.")
    path = files.path_of(revision["FileId"])
    if not path.is_file():
        raise errors.not_found("FILE_NOT_FOUND", "파일을 찾을 수 없습니다.")
    return path, revision["FileNm"]


def delete_pdf(conn: sqlite3.Connection, drawing_id: int, rev_no: int) -> None:
    with transaction(conn):
        revision = ensure_revision(conn, drawing_id, rev_no)
        if revision["RevStatus"] != "DRAFT":
            raise _state_error("작성중(DRAFT) 리비전만 파일을 삭제할 수 있습니다.")
        if not revision["FileId"]:
            raise errors.not_found("NO_FILE", "업로드된 파일이 없습니다.")
        conn.execute(
            "UPDATE TB_DWG_Revision SET FileId = NULL, FileNm = NULL WHERE DrawingId = ? AND RevNo = ?", (drawing_id, rev_no)
        )
    files.remove([revision["FileId"]])


def add_plan(conn: sqlite3.Connection, drawing_id: int, plan_id: int, required: bool) -> dict:
    ensure(conn, drawing_id)
    plans.add_link(conn, plan_id, drawing_id, required)
    return linked_plans(conn, drawing_id)
