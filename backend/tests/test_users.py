import pytest

NEW = dict(
    last_name="홍", first_name="길동", birth_date="1990-01-02", phone="010-9999-8888", email="hong@swp.co.kr",
    emp_no="hong.gd", password="password1",
)


def test_t01_filter(client, login):
    h = login("admin")
    body = client.get("/api/users", headers=h).json()
    assert body["total"] == 6 and body["pending"] == 1 and "password_hash" not in body["users"][0]
    body = client.get("/api/users?status=pending", headers=h).json()
    assert [u["emp_no"] for u in body["users"]] == ["jung.new"] and body["total"] == 1
    assert client.get("/api/users?q=010-1111-0001", headers=h).json()["total"] == 1
    assert client.get("/api/users?q=없는값", headers=h).json()["pending"] == 1


@pytest.mark.parametrize(
    "patch,status,message",
    [
        ({"emp_no": "park.pm"}, 409, "이미 사용 중인 아이디입니다."),
        ({"email": "bad"}, 400, "이메일 형식이 올바르지 않습니다."),
        ({"status": "x"}, 400, "허용되지 않는 상태입니다."),
        ({"groups": ["X"]}, 400, "존재하지 않는 권한 그룹입니다."),
    ],
)
def test_t02_rejects(client, login, patch, status, message):
    res = client.post("/api/users", json={**NEW, **patch}, headers=login("admin"))
    assert res.status_code == status and res.json()["message"] == message


def test_t02_length(client, login):
    assert client.post("/api/users", json={**NEW, "last_name": "가" * 51}, headers=login("admin")).status_code == 422


def test_create_default_approved_with_group(client, login):
    h = login("admin")
    res = client.post("/api/users", json={**NEW, "groups": ["VIEW"]}, headers=h)
    assert res.status_code == 201
    assert res.json()["status"] == "approved" and res.json()["groups"] == [{"code": "VIEW", "name": "조회전용"}]
    assert client.post("/api/auth/login", json={"emp_no": "hong.gd", "password": "password1"}).status_code == 200


def test_t03_blank_password_keeps_hash(client, conn, login):
    h = login("admin")
    before = conn.execute("SELECT password_hash FROM users WHERE emp_no='han.wk'").fetchone()[0]
    res = client.patch("/api/users/han.wk", json={"last_name": "한", "first_name": "둘", "password": ""}, headers=h)
    assert res.status_code == 200 and res.json()["display_name"] == "한둘"
    assert conn.execute("SELECT password_hash FROM users WHERE emp_no='han.wk'").fetchone()[0] == before
    res = client.patch("/api/users/han.wk", json={"password": "short"}, headers=h)
    assert res.json()["message"] == "비밀번호는 8자 이상 입력하세요."
    assert client.patch("/api/users/han.wk", json={"password": "newpassword"}, headers=h).status_code == 200
    assert conn.execute("SELECT password_hash FROM users WHERE emp_no='han.wk'").fetchone()[0] != before


def test_update_duplicates_exclude_self(client, login):
    h = login("admin")
    me = client.get("/api/users/han.wk", headers=h).json()
    assert client.patch("/api/users/han.wk", json={"email": me["email"].upper(), "phone": me["phone"]}, headers=h).status_code == 200
    assert client.patch("/api/users/han.wk", json={"emp_no": "x"}, headers=h).json()["message"] == "아이디는 변경할 수 없습니다."
    assert client.patch("/api/users/han.wk", json={"email": "admin@swp.co.kr"}, headers=h).status_code == 409


def test_t04_group_change_applies(client, login):
    admin, pm = login("admin"), login("park.pm")
    assert client.get("/api/hulls", headers=pm).status_code == 200
    client.patch("/api/users/park.pm", json={"groups": []}, headers=admin)
    assert client.get("/api/hulls", headers=pm).status_code == 403
    client.patch("/api/users/park.pm", json={"groups": ["VIEW"]}, headers=admin)
    assert client.post("/api/hulls", json={"hull_no": "z"}, headers=pm).status_code == 403
    assert client.get("/api/hulls", headers=pm).status_code == 200


def test_t05_approve_then_login(client, login):
    h = login("admin")
    res = client.post("/api/users/jung.new/approve", json={"groups": []}, headers=h)
    assert res.json()["message"] == "승인 시 권한 그룹을 1개 이상 지정하세요."
    assert client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=h).json()["status"] == "approved"
    assert client.post("/api/auth/login", json={"emp_no": "jung.new", "password": "new12345"}).status_code == 200
    res = client.post("/api/users/jung.new/approve", json={"groups": ["VIEW"]}, headers=h)
    assert res.status_code == 409 and res.json()["code"] == "INVALID_STATUS"


def test_reject_api(client, login):
    assert client.post("/api/users/jung.new/reject", headers=login("admin")).json()["status"] == "rejected"


def test_t06_self_delete_and_references(client, conn, login):
    h = login("admin")
    res = client.delete("/api/users/admin", headers=h)
    assert res.status_code == 409 and res.json()["code"] == "SELF_DELETE"
    assert client.delete("/api/users/park.pm", headers=h).status_code == 204
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan WHERE ManagerEmpNo='park.pm'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM TB_SYS_AuthUser WHERE EmpNo='park.pm'").fetchone()[0] == 0
    res = client.delete("/api/users/park.pm", headers=h)
    assert res.status_code == 404 and res.json()["code"] == "USER_NOT_FOUND"


def test_t07_non_admin_403(client, login):
    h = login("park.pm")
    assert client.get("/api/users", headers=h).status_code == 403
    assert client.get("/api/auth-groups", headers=h).status_code == 403
    assert client.get("/api/users/options", headers=h).status_code == 200


def test_t08_secret_hidden_and_otp_toggle(client, conn, login):
    h = login("admin")
    body = client.get("/api/users/lee.dwg", headers=h).text
    assert "totp_secret" not in body and "password_hash" not in body and "JBSWY3" not in body
    res = client.patch("/api/users/park.pm", json={"totp_enabled": True}, headers=h)
    assert res.status_code == 409 and res.json()["code"] == "OTP_NOT_ENROLLED"
    assert client.post("/api/users", json={**NEW, "totp_enabled": True}, headers=h).json()["code"] == "OTP_NOT_ENROLLED"
    assert client.patch("/api/users/lee.dwg", json={"totp_enabled": False}, headers=h).json()["totp_enabled"] is False
    assert conn.execute("SELECT totp_secret FROM users WHERE emp_no='lee.dwg'").fetchone()[0]
