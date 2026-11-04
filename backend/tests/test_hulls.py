import pytest

NEW = {"hull_no": "9001", "hull_nm": "테스트선", "ship_type": "LNG", "contract_dt": "2026-01-01", "delivery_dt": "2028-01-01"}


def test_list_filters(client, login):
    h = login("choi.qa")
    body = client.get("/api/hulls", headers=h).json()
    assert [x["hull_no"] for x in body] == ["8001", "8002", "8003", "8004", "8005"]
    assert [x["progress"] for x in body] == [65, 17, 0, None, 94]
    assert body[0]["delay_count"] == 1 and body[3]["plan_count"] == 0
    assert [x["hull_no"] for x in client.get("/api/hulls?q=nordic", headers=h).json()] == ["8001", "8005"]
    assert len(client.get("/api/hulls?ship_type=LNG&status=BUILD", headers=h).json()) == 1


@pytest.mark.parametrize(
    "patch,status,message",
    [
        ({"hull_no": ""}, 400, "호선번호를 입력하세요."),
        ({"hull_no": "a b"}, 400, "호선번호는 영문/숫자/._- 1~20자입니다."),
        ({"hull_no": "8001"}, 409, "이미 존재하는 호선번호입니다."),
        ({"ship_type": "X"}, 400, "허용되지 않는 코드값입니다."),
        ({"contract_dt": "2026/01/01"}, 400, "날짜 형식(YYYY-MM-DD)이 올바르지 않습니다."),
        ({"delivery_dt": "2025-01-01"}, 400, "인도 예정일이 계약일보다 빠릅니다."),
        ({"length_m": -1}, 400, "0 이상의 값을 입력하세요."),
        ({"hull_status": ""}, 400, "상태를 선택하세요."),
    ],
)
def test_t02_rejects(client, login, patch, status, message):
    res = client.post("/api/hulls", json={**NEW, **patch}, headers=login("park.pm"))
    assert res.status_code == status and res.json()["message"] == message


def test_t03_create_defaults_and_milestones(client, login):
    h = login("park.pm")
    res = client.post("/api/hulls", json=NEW, headers=h)
    assert res.status_code == 201
    body = res.json()
    assert body["hull_status"] == "PLAN" and body["use_yn"] is True and body["create_user_id"] == "park.pm"
    assert body["create_dt"] == "2026-10-19" and body["progress"] is None
    ms = client.get("/api/hulls/9001/milestones", headers=h).json()
    assert [m["milestone_cd"] for m in ms] == ["CUT", "KEEL", "LAUNCH", "TRIAL", "DELIVER"]
    assert [m["plan_dt"] for m in ms] == [None, None, None, None, "2028-01-01"]


def test_t04_patch_only_sent_fields(client, login):
    h = login("park.pm")
    res = client.patch("/api/hulls/8001", json={"owner_nm": "새 선주"}, headers=h)
    assert res.status_code == 200
    body = res.json()
    assert body["owner_nm"] == "새 선주" and body["hull_nm"] == "SWP LNG 174K 1호"
    assert body["modify_user_id"] == "park.pm" and body["modify_dt"] == "2026-10-19"
    res = client.patch("/api/hulls/8001", json={"hull_no": "9"}, headers=h)
    assert res.json()["message"] == "호선번호는 수정할 수 없습니다."
    assert client.patch("/api/hulls/8001", json={"hull_status": None}, headers=h).status_code == 400
    assert client.patch("/api/hulls/8001", json={"delivery_dt": "2020-01-01"}, headers=h).status_code == 400
    res = client.patch("/api/hulls/none", json={}, headers=h)
    assert res.status_code == 404 and res.json()["code"] == "HULL_NOT_FOUND"


def test_milestones(client, login):
    h = login("park.pm")
    item = {"milestone_cd": "CUT", "plan_dt": "2026-06-15", "actual_dt": "2026-06-20"}
    body = client.put("/api/hulls/8001/milestones", json={"items": [item]}, headers=h).json()
    assert next(m for m in body if m["milestone_cd"] == "CUT")["diff_days"] == 5
    for items in ([item, item], [{**item, "milestone_cd": "ZZ"}]):
        res = client.put("/api/hulls/8001/milestones", json={"items": items}, headers=h)
        assert res.status_code == 400 and res.json()["message"] == "허용되지 않거나 중복된 일정 코드입니다."


