import time

import pytest

from app import config
from app.services import tokens, totp
from conftest import _demo_passwords, _demo_secret

NEW = dict(
    last_name="홍", first_name="길동", birth_date="1990-01-02", phone="01099998888", email="Hong@swp.co.kr",
    emp_no="hong.gd", password="password1", password_confirm="password1",
)


def post_login(client, emp_no, password=None):
    return client.post("/api/auth/login", json={"emp_no": emp_no, "password": password or _demo_passwords()[emp_no]})


def otp_headers(client, emp_no="admin"):
    return {"Authorization": f"Bearer {post_login(client, emp_no).json()['otp_token']}"}


def now_code(emp_no="admin", offset=0):
    return totp.code_at(_demo_secret(emp_no), int(time.time() // 30) + offset)


def test_rfc6238_vector():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890"
    assert totp.code_at(secret, 59 // 30) == "287082"
    assert totp.code_at(secret, 1111111109 // 30) == "081804"


def test_t01_login(client):
    res = post_login(client, "park.pm")
    assert res.status_code == 200
    body = res.json()
    assert body["otp_required"] is False and body["token_type"] == "bearer" and body["expires_in"] == 28800
    assert body["user"]["today"] == "2026-10-19"
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    assert me["emp_no"] == "park.pm" and me["groups"] and me == body["user"]


@pytest.mark.parametrize("emp_no,password", [("nouser", "x"), ("park.pm", "wrong-password")])
def test_invalid_credentials(client, emp_no, password):
    res = post_login(client, emp_no, password)
    assert res.status_code == 401
    assert res.json()["code"] == "INVALID_CREDENTIALS"
    assert res.json()["message"] == "아이디 또는 비밀번호가 올바르지 않습니다."


@pytest.mark.parametrize(
    "status,code", [("pending", "ACCOUNT_PENDING"), ("rejected", "ACCOUNT_REJECTED"), ("disabled", "ACCOUNT_DISABLED")]
)
def test_t02_account_status(client, conn, status, code):
    conn.execute("UPDATE users SET status=? WHERE emp_no='park.pm'", (status,))
    res = post_login(client, "park.pm")
    assert res.status_code == 403 and res.json()["code"] == code


def test_t03_otp_token_cannot_call_protected_api(client):
    assert client.get("/api/auth/me", headers=otp_headers(client)).status_code == 401
    assert client.get("/api/codes", headers=otp_headers(client)).status_code == 401


def test_otp_success_and_step_reuse(client):
    headers = otp_headers(client)
    code = now_code()
    res = client.post("/api/auth/otp/verify", json={"code": code}, headers=headers)
    assert res.status_code == 200 and res.json()["user"]["totp_enabled"] is True
    again = client.post("/api/auth/otp/verify", json={"code": code}, headers=otp_headers(client))
    assert again.status_code == 400 and again.json()["code"] == "OTP_INVALID"


def test_otp_lock_after_five_failures(client):
    headers = otp_headers(client)
    bad = "000000" if now_code() != "000000" else "000001"
    for _ in range(5):
        res = client.post("/api/auth/otp/verify", json={"code": bad}, headers=headers)
        assert res.status_code == 400
    res = client.post("/api/auth/otp/verify", json={"code": now_code()}, headers=headers)
    assert res.status_code == 429 and res.json()["code"] == "OTP_LOCKED"


def test_session_token_rejected_on_otp_verify(client, login):
    assert client.post("/api/auth/otp/verify", json={"code": "123456"}, headers=login("park.pm")).status_code == 401


@pytest.mark.parametrize(
    "patch,field",
    [
        ({"last_name": " "}, "name"),
        ({"birth_date": "1990-13-40"}, "birth_date"),
        ({"email": "a@b"}, "email"),
        ({"phone": "02-123-4567"}, "phone"),
        ({"emp_no": "a b"}, "emp_no"),
        ({"password": "short", "password_confirm": "short"}, "password"),
        ({"password_confirm": "different1"}, "password_confirm"),
    ],
)
def test_t04_validation(client, patch, field):
    res = client.post("/api/auth/register", json={**NEW, **patch})
    assert res.status_code == 400
    assert res.json()["code"] == "VALIDATION_ERROR" and res.json()["details"]["field"] == field


def test_validation_order(client):
    res = client.post("/api/auth/register", json={})
    assert res.json()["details"]["field"] == "name"


@pytest.mark.parametrize(
    "patch,message",
    [
        ({"emp_no": "park.pm"}, "이미 사용 중인 아이디입니다."),
        ({"email": "ADMIN@SWP.CO.KR"}, "이미 등록된 이메일입니다."),
        ({"phone": "01011110001"}, "이미 등록된 전화번호입니다."),
    ],
)
def test_t04_duplicates(client, patch, message):
    res = client.post("/api/auth/register", json={**NEW, **patch})
    assert res.status_code == 409 and res.json()["code"] == "DUPLICATE" and res.json()["message"] == message


def test_t05_register_pending(client, conn):
    res = client.post("/api/auth/register", json=NEW)
    assert res.status_code == 201 and res.json()["status"] == "pending" and res.json()["emp_no"] == "hong.gd"
    row = conn.execute("SELECT * FROM users WHERE emp_no='hong.gd'").fetchone()
    assert row["id"] == "u-hong.gd" and row["display_name"] == "홍길동" and row["phone"] == "010-9999-8888"
    assert row["created_at"] == "2026-10-19" and row["password_hash"].startswith("$argon2id$")
    assert conn.execute("SELECT 1 FROM TB_SYS_AuthUser WHERE EmpNo='hong.gd'").fetchone() is None
    assert post_login(client, "hong.gd", "password1").json()["code"] == "ACCOUNT_PENDING"


def test_t06_logout_then_401(client, login):
    headers = login("park.pm")
    assert client.post("/api/auth/logout", headers=headers).status_code == 204
    res = client.get("/api/auth/me", headers=headers)
    assert res.status_code == 401 and res.json()["code"] == "UNAUTHORIZED"


def test_t06_expired_token(client, conn):
    log_id = conn.execute("INSERT INTO TB_SYS_LogAccess (UserId, LoginDt) VALUES ('park.pm','x')").lastrowid
    token = tokens.issue("park.pm", "full", -10, lid=log_id)
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_status_change_invalidates_session(client, conn, login):
    headers = login("park.pm")
    conn.execute("UPDATE users SET status='disabled' WHERE emp_no='park.pm'")
    assert client.get("/api/auth/me", headers=headers).status_code == 401


def test_t07_access_log(client, conn, login):
    headers = login("lee.dwg")
    row = conn.execute("SELECT * FROM TB_SYS_LogAccess ORDER BY LogId DESC LIMIT 1").fetchone()
    assert row["UserId"] == "lee.dwg" and row["LoginDt"] and row["LogoutDt"] is None and row["IpAddress"]
    client.post("/api/auth/logout", headers=headers)
    row = conn.execute("SELECT * FROM TB_SYS_LogAccess WHERE LogId=?", (row["LogId"],)).fetchone()
    assert row["LogoutDt"]


def test_error_shapes(client):
    res = client.post("/api/auth/login", json={})
    assert res.status_code == 422 and res.json()["code"] == "INVALID_FORMAT"
    assert res.json()["message"] == "요청 형식이 올바르지 않습니다."
    assert client.get("/api/health").json() == {"status": "ok"}


def test_codes(client, login):
    assert client.get("/api/codes").status_code == 401
    codes = client.get("/api/codes", headers=login("park.pm")).json()
    assert {"code": "LNG", "name": "LNG운반선"} in codes["SHIPTYPE"]
