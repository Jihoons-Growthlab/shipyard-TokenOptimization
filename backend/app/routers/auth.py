import sqlite3

from fastapi import APIRouter, Depends, Request, Response

from ..db import get_db
from ..deps import Principal, bearer, current_user
from ..schemas import LoginIn, OtpIn, RegisterIn
from ..services import accounts, auth

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.post("/login")
def login(body: LoginIn, request: Request, conn: sqlite3.Connection = Depends(get_db)):
    return auth.login(conn, body.emp_no, body.password, _ip(request))


@router.post("/otp/verify")
def otp_verify(
    body: OtpIn, request: Request, token: str = Depends(bearer), conn: sqlite3.Connection = Depends(get_db)
):
    return auth.verify_otp(conn, token, body.code, _ip(request))


@router.post("/register", status_code=201)
def register(body: RegisterIn, conn: sqlite3.Connection = Depends(get_db)):
    accounts.create(conn, body.model_dump())
    return {"emp_no": body.emp_no, "status": "pending", "message": "가입 신청이 완료되었습니다. 관리자 승인 후 로그인할 수 있습니다."}


@router.post("/logout", status_code=204)
def logout(user: Principal = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    auth.logout(conn, user.log_id)
    return Response(status_code=204)


@router.get("/me")
def me(user: Principal = Depends(current_user), conn: sqlite3.Connection = Depends(get_db)):
    return auth.profile(conn, user.emp_no)
