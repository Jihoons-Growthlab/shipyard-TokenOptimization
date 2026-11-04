"""`uv run init-db [--seed]`: 마이그레이션 적용 후 시드 적재. 반복 실행해도 안전하다."""
import argparse

from . import config, db


def main() -> None:
    parser = argparse.ArgumentParser(prog="init-db")
    parser.add_argument("--seed", action="store_true", help="시드 적재")
    args = parser.parse_args()
    conn = db.connect()
    applied = db.migrate(conn)
    print(f"migrations: {applied or '변경 없음'}")
    if args.seed:
        print("seed: 적재 완료" if db.seed(conn) else "seed: 이미 적재됨")
    print(f"db: {config.db_path()}")
