import pytest

from app.services import drawings, files

D = dict(drawing_no="T-100", drawing_nm="시험도면", hull_no="8004", discipline="HULL", designer_emp_no="lee.dwg")
PDF = b"%PDF-1.4 test"


def did(conn, no):
    return conn.execute("SELECT DrawingId FROM TB_DWG_Drawing WHERE DrawingNo=?", (no,)).fetchone()[0]


def new(client, h, **patch):
    return client.post("/api/drawings", json={**D, **patch}, headers=h)


def upload(client, h, drawing, rev=0, data=PDF, name="a.pdf", ctype="application/pdf"):
    return client.post(
        f"/api/drawings/{drawing}/revisions/{rev}/pdf", params={"filename": name}, content=data,
        headers={**h, "Content-Type": ctype},
    )


def test_t01_filters_and_rev_labels(client, login):
    h = login("choi.qa")
    body = client.get("/api/drawings", headers=h).json()
    assert len(body) == 47 and body[0]["drawing_no"] == "8001-HULL-101"
    item = next(x for x in body if x["drawing_no"] == "8001-ELEC-401")
    assert (item["current_rev_no"], item["latest_rev_no"]) == (0, 1) and item["dwg_status"] == "APPROVED"
    assert all(x["hull_no"] == "8002" for x in client.get("/api/drawings?hull_no=8002", headers=h).json())
    assert all(x["discipline"] == "PIPE" for x in client.get("/api/drawings?discipline=PIPE", headers=h).json())
    assert len(client.get("/api/drawings?q=8001-hull", headers=h).json()) == 5


@pytest.mark.parametrize(
    "patch,message",
    [
        ({"drawing_no": ""}, "도면번호를 입력하세요."),
        ({"hull_no": ""}, "호선을 선택하세요."),
        ({"drawing_nm": ""}, "도면명을 입력하세요."),
        ({"discipline": "X"}, "허용되지 않는 분야입니다."),
        ({"block_id": 1}, "해당 호선의 블록이 아닙니다."),
        ({"designer_emp_no": "jung.new"}, "승인된 회원만 지정할 수 있습니다."),
    ],
)
def test_t02_t03_create_rejects(client, login, patch, message):
    res = new(client, login("lee.dwg"), **patch)
    assert res.status_code == 400 and res.json()["message"] == message


def test_t02_create_rev0_and_duplicate(client, login):
    h = login("lee.dwg")
    res = new(client, h)
    assert res.status_code == 201
    body = res.json()
    assert body["dwg_status"] == "DRAFT" and body["current_rev_no"] == 0 and body["latest_rev_no"] == 0
    assert body["revisions"][0]["rev_status"] == "DRAFT" and body["revisions"][0]["change_desc"] == "최초 작성"
    res = new(client, h)
    assert res.status_code == 409 and res.json()["message"] == "이미 존재하는 도면번호입니다."


def test_t03_update_restrictions(client, conn, login):
    h = login("lee.dwg")
    pk = did(conn, "8001-HULL-101")
    assert client.patch(f"/api/drawings/{pk}", json={"hull_no": "8002"}, headers=h).json()["message"] == "호선은 변경할 수 없습니다."
    assert client.patch(f"/api/drawings/{pk}", json={"drawing_no": "X"}, headers=h).json()["message"] == "도면번호는 변경할 수 없습니다."
    res = client.patch(f"/api/drawings/{pk}", json={"drawing_nm": "새 이름"}, headers=h)
    assert res.json()["drawing_nm"] == "새 이름" and res.json()["modify_user_id"] == "lee.dwg"


def test_t04_pdf_rules(client, conn, login):
    h = login("lee.dwg")
    pk = new(client, h).json()["drawing_id"]
    assert upload(client, h, pk, data=b"not pdf").json()["code"] == "INVALID_FILE_TYPE"
    assert upload(client, h, pk, name="a.txt", ctype="text/plain").json()["code"] == "INVALID_FILE_TYPE"
    res = upload(client, h, pk, data=PDF + b"x" * drawings.MAX_PDF)
    assert res.status_code == 413 and res.json()["code"] == "FILE_TOO_LARGE"
    assert list(files.path_of("x").parent.glob("*.pdf")) == []
    assert upload(client, h, pk, name="../../dir/도면.pdf").status_code == 201
    rev = client.get(f"/api/drawings/{pk}/revisions", headers=h).json()[0]
    assert rev["has_file"] is True and rev["file_nm"] == "도면.pdf"
    res = client.get(f"/api/drawings/{pk}/revisions/0/pdf", headers=h)
    assert res.content == PDF and res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["content-disposition"].startswith("inline")
    file_id = conn.execute("SELECT FileId FROM TB_DWG_Revision WHERE DrawingId=?", (pk,)).fetchone()[0]
    assert len(file_id) == 32 and files.path_of(file_id).exists()
    assert upload(client, h, pk, name="b.pdf").status_code == 201
    assert not files.path_of(file_id).exists()
    assert client.delete(f"/api/drawings/{pk}/revisions/0/pdf", headers=h).status_code == 204
    assert client.get(f"/api/drawings/{pk}/revisions/0/pdf", headers=h).json()["code"] == "NO_FILE"


