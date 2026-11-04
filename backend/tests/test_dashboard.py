from test_drawings import decide, did, new, request, waiting_id
from test_plans import plan_id


def get(client, h):
    return client.get("/api/dashboard/summary", headers=h).json()


def test_seed_values(client, login):
    body = get(client, login("choi.qa"))
    assert {k: v["value"] for k, v in body["kpi"].items()} == {
        "active_hulls": 4, "delay_plans": 1, "waiting_plans": 8, "pending_drawings": 6,
    }
    assert [h["progress"] for h in body["hull_progress"]] == [65, 17, 0, 0, 94]
    assert {x["status"]: x["count"] for x in body["plan_status"]} == {"PLAN": 39, "READY": 0, "WORK": 7, "DONE": 36, "DELAY": 1}
    assert [x["status"] for x in body["plan_status"]] == ["PLAN", "READY", "WORK", "DONE", "DELAY"]
    assert [(d["name"], d["total"]) for d in body["drawing_disciplines"]] == [("선체", 17), ("전장", 15), ("배관", 15)]
    assert body["delay_list"]["items"][0]["label"] == "[301] 도장"
    assert body["impact_list"]["count"] == 3


def test_t01_progress_updates_aggregate(client, conn, login):
    h = login("park.pm")
    pid = plan_id(conn, "8001", "301", "PAINT")
    client.put(f"/api/plans/{pid}/progress/2026-10-19", json={"progress_rate": 100}, headers=h)
    body = get(client, h)
    assert body["kpi"]["delay_plans"]["value"] == 0 and body["delay_list"]["count"] == 0


def test_t02_required_link_changes_wait_count(client, conn, login):
    lee, pm, admin = login("lee.dwg"), login("park.pm"), login("admin")
    plan = client.post("/api/hulls/8004/plans", json={"proc_cd": "CUT", "plan_start_dt": "2026-11-01", "plan_end_dt": "2026-11-10"}, headers=pm).json()
    pk = new(client, lee).json()["drawing_id"]
    client.post(f"/api/plans/{plan['plan_id']}/drawings", json={"drawing_id": pk, "required": True}, headers=pm)
    body = get(client, pm)
    assert body["kpi"]["waiting_plans"]["value"] == 9
    assert body["waiting_list"]["count"] == 9
    request(client, lee, pk, 0)
    decide(client, lee, waiting_id(client, lee, pk))
    decide(client, admin, waiting_id(client, admin, pk))
    client.post(f"/api/drawings/{pk}/revisions/0/issue", headers=lee)
    assert get(client, pm)["kpi"]["waiting_plans"]["value"] == 8


def test_t03_impact_rules(client, conn, login):
    h = login("choi.qa")
    items = get(client, h)["impact_list"]["items"]
    assert all(i["plan_status"] in ("WORK", "DONE", "DELAY") and i["rev_no"] >= 1 for i in items)
    assert items[0]["link"] == {"screen": "drawing", "param": items[0]["drawing_id"]}
    conn.execute("UPDATE TB_DWG_Revision SET IssueDt='2026-09-18' WHERE IssueDt='2026-09-23'")
    assert get(client, h)["impact_list"]["count"] == 2
    conn.execute("UPDATE TB_DWG_Revision SET IssueDt='2026-09-19' WHERE IssueDt='2026-09-18'")
    assert get(client, h)["impact_list"]["count"] == 3


def test_t04_monthly_deliveries(client, conn, login):
    h = login("choi.qa")
    conn.execute("UPDATE TB_MST_Hull SET DeliveryDt='2027-06-01' WHERE HullNo='8002'")
    body = get(client, h)["deliveries"]
    assert {"month": "2027-06", "count": 2, "hull_nos": ["8001", "8002"]} in body
    assert [x["month"] for x in body] == sorted(x["month"] for x in body)


def test_t05_links(client, login):
    body = get(client, login("choi.qa"))
    assert body["kpi"]["active_hulls"]["link"]["screen"] == "hull-list"
    assert body["kpi"]["pending_drawings"]["link"]["screen"] == "dwg-approval"
    item = body["waiting_list"]["items"][0]
    assert item["link"] == {"screen": "plan-gantt", "param": item["hull_no"]} and item["blockers"]


def test_t06_six_items_max(client, login):
    body = get(client, login("choi.qa"))
    assert body["waiting_list"]["count"] == 8 and len(body["waiting_list"]["items"]) == 6
    starts = [x["plan_start_dt"] for x in body["waiting_list"]["items"]]
    assert starts == sorted(starts)


def test_use_yn_excluded(client, conn, login):
    conn.execute("UPDATE TB_MST_Hull SET UseYN=0 WHERE HullNo='8001'")
    body = get(client, login("choi.qa"))
    assert [h["hull_no"] for h in body["hull_progress"]] == ["8002", "8003", "8004", "8005"]
