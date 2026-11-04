import pytest

P = dict(proc_cd="CUT", plan_start_dt="2026-11-01", plan_end_dt="2026-11-10")


def plan_id(conn, hull, block_cd, proc):
    return conn.execute(
        "SELECT p.PlanId FROM TB_PRC_Plan p JOIN TB_MST_Block b ON b.BlockId=p.BlockId"
        " WHERE p.HullNo=? AND b.BlockCd=? AND p.ProcCd=?",
        (hull, block_cd, proc),
    ).fetchone()[0]


def test_t01_list_and_order(client, conn, login):
    h = login("choi.qa")
    body = client.get("/api/hulls/8001/plans", headers=h).json()
    assert body["hull_progress"] == 65 and body["today"] == "2026-10-19" and len(body["plans"]) == 27
    assert [p["label"] for p in body["plans"][:2]] == ["[101] 강재절단", "[101] 소조립"]
    block = conn.execute("SELECT BlockId FROM TB_MST_Block WHERE HullNo='8001' AND BlockCd='201'").fetchone()[0]
    filtered = client.get(f"/api/hulls/8001/plans?block_id={block}", headers=h).json()
    assert filtered["hull_progress"] == 65 and len(filtered["plans"]) == 5
    assert all(d["plan_id"] in {p["plan_id"] for p in filtered["plans"]} for d in filtered["deps"])
    assert client.get("/api/hulls/8004/plans", headers=h).json()["hull_progress"] is None
    assert [x["plan_count"] for x in client.get("/api/plan-hulls", headers=h).json()][3] == 0
    assert client.get("/api/users/options", headers=h).json()[0].keys() == {"emp_no", "display_name"}
    assert len(client.get("/api/procs", headers=h).json()) == 7


def test_block_less_plan_sorted_last(client, login):
    h = login("park.pm")
    client.post("/api/hulls/8001/plans", json=P, headers=h)
    labels = [p["label"] for p in client.get("/api/hulls/8001/plans", headers=h).json()["plans"]]
    assert labels[-1] == "[호선] 시운전" and labels[-3:].count("[호선] 강재절단") == 1
    assert all(label.startswith("[호선]") for label in labels[labels.index("[호선] 강재절단"):])


@pytest.mark.parametrize(
    "patch,message",
    [
        ({"plan_start_dt": ""}, "계획 시작/종료일을 입력하세요."),
        ({"plan_end_dt": "2026-10-01"}, "계획 종료일이 시작일보다 빠릅니다."),
        ({"block_id": 99999}, "해당 호선의 블록이 아닙니다."),
        ({"proc_cd": "X"}, "허용되지 않는 공정 코드입니다."),
        ({"manager_emp_no": "jung.new"}, "승인된 회원만 담당자로 지정할 수 있습니다."),
    ],
)
def test_t02_validation(client, login, patch, message):
    res = client.post("/api/hulls/8001/plans", json={**P, **patch}, headers=login("park.pm"))
    assert res.status_code == 400 and res.json()["message"] == message


def test_create_defaults_and_update_preserves_progress(client, conn, login):
    h = login("park.pm")
    res = client.post("/api/hulls/8004/plans", json={**P, "manager_emp_no": "han.wk"}, headers=h)
    assert res.status_code == 201
    body = res.json()
    assert body["progress_rate"] == 0 and body["plan_status"] == "READY" and body["manager_nm"]
    pid = plan_id(conn, "8001", "201", "ERECT")
    before = conn.execute("SELECT ProgressRate, ActualStartDt FROM TB_PRC_Plan WHERE PlanId=?", (pid,)).fetchone()
    res = client.patch(f"/api/plans/{pid}", json={"remark": "메모"}, headers=h)
    assert res.status_code == 200 and res.json()["remark"] == "메모"
    assert res.json()["progress_rate"] == before[0] and res.json()["actual_start_dt"] == before[1]


def test_t03_self_and_cycle(client, conn, login):
    h = login("park.pm")
    a, b = plan_id(conn, "8003", "101", "CUT"), plan_id(conn, "8003", "101", "SUBASM")
    res = client.put(f"/api/plans/{a}/predecessors", json={"pred_plan_ids": [a]}, headers=h)
    assert res.status_code == 400 and res.json()["code"] == "PLAN_DEPENDENCY_SELF"
    res = client.put(f"/api/plans/{a}/predecessors", json={"pred_plan_ids": [b]}, headers=h)
    assert res.status_code == 400 and res.json()["code"] == "PLAN_DEPENDENCY_CYCLE"
    other = plan_id(conn, "8001", "101", "CUT")
    res = client.put(f"/api/plans/{a}/predecessors", json={"pred_plan_ids": [other]}, headers=h)
    assert res.status_code == 400 and res.json()["message"] == "선행 공정은 같은 호선의 공정이어야 합니다."


