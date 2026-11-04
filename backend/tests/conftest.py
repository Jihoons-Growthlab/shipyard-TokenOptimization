import pytest

from app import config, db


@pytest.fixture(scope="session")
def _template(tmp_path_factory):
    """Argon2 해시 비용을 한 번만 쓰도록 시드 DB 원본을 재사용한다."""
    path = tmp_path_factory.mktemp("tpl") / "seed.db"
    conn = db.connect(path)
    db.migrate(conn)
    db.seed(conn)
    conn.close()
    return path.read_bytes()


@pytest.fixture
def db_file(tmp_path, monkeypatch, _template):
    path = tmp_path / "test.db"
    path.write_bytes(_template)
    monkeypatch.setenv("SHIPYARD_DB_PATH", str(path))
    monkeypatch.setenv("SHIPYARD_FILE_DIR", str(tmp_path / "files"))
    return path


@pytest.fixture
def conn(db_file):
    connection = db.connect(db_file)
    yield connection
    connection.close()


@pytest.fixture
def client(db_file):
    from fastapi.testclient import TestClient

    from app.main import app
    from app.services import auth

    auth.otp_failures.clear()
    auth.otp_last_step.clear()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def login(client):
    """login("park.pm") → Authorization 헤더. OTP 계정은 코드까지 처리한다."""
    from app.services import totp

    passwords = _demo_passwords()

    def _login(emp_no: str) -> dict:
        body = client.post("/api/auth/login", json={"emp_no": emp_no, "password": passwords[emp_no]}).json()
        if body.get("otp_required"):
            import time

            secret = _demo_secret(emp_no)
            code = totp.code_at(secret, int(time.time() // 30))
            headers = {"Authorization": f"Bearer {body['otp_token']}"}
            body = client.post("/api/auth/otp/verify", json={"code": code}, headers=headers).json()
        return {"Authorization": f"Bearer {body['access_token']}"}

    return _login


def _seed_users() -> list[dict]:
    import json

    data = json.loads(config.SEED_PATH.read_text())["users"]
    return [dict(zip(data["columns"], row)) for row in data["rows"]]


def _demo_passwords() -> dict:
    return {u["emp_no"]: u["demo_password"] for u in _seed_users()}


def _demo_secret(emp_no: str) -> str:
    return next(u["totp_secret"] for u in _seed_users() if u["emp_no"] == emp_no)
