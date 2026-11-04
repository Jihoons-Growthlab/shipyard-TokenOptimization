import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import Principal, require
from ..schemas import DecisionIn
from ..services import approvals

router = APIRouter(prefix="/api/approvals", tags=["approvals"])
Conn = sqlite3.Connection


@router.get("/inbox")
def inbox(user: Principal = Depends(require("M33", "View")), conn: Conn = Depends(get_db)):
    return approvals.inbox(conn, user.emp_no)


@router.post("/{approval_id}/decision")
def decision(
    approval_id: int, body: DecisionIn, user: Principal = Depends(require("M33", "Write")), conn: Conn = Depends(get_db)
):
    return approvals.decide(conn, approval_id, body.result, body.comment, user.emp_no)


@router.get("/history", dependencies=[Depends(require("M33", "View"))])
def history(conn: Conn = Depends(get_db)):
    return approvals.history(conn)