def test_t04_late_pred_confirm(client, conn, login):
    h = login("park.pm")
    late, target = plan_id(conn, "8003", "301", "CUT"), plan_id(conn, "8003", "101", "CUT")
    before = conn.execute("SELECT COUNT(*) FROM TB_PRC_PlanDep WHERE PlanId=?", (target,)).fetchone()[0]
    res = client.put(f"/api/plans/{target}/predecessors", json={"pred_plan_ids": [late]}, headers=h)
    assert res.status_code == 409 and res.json()["code"] == "PRED_LATE_CONFIRM_REQUIRED"
    assert res.json()["details"]["late_pred_plan_ids"] == [late]
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_PlanDep WHERE PlanId=?", (target,)).fetchone()[0] == before
    body = {"pred_plan_ids": [late], "confirm_late_preds": True}
    res = client.put(f"/api/plans/{target}/predecessors", json=body, headers=h)
    assert res.status_code == 200 and res.json()["pred_plan_ids"] == [late]
    assert conn.execute("SELECT LagDays FROM TB_PRC_PlanDep WHERE PlanId=?", (target,)).fetchone()[0] == 0


def make_ready_case(client, conn, h):
    a = client.post("/api/hulls/8004/plans", json=P, headers=h).json()["plan_id"]
    b = client.post(
        "/api/hulls/8004/plans",
        json={**P, "plan_start_dt": "2026-11-11", "plan_end_dt": "2026-11-20", "pred_plan_ids": [a]},
        headers=h,
    ).json()["plan_id"]
    drawing = conn.execute(
        "INSERT INTO TB_DWG_Drawing (DrawingNo, DrawingNm, HullNo) VALUES ('T-9','x','8004')"
    ).lastrowid
    conn.execute("INSERT INTO TB_DWG_Revision (DrawingId, RevNo) VALUES (?,0)", (drawing,))
    return a, b, drawing


def test_t05_t06_t08_gate_with_links(client, conn, login):
    h = login("park.pm")
    a, b, drawing = make_ready_case(client, conn, h)
    assert client.get(f"/api/plans/{b}", headers=h).json()["plan_status"] == "PLAN"
    conn.execute("UPDATE TB_PRC_Plan SET ProgressRate=100 WHERE PlanId=?", (a,))
    res = client.post(f"/api/plans/{b}/drawings", json={"drawing_id": drawing, "required": True}, headers=h)
    assert res.status_code == 201
    assert res.json()["links"][0]["need_dt"] == "2026-11-11" and res.json()["blockers"][0]["drawing_no"] == "T-9"
    plan = client.get(f"/api/plans/{b}", headers=h).json()
    assert plan["plan_status"] == "PLAN" and plan["drawing_wait"] is True and plan["gate_ok"] is False
    conn.execute("UPDATE TB_DWG_Revision SET RevStatus='ISSUED' WHERE DrawingId=?", (drawing,))
    assert client.delete(f"/api/plans/{b}/drawings/{drawing}", headers=h).status_code == 204
    assert client.get(f"/api/plans/{b}", headers=h).json()["plan_status"] == "READY"
    res = client.delete(f"/api/plans/{b}/drawings/{drawing}", headers=h)
    assert res.status_code == 404 and res.json()["code"] == "LINK_NOT_FOUND"


def test_link_errors(client, conn, login):
    h = login("park.pm")
    pid = plan_id(conn, "8001", "101", "CUT")
    linked = conn.execute("SELECT DrawingId FROM TB_DWG_PlanLink WHERE PlanId=?", (pid,)).fetchone()[0]
    res = client.post(f"/api/plans/{pid}/drawings", json={"drawing_id": linked}, headers=h)
    assert res.status_code == 409 and res.json()["message"] == "이미 연계된 도면입니다."
    other = conn.execute("SELECT DrawingId FROM TB_DWG_Drawing WHERE HullNo='8003'").fetchone()[0]
    res = client.post(f"/api/plans/{pid}/drawings", json={"drawing_id": other}, headers=h)
    assert res.status_code == 400 and res.json()["message"] == "같은 호선의 도면만 연계할 수 있습니다."
    assert client.post(f"/api/plans/{pid}/drawings", json={"drawing_id": 99999}, headers=h).json()["code"] == "DRAWING_NOT_FOUND"
    assert client.get("/api/plans/99999/drawings", headers=h).json()["code"] == "PLAN_NOT_FOUND"
    body = client.get(f"/api/plans/{pid}/drawings", headers=h).json()
    assert body["available"] and all(a["drawing_id"] != linked for a in body["available"])


def test_t07_delete_no_orphans(client, conn, login):
    pid = plan_id(conn, "8001", "201", "ERECT")
    assert client.delete(f"/api/plans/{pid}", headers=login("park.pm")).status_code == 204
    for table, col in (
        ("TB_PRC_Progress", "PlanId"), ("TB_PRC_PlanDep", "PlanId"), ("TB_PRC_PlanDep", "PredPlanId"), ("TB_DWG_PlanLink", "PlanId"),
    ):
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col}=?", (pid,)).fetchone()[0] == 0


def test_t09_view_write_403(client, conn, login):
    h = login("choi.qa")
    pid = plan_id(conn, "8001", "101", "CUT")
    for res in (
        client.post("/api/hulls/8001/plans", json=P, headers=h),
        client.patch(f"/api/plans/{pid}", json={}, headers=h),
        client.delete(f"/api/plans/{pid}", headers=h),
        client.put(f"/api/plans/{pid}/predecessors", json={"pred_plan_ids": []}, headers=h),
        client.post(f"/api/plans/{pid}/drawings", json={"drawing_id": 1}, headers=h),
        client.delete(f"/api/plans/{pid}/drawings/1", headers=h),
    ):
        assert res.status_code == 403
