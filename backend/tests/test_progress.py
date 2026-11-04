import pytest

from test_plans import plan_id


def put(client, h, pid, day, **body):
    return client.put(f"/api/plans/{pid}/progress/{day}", json={"progress_rate": 50, **body}, headers=h)


def test_t01_targets(client, login):
    h = login("choi.qa")
    body = client.get("/api/progress-hulls", headers=h).json()
    assert body["default_hull_no"] == "8001" and "8004" not in [x["hull_no"] for x in body["hulls"]]
    plans = client.get("/api/hulls/8001/progress-targets", headers=h).json()["plans"]
    assert [p["label"] for p in plans] == ["[201] 탑재", "[301] 도장", "[401] 도장", "[501] 대조립"]
    assert all(p["plan_status"] in ("READY", "WORK", "DELAY") for p in plans)
    assert len(client.get("/api/hulls/8001/progress-targets?include_done=true", headers=h).json()["plans"]) == 27


def test_t02_same_day_upsert(client, conn, login):
    h = login("park.pm")
    pid = plan_id(conn, "8001", "401", "PAINT")
    assert put(client, h, pid, "2026-10-19", progress_rate=40).status_code == 200
    body = put(client, h, pid, "2026-10-19", progress_rate=45, man_hour=8, worker_cnt=2, worker_emp_no="han.wk").json()
    day = [x for x in body["history"] if x["work_dt"] == "2026-10-19"]
    assert len(day) == 1 and day[0]["progress_rate"] == 45 and day[0]["worker_nm"]
    assert body["plan"]["progress_rate"] == 45


def test_t03_last_day_rate_not_sum(client, conn, login):
    h = login("park.pm")
    pid = plan_id(conn, "8003", "101", "CUT")
    conn.execute("UPDATE TB_DWG_Drawing SET DwgStatus='ISSUED' WHERE HullNo='8003'")
    put(client, h, pid, "2026-10-10", progress_rate=30)
    body = put(client, h, pid, "2026-10-12", progress_rate=20).json()  # 역행 허용
    assert body["plan"]["progress_rate"] == 20 and body["plan"]["actual_start_dt"] == "2026-10-10"
    assert [x["work_dt"] for x in body["history"]] == ["2026-10-12", "2026-10-10"]
    body = put(client, h, pid, "2026-10-11", progress_rate=90).json()  # 과거일 입력은 마지막 값에 영향 없음
    assert body["plan"]["progress_rate"] == 20


@pytest.mark.parametrize(
    "day,body,message",
    [
        ("2026-13-01", {"progress_rate": 1}, "작업일을 입력하세요."),
        ("2026-10-20", {"progress_rate": 1}, "미래 일자의 실적은 입력할 수 없습니다."),
        ("2026-10-19", {}, "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-19", {"progress_rate": 101}, "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-19", {"progress_rate": -1}, "진척률은 0~100 사이로 입력하세요."),
        ("2026-10-19", {"progress_rate": 1, "worker_emp_no": "jung.new"}, "승인된 회원만 작업자로 지정할 수 있습니다."),
    ],
)
def test_t04_rejects(client, conn, login, day, body, message):
    pid = plan_id(conn, "8001", "401", "PAINT")
    res = client.put(f"/api/plans/{pid}/progress/{day}", json=body, headers=login("park.pm"))
    assert res.status_code == 400 and res.json()["message"] == message


def test_negative_man_hour_allowed(client, conn, login):
    pid = plan_id(conn, "8001", "401", "PAINT")
    assert put(client, login("park.pm"), pid, "2026-10-19", man_hour=-1).status_code == 200


def test_t05_done_and_revert(client, conn, login):
    h = login("park.pm")
    pid = plan_id(conn, "8003", "101", "CUT")
    body = put(client, h, pid, "2026-10-19", progress_rate=100).json()
    assert body["plan"]["plan_status"] == "DONE" and body["plan"]["actual_end_dt"] == "2026-10-19"
    res = client.delete(f"/api/progress/{body['history'][0]['progress_id']}", headers=h)
    plan = res.json()["plan"]
    assert plan["progress_rate"] == 0 and plan["actual_start_dt"] is None and plan["actual_end_dt"] is None
    assert plan["plan_status"] == "PLAN"
    res = client.delete(f"/api/progress/{body['history'][0]['progress_id']}", headers=h)
    assert res.status_code == 404 and res.json()["code"] == "PROGRESS_NOT_FOUND"


def test_work_transitions_design_hull_to_build(client, conn, login):
    h = login("park.pm")
    assert conn.execute("SELECT HullStatus FROM TB_MST_Hull WHERE HullNo='8003'").fetchone()[0] == "DESIGN"
    pid = plan_id(conn, "8003", "101", "CUT")
    put(client, h, pid, "2026-10-19", progress_rate=10)
    assert conn.execute("SELECT HullStatus FROM TB_MST_Hull WHERE HullNo='8003'").fetchone()[0] == "BUILD"


def test_t06_view_write_403(client, conn, login):
    h = login("choi.qa")
    pid = plan_id(conn, "8001", "401", "PAINT")
    assert put(client, h, pid, "2026-10-19").status_code == 403
    assert client.delete("/api/progress/1", headers=h).status_code == 403
    assert client.get("/api/progress-hulls", headers=login("lee.dwg")).status_code == 403
