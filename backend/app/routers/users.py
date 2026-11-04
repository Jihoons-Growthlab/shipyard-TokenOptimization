import sqlite3

from fastapi import APIRouter, Depends, Response

from ..db import get_db
from ..deps import Principal, require
from ..schemas import ApproveIn, UserCreateIn, UserUpdateIn
from ..services import users

admin = require("M91", "Admin")
router = APIRouter(prefix="/api", tags=["users"])
Conn = sqlite3.Connection


@router.get("/users", dependencies=[Depends(admin)])
def list_users(status: str = "", q: str = "", conn: Conn = Depends(get_db)):
    return users.list_users(conn, status, q)


@router.post("/users", status_code=201, dependencies=[Depends(admin)])
def create(body: UserCreateIn, conn: Conn = Depends(get_db)):
    return users.create_user(conn, body.model_dump())


@router.get("/users/{emp_no}", dependencies=[Depends(admin)])
def get_user(emp_no: str, conn: Conn = Depends(get_db)):
    return users.get_user(conn, emp_no)


@router.patch("/users/{emp_no}", dependencies=[Depends(admin)])
def update(emp_no: str, body: UserUpdateIn, conn: Conn = Depends(get_db)):
    return users.update_user(conn, emp_no, body.model_dump(exclude_unset=True))


@router.delete("/users/{emp_no}", status_code=204)
def delete(emp_no: str, actor: Principal = Depends(admin), conn: Conn = Depends(get_db)):
    users.delete_user(conn, emp_no, actor.emp_no)
    return Response(status_code=204)


@router.post("/users/{emp_no}/approve", dependencies=[Depends(admin)])
def approve(emp_no: str, body: ApproveIn, conn: Conn = Depends(get_db)):
    return users.approve(conn, emp_no, body.groups)


@router.post("/users/{emp_no}/reject", dependencies=[Depends(admin)])
def reject(emp_no: str, conn: Conn = Depends(get_db)):
    return users.reject(conn, emp_no)


@router.get("/auth-groups", dependencies=[Depends(admin)])
def auth_groups(conn: Conn = Depends(get_db)):
    return users.auth_groups(conn)
