import sqlite3

from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import Principal, require
from ..schemas import PlanIn, PlanLinkIn, PredecessorsIn
from ..services import plans

router = APIRouter(prefix="/api", tags=["plans"])
view = require("M21", "View")
write = require("M21", "Write")
Conn = sqlite3.Connection


@router.get("/plan-hulls", dependencies=[Depends(view)])
def plan_hulls(conn: Conn = Depends(get_db)):
    return plans.plan_hulls(conn)


@router.get("/hulls/{hull_no}/plans", dependencies=[Depends(view)])
def list_plans(hull_no: str, block_id: int | None = None, conn: Conn = Depends(get_db)):
    return plans.list_plans(conn, hull_no, block_id)


@router.post("/hulls/{hull_no}/plans", status_code=201)
def create_plan(hull_no: str, body: PlanIn, user: Principal = Depends(write), conn: Conn = Depends(get_db)):
    return plans.create_plan(conn, hull_no, body.model_dump(exclude_unset=True), user.emp_no)


@router.get("/plans/{plan_id}", dependencies=[Depends(view)])
def get_plan(plan_id: int, conn: Conn = Depends(get_db)):
    return plans.get_plan(conn, plan_id)


@router.patch("/plans/{plan_id}", dependencies=[Depends(write)])
def update_plan(plan_id: int, body: PlanIn, conn: Conn = Depends(get_db)):
    return plans.update_plan(conn, plan_id, body.model_dump(exclude_unset=True))


@router.delete("/plans/{plan_id}", status_code=204, dependencies=[Depends(write)])
def delete_plan(plan_id: int, conn: Conn = Depends(get_db)):
    plans.delete_plan(conn, plan_id)
    return Response(status_code=204)


@router.put("/plans/{plan_id}/predecessors", dependencies=[Depends(write)])
def predecessors(plan_id: int, body: PredecessorsIn, conn: Conn = Depends(get_db)):
    return plans.set_predecessors(conn, plan_id, body.pred_plan_ids, body.confirm_late_preds)


@router.get("/plans/{plan_id}/drawings", dependencies=[Depends(view)])
def plan_drawings(plan_id: int, conn: Conn = Depends(get_db)):
    return plans.plan_links(conn, plan_id)


@router.post("/plans/{plan_id}/drawings", status_code=201, dependencies=[Depends(write)])
def add_drawing(plan_id: int, body: PlanLinkIn, conn: Conn = Depends(get_db)):
    return plans.add_link(conn, plan_id, body.drawing_id, body.required)


@router.delete("/plans/{plan_id}/drawings/{drawing_id}", status_code=204, dependencies=[Depends(write)])
def remove_drawing(plan_id: int, drawing_id: int, conn: Conn = Depends(get_db)):
    plans.remove_link(conn, plan_id, drawing_id)
    return Response(status_code=204)