def test_t04_only_draft_file_change(client, conn, login):
    h = login("lee.dwg")
    pk = did(conn, "8001-HULL-101")
    res = upload(client, h, pk)
    assert res.status_code == 409 and res.json()["message"] == "작성중(DRAFT) 리비전만 업로드할 수 있습니다."
    res = client.delete(f"/api/drawings/{pk}/revisions/0/pdf", headers=h)
    assert res.status_code == 409 and res.json()["message"] == "작성중(DRAFT) 리비전만 파일을 삭제할 수 있습니다."


def test_t05_seed_has_no_file(client, conn, login):
    h = login("choi.qa")
    pk = did(conn, "8001-PIPE-501")
    rev = client.get(f"/api/drawings/{pk}/revisions", headers=h).json()[0]
    assert rev["has_file"] is False and rev["file_nm"]
    assert client.get(f"/api/drawings/{pk}/revisions/2/pdf", headers=h).json()["code"] == "NO_FILE"


def test_pdf_disk_missing(client, conn, login):
    h = login("lee.dwg")
    pk = new(client, h).json()["drawing_id"]
    upload(client, h, pk)
    file_id = conn.execute("SELECT FileId FROM TB_DWG_Revision WHERE DrawingId=?", (pk,)).fetchone()[0]
    files.path_of(file_id).unlink()
    assert client.get(f"/api/drawings/{pk}/revisions/0/pdf", headers=h).json()["code"] == "FILE_NOT_FOUND"


def decide(client, headers, approval_id, result="APPROVE", comment=""):
    return client.post(f"/api/approvals/{approval_id}/decision", json={"result": result, "comment": comment}, headers=headers)


def waiting_id(client, headers, pk):
    return next(x["approval_id"] for x in client.get("/api/approvals/inbox", headers=headers).json()["waiting"] if x["drawing_id"] == pk)


def request(client, h, pk, rev):
    return client.post(
        f"/api/drawings/{pk}/revisions/{rev}/request-approval",
        json={"reviewer_emp_no": "lee.dwg", "approver_emp_no": "admin"}, headers=h,
    )


def test_t06_t07_revision_flow(client, conn, login):
    lee, admin = login("lee.dwg"), login("admin")
    pk = did(conn, "8001-PIPE-501")
    assert client.post(f"/api/drawings/{pk}/revisions", json={"change_desc": " "}, headers=lee).json()["message"] == "개정 사유를 입력하세요."
    body = client.post(f"/api/drawings/{pk}/revisions", json={"change_desc": "개정"}, headers=lee).json()
    assert body["latest_rev_no"] == 3 and body["current_rev_no"] == 2 and body["dwg_status"] == "DRAFT"
    assert body["revisions"][1]["rev_status"] == "ISSUED"
    res = client.post(f"/api/drawings/{pk}/revisions", json={"change_desc": "또"}, headers=lee)
    assert res.status_code == 409 and res.json()["code"] == "INVALID_REV_STATE"
    res = client.post(f"/api/drawings/{pk}/revisions/3/issue", headers=lee)
    assert res.status_code == 409 and res.json()["message"] == "승인(APPROVED)된 리비전만 배포할 수 있습니다."
    assert request(client, lee, pk, 2).status_code == 409
    assert request(client, lee, pk, 3).json()["dwg_status"] == "REVIEW"
    assert decide(client, lee, waiting_id(client, lee, pk)).json()["result"] == "APPROVE"
    decide(client, admin, waiting_id(client, admin, pk))
    assert client.get(f"/api/drawings/{pk}", headers=lee).json()["dwg_status"] == "APPROVED"
    body = client.post(f"/api/drawings/{pk}/revisions/3/issue", headers=lee).json()
    assert body["current_rev_no"] == 3 and body["dwg_status"] == "ISSUED"
    assert [r["rev_status"] for r in body["revisions"]] == ["ISSUED", "OBSOLETE", "OBSOLETE", "OBSOLETE"]
    assert body["revisions"][0]["issue_dt"] == "2026-10-19"


