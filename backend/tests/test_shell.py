from app.services import weather


def tokens(client, headers):
    return {m["token"]: m for m in client.get("/api/me/menu", headers=headers).json() if m["token"]}


def test_t01_menu_by_group(client, login):
    assert set(tokens(client, login("choi.qa"))) == {"dashboard", "hull-list", "plan-gantt", "progress", "dwg-list", "dwg-approval"}
    pm = tokens(client, login("park.pm"))
    assert "dwg-approval" not in pm and "user-mgmt" not in pm
    assert pm["hull-list"]["can_write"] is True and pm["dwg-list"]["can_write"] is False
    assert pm["hull-list"]["auth_gbn"] == "Write"
    dwg = tokens(client, login("lee.dwg"))
    assert "progress" not in dwg and dwg["dwg-approval"]["can_write"] is True
    assert client.post("/api/me/menu-access", json={"menu_id": "M91"}, headers=login("park.pm")).status_code == 403


def test_menu_requires_visible_parent(client, conn, login):
    conn.execute("DELETE FROM TB_SYS_AuthMenu WHERE MenuId='M20' AND AuthCd='PROC'")
    assert "plan-gantt" not in tokens(client, login("park.pm"))


def test_permission_change_applies_immediately(client, conn, login):
    headers = login("park.pm")
    conn.execute("DELETE FROM TB_SYS_AuthUser WHERE EmpNo='park.pm'")
    assert client.get("/api/me/menu", headers=headers).json() == []


def test_menu_access_logged(client, conn, login):
    assert client.post("/api/me/menu-access", json={"menu_id": "M00"}, headers=login("park.pm")).status_code == 204
    assert conn.execute("SELECT MenuId FROM TB_SYS_LogMenuAccess").fetchone()["MenuId"] == "M00"


def test_weather_regions(client, login):
    headers = login("park.pm")
    body = client.get("/api/weather", params={"region": "거제"}, headers=headers).json()
    assert body["source"] == "SAMPLE" and body["tempC"] == 18.9 and body["region"] == "거제" and body["error"]
    assert client.get("/api/weather", params={"region": "부산"}, headers=headers).status_code == 400
    assert client.get("/api/weather").status_code == 401


def test_weather_provider_fallback(client, login, monkeypatch):
    headers = login("park.pm")
    def fail(_):
        raise RuntimeError("boom")
    monkeypatch.setitem(weather.PROVIDERS, "bad", fail)
    monkeypatch.setitem(weather.PROVIDERS, "odd", lambda _: {"tempC": 1})
    good = {"obsDt": "x", "tempC": 1.0, "condition": "맑음", "humidity": 1, "windMs": 1.0}
    monkeypatch.setitem(weather.PROVIDERS, "good", lambda _: good)
    for name, source in (("bad", "SAMPLE"), ("odd", "SAMPLE"), ("none", "SAMPLE"), ("good", "LIVE")):
        monkeypatch.setenv("WEATHER_PROVIDER", name)
        body = client.get("/api/weather", headers=headers).json()
        assert body["source"] == source and bool(body["error"]) == (source == "SAMPLE")
