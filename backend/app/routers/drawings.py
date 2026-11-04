import sqlite3
from urllib.parse import quote

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import FileResponse

from ..db import get_db
from ..deps import Principal, require
from ..schemas import ApprovalRequestIn, DrawingIn, DrawingPlanIn, RevisionIn
from ..services import drawings, plans

router = APIRouter(prefix="/api/drawings", tags=["drawings"])
view = require("M31", "View")
write = require("M31", "Write")
Conn = sqlite3.Connection


@router.get("", dependencies=[Depends(view)])
def list_drawings(hull_no: str = "", discipline: str = "", status: str = "", q: str = "", conn: Conn = Depends(get_db)):
    return drawings.list_drawings(conn, hull_no, discipline, status, q)


@router.post("", status_code=201)
def create(body: DrawingIn, user: Principal = Depends(write), conn: Conn = Depends(get_db)):
    return drawings.create_drawing(conn, body.model_dump(exclude_unset=True), user.emp_no)


@router.get("/{drawing_id}", dependencies=[Depends(view)])
def detail(drawing_id: int, conn: Conn = Depends(get_db)):
    return drawings.get_drawing(conn, drawing_id)


@router.patch("/{drawing_id}")
def update(drawing_id: int, body: DrawingIn, user: Principal = Depends(write), conn: Conn = Depends(get_db)):
    return drawings.update_drawing(conn, drawing_id, body.model_dump(exclude_unset=True), user.emp_no)


@router.delete("/{drawing_id}", status_code=204, dependencies=[Depends(write)])
def delete(drawing_id: int, conn: Conn = Depends(get_db)):
    drawings.delete_drawing(conn, drawing_id)
    return Response(status_code=204)


@router.get("/{drawing_id}/revisions", dependencies=[Depends(view)])
def revisions(drawing_id: int, conn: Conn = Depends(get_db)):
    return drawings.list_revisions(conn, drawing_id)


@router.post("/{drawing_id}/revisions", status_code=201)
def create_revision(drawing_id: int, body: RevisionIn, user: Principal = Depends(write), conn: Conn = Depends(get_db)):
    return drawings.create_revision(conn, drawing_id, body.change_desc, user.emp_no)


@router.post("/{drawing_id}/revisions/{rev_no}/pdf", status_code=201, dependencies=[Depends(write)])
async def upload_pdf(drawing_id: int, rev_no: int, request: Request, filename: str = "", conn: Conn = Depends(get_db)):
    length = request.headers.get("content-length")
    size = int(length) if length and length.isdigit() else None
    return await drawings.upload_pdf(
        conn, drawing_id, rev_no, filename, request.headers.get("content-type", ""), size, request.stream()
    )


@router.get("/{drawing_id}/revisions/{rev_no}/pdf", dependencies=[Depends(view)])
def get_pdf(drawing_id: int, rev_no: int, conn: Conn = Depends(get_db)):
    path, name = drawings.pdf_info(conn, drawing_id, rev_no)
    headers = {
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(name or 'drawing.pdf')}",
        "X-Content-Type-Options": "nosniff",
    }
    return FileResponse(path, media_type="application/pdf", headers=headers)


@router.delete("/{drawing_id}/revisions/{rev_no}/pdf", status_code=204, dependencies=[Depends(write)])
def delete_pdf(drawing_id: int, rev_no: int, conn: Conn = Depends(get_db)):
    drawings.delete_pdf(conn, drawing_id, rev_no)
    return Response(status_code=204)


@router.post("/{drawing_id}/revisions/{rev_no}/request-approval", dependencies=[Depends(write)])
def request_approval(drawing_id: int, rev_no: int, body: ApprovalRequestIn, conn: Conn = Depends(get_db)):
    return drawings.request_approval(conn, drawing_id, rev_no, body.reviewer_emp_no, body.approver_emp_no)


@router.post("/{drawing_id}/revisions/{rev_no}/issue", dependencies=[Depends(write)])
def issue(drawing_id: int, rev_no: int, conn: Conn = Depends(get_db)):
    return drawings.issue(conn, drawing_id, rev_no)


@router.get("/{drawing_id}/plans", dependencies=[Depends(view)])
def linked_plans(drawing_id: int, conn: Conn = Depends(get_db)):
    return drawings.linked_plans(conn, drawing_id)


@router.post("/{drawing_id}/plans", status_code=201, dependencies=[Depends(write)])
def add_plan(drawing_id: int, body: DrawingPlanIn, conn: Conn = Depends(get_db)):
    return drawings.add_plan(conn, drawing_id, body.plan_id, body.required)


@router.delete("/{drawing_id}/plans/{plan_id}", status_code=204, dependencies=[Depends(write)])
def remove_plan(drawing_id: int, plan_id: int, conn: Conn = Depends(get_db)):
    plans.remove_link(conn, plan_id, drawing_id)
    return Response(status_code=204)