def test_t05_block_code_unique_within_hull(client, login):
    h = login("park.pm")
    body = {"block_cd": "101", "block_nm": "x", "block_type": "FLAT", "weight_ton": 1}
    res = client.post("/api/hulls/8001/blocks", json=body, headers=h)
    assert res.status_code == 409 and res.json()["message"] == "이미 존재하는 블록코드입니다."
    assert client.post("/api/hulls/8004/blocks", json={**body, "block_cd": "ZZ1"}, headers=h).status_code == 201
    assert client.post("/api/hulls/8001/blocks", json={"block_cd": ""}, headers=h).json()["message"] == "블록코드를 입력하세요."
    assert client.post("/api/hulls/8001/blocks", json={"block_cd": "Q", "weight_ton": -1}, headers=h).status_code == 400
    assert client.post("/api/hulls/8001/blocks", json={"block_cd": "Q", "block_type": "X"}, headers=h).status_code == 400


def test_block_view(client, login):
    body = client.get("/api/hulls/8001/blocks", headers=login("choi.qa")).json()
    assert [b["block_cd"] for b in body] == ["101", "201", "301", "401", "501"]
    assert [b["progress"] for b in body] == [100, 90, 60, 56, 39]
    assert body[0]["plan_count"] == 5 and body[0]["drawing_count"] == 3


def test_t06_block_delete_keeps_drawing(client, conn, login):
    h = login("park.pm")
    block_id = conn.execute("SELECT BlockId FROM TB_MST_Block WHERE HullNo='8001' AND BlockCd='101'").fetchone()[0]
    drawing = conn.execute("SELECT DrawingId FROM TB_DWG_Drawing WHERE BlockId=?", (block_id,)).fetchone()[0]
    assert client.delete(f"/api/blocks/{block_id}", headers=h).status_code == 204
    assert conn.execute("SELECT BlockId FROM TB_DWG_Drawing WHERE DrawingId=?", (drawing,)).fetchone()[0] is None
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_Plan WHERE BlockId=?", (block_id,)).fetchone()[0] == 0
    res = client.delete(f"/api/blocks/{block_id}", headers=h)
    assert res.status_code == 404 and res.json()["code"] == "BLOCK_NOT_FOUND"


def test_t07_hull_delete_no_orphans(client, conn, login, db_file):
    from app.services import files

    conn.execute("UPDATE TB_DWG_Revision SET FileId='f1' WHERE DrawingId=1 AND RevNo=0")
    path = files.path_of("f1")
    path.parent.mkdir(parents=True)
    path.write_bytes(b"x")
    assert client.delete("/api/hulls/8001", headers=login("park.pm")).status_code == 204
    assert not path.exists()
    for table in ("TB_MST_Block", "TB_PRC_Plan", "TB_DWG_Drawing", "TB_MST_HullMilestone"):
        assert conn.execute(f"SELECT COUNT(*) FROM {table} WHERE HullNo='8001'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM TB_PRC_Progress WHERE PlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM TB_DWG_PlanLink WHERE PlanId NOT IN (SELECT PlanId FROM TB_PRC_Plan)").fetchone()[0] == 0


def test_t08_view_write_403(client, login):
    h = login("choi.qa")
    for res in (
        client.post("/api/hulls", json=NEW, headers=h),
        client.patch("/api/hulls/8001", json={}, headers=h),
        client.delete("/api/hulls/8001", headers=h),
        client.put("/api/hulls/8001/milestones", json={"items": []}, headers=h),
        client.post("/api/hulls/8001/blocks", json={"block_cd": "x"}, headers=h),
        client.delete("/api/blocks/1", headers=h),
    ):
        assert res.status_code == 403 and res.json()["details"]["menu_id"] == "M11"


def test_summary(client, login):
    body = client.get("/api/hulls/8001/summary", headers=login("choi.qa")).json()
    assert body["progress"] == 65 and body["plan_count"] == 27
    assert body["plan_status"] == {"PLAN": 6, "READY": 0, "WORK": 3, "DONE": 17, "DELAY": 1}
    assert body["drawing_status"] == {"ISSUED": 13, "APPROVED": 1, "REVIEW": 1, "DRAFT": 0} and body["drawing_count"] == 15