def test_request_validation(client, conn, login):
    lee = login("lee.dwg")
    pk = new(client, lee).json()["drawing_id"]
    url = f"/api/drawings/{pk}/revisions/0/request-approval"
    assert client.post(url, json={}, headers=lee).json()["message"] == "검토자와 승인자를 선택하세요."
    res = client.post(url, json={"reviewer_emp_no": "admin", "approver_emp_no": "admin"}, headers=lee)
    assert res.json()["message"] == "검토자와 승인자는 서로 다른 사람이어야 합니다."


def test_issue_incomplete_approval(client, conn, login):
    lee = login("lee.dwg")
    pk = new(client, lee).json()["drawing_id"]
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus='APPROVED' WHERE DrawingId=?", (pk,))
    res = client.post(f"/api/drawings/{pk}/revisions/0/issue", headers=lee)
    assert res.status_code == 409 and res.json()["code"] == "APPROVAL_INCOMPLETE"


def test_t07_issue_opens_gate(client, conn, login):
    lee, admin, pm = login("lee.dwg"), login("admin"), login("park.pm")
    plan = client.post("/api/hulls/8004/plans", json={"proc_cd": "CUT", "plan_start_dt": "2026-11-01", "plan_end_dt": "2026-11-10"}, headers=pm).json()
    assert plan["plan_status"] == "READY"
    pk = new(client, lee).json()["drawing_id"]
    res = client.post(f"/api/drawings/{pk}/plans", json={"plan_id": plan["plan_id"], "required": True}, headers=lee)
    assert res.status_code == 201 and res.json()["plans"][0]["required"] is True
    url = f"/api/plans/{plan['plan_id']}"
    assert client.get(url, headers=pm).json()["plan_status"] == "PLAN"
    request(client, lee, pk, 0)
    decide(client, lee, waiting_id(client, lee, pk))
    decide(client, admin, waiting_id(client, admin, pk))
    assert client.get(url, headers=pm).json()["plan_status"] == "PLAN"  # APPROVED만으로는 통과하지 못한다
    client.post(f"/api/drawings/{pk}/revisions/0/issue", headers=lee)
    assert client.get(url, headers=pm).json()["plan_status"] == "READY"


def test_t08_links_and_impacts(client, conn, login):
    h = login("lee.dwg")
    pk = did(conn, "8001-PIPE-501")
    body = client.get(f"/api/drawings/{pk}", headers=h).json()
    assert [i["rev_no"] for i in body["impacts"]] == [2] and body["impacts"][0]["plan_status"] in ("WORK", "DONE", "DELAY")
    link = body["plans"][0]
    assert link["label"] and body["available_plans"]
    assert client.delete(f"/api/drawings/{pk}/plans/{link['plan_id']}", headers=h).status_code == 204
    assert client.get(f"/api/drawings/{pk}", headers=h).json()["impacts"] == []
    assert client.delete(f"/api/drawings/{pk}/plans/{link['plan_id']}", headers=h).json()["code"] == "LINK_NOT_FOUND"


def test_t09_delete_no_orphans(client, conn, login):
    h = login("lee.dwg")
    pk = new(client, h).json()["drawing_id"]
    upload(client, h, pk)
    file_id = conn.execute("SELECT FileId FROM TB_DWG_Revision WHERE DrawingId=?", (pk,)).fetchone()[0]
    assert client.delete(f"/api/drawings/{pk}", headers=h).status_code == 204
    assert not files.path_of(file_id).exists()
    for table in ("TB_DWG_Revision", "TB_DWG_Approval", "TB_DWG_PlanLink"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE DrawingId=?", (pk,)).fetchone()[0] == 0
    assert client.get(f"/api/drawings/{pk}", headers=h).json()["code"] == "DRAWING_NOT_FOUND"


def test_t10_view_403(client, conn, login):
    h = login("choi.qa")
    pk = did(conn, "8002-PIPE-401")
    assert new(client, h).status_code == 403
    assert upload(client, h, pk).status_code == 403
    assert client.post(f"/api/drawings/{pk}/revisions/0/issue", headers=h).status_code == 403
    assert client.delete(f"/api/drawings/{pk}", headers=h).status_code == 403
    assert client.post(f"/api/drawings/{pk}/plans", json={"plan_id": 1}, headers=login("park.pm")).status_code == 403
