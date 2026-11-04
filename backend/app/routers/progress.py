import sqlite3

from fastapi import APIRouter, Depends

from ..db import get_db
from ..deps import require
from ..schemas import ProgressIn
from ..services import progress

router = APIRouter(prefix="/api", tags=["progress"])
view = require("M22", "View")
write = require("M22", "Write")
Conn = sqlite3.Connection


@router.get("/progress-hulls", dependencies=[Depends(view)])
def progress_hulls(conn: Conn = Depends(get_db)):
    return progress.progress_hulls(conn)


@router.get("/hulls/{hull_no}/progress-targets", dependencies=[Depends(view)])
def targets(hull_no: str, include_done: bool = False, conn: Conn = Depends(get_db)):
    return progress.targets(conn, hull_no, include_done)


@router.get("/plans/{plan_id}/progress", dependencies=[Depends(view)])
def detail(plan_id: int, conn: Conn = Depends(get_db)):
    return progress.detail(conn, plan_id)


@router.put("/plans/{plan_id}/progress/{work_dt}", dependencies=[Depends(write)])
def save(plan_id: int, work_dt: str, body: ProgressIn, conn: Conn = Depends(get_db)):
    return progress.save(conn, plan_id, work_dt, body.model_dump())


@router.delete("/progress/{progress_id}", dependencies=[Depends(write)])
def delete(progress_id: int, conn: Conn = Depends(get_db)):
    return progress.delete(conn, progress_id)
