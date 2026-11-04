from test_drawings import decide, did, new, request, waiting_id


def inbox(client, h):
    return client.get("/api/approvals/inbox", headers=h).json()


def start(client, lee):
    pk = new(client, lee).json()["drawing_id"]
    request(client, lee, pk, 0)
    return pk


def test_t01_step_two_waits_for_step_one(client, login):
    lee, admin = login("lee.dwg"), login("admin")
    pk = start(client, lee)
    assert pk not in [x["drawing_id"] for x in inbox(client, admin)["waiting"]]
    step2 = client.get(f"/api/drawings/{pk}", headers=lee).json()["approvals"][1]["approval_id"]
    res = decide(client, admin, step2)
    assert res.status_code == 409 and res.json()["code"] == "NOT_CURRENT_STEP"
    decide(client, lee, waiting_id(client, lee, pk))
    assert pk in [x["drawing_id"] for x in inbox(client, admin)["waiting"]]


def test_t02_not_assigned(client, login):
    lee = login("lee.dwg")
    pk = start(client, lee)
    res = decide(client, login("admin"), waiting_id(client, lee, pk))
    assert res.status_code == 403 and res.json()["code"] == "NOT_ASSIGNED_APPROVER"


def test_t03_reject(client, login):
    lee = login("lee.dwg")
    pk = start(client, lee)
    approval = waiting_id(client, lee, pk)
    res = decide(client, lee, approval, "REJECT", " ")
    assert res.status_code == 400 and res.json()["message"] == "반려 시 의견을 입력하세요."
    assert decide(client, lee, approval, "REJECT", "수정 필요").status_code == 200
    body = client.get(f"/api/drawings/{pk}", headers=lee).json()
    assert body["dwg_status"] == "DRAFT" and body["revisions"][0]["rev_status"] == "DRAFT"
    assert [(a["result"], a["comment"]) for a in body["approvals"]] == [("REJECT", "수정 필요")]
    res = decide(client, lee, approval)
    assert res.status_code == 409 and res.json()["code"] == "ALREADY_DECIDED"
    assert request(client, lee, pk, 0).status_code == 200


def test_decision_order(client, login):
    lee = login("lee.dwg")
    assert decide(client, lee, 999999, "X").json()["message"] == "결재 결과는 APPROVE 또는 REJECT 이어야 합니다."
    assert decide(client, lee, 999999).json()["code"] == "APPROVAL_NOT_FOUND"


def test_t04_both_steps_approved_default_comment(client, login):
    lee, admin = login("lee.dwg"), login("admin")
    pk = start(client, lee)
    decide(client, lee, waiting_id(client, lee, pk))
    res = decide(client, admin, waiting_id(client, admin, pk))
    assert pk in [x["drawing_id"] for x in res.json()["ready"]]
    approvals = client.get(f"/api/drawings/{pk}", headers=lee).json()["approvals"]
    assert approvals[1]["comment"] == "승인" and approvals[1]["act_dt"].startswith("2026-10-19 ")


def test_t05_ready_list(client, login):
    body = inbox(client, login("admin"))
    assert [(x["drawing_no"], x["rev_no"]) for x in body["ready"]] == [("8001-ELEC-401", 1), ("8003-HULL-101", 0)]
    assert body["ready"][0]["effect_plans"] == ["[401] 탑재"] and body["can_issue"] is True
    assert [x["drawing_no"] for x in body["waiting"]] == ["8002-HULL-401"]
    assert inbox(client, login("choi.qa"))["can_issue"] is False


def test_t06_history(client, login):
    body = client.get("/api/approvals/history", headers=login("choi.qa")).json()
    assert len(body) == 10 and body[0]["act_dt"] == "2026-11-26 16:00" and body[0]["drawing_no"] == "8002-ELEC-201"
    assert all(x["result"] != "WAIT" for x in body)


def test_permissions(client, conn, login):
    assert client.get("/api/approvals/inbox", headers=login("park.pm")).status_code == 403
    assert decide(client, login("choi.qa"), 1).status_code == 403
