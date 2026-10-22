import sys, json, os, subprocess, re
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
ROOT = Path(__file__).resolve().parents[1]


class Result:
    def __init__(self, r):
        fields = r.get("fields", [])
        self.rows = []
        for row in r.get("rows", []):
            values = []
            for f in fields:
                v = row[f["name"]]
                if f.get("dataTypeID") in (1184, 1114) and v:
                    v = datetime.fromisoformat(v.replace("Z", "+00:00"))
                values.append(v)
            self.rows.append(tuple(values))

    def fetchone(self):
        return self.rows[0] if self.rows else None

    def fetchall(self):
        return self.rows


class WasmDB:
    def __init__(self):
        self.process = subprocess.Popen(
            ["node", str(ROOT / "tests/pglite_bridge.mjs")],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
        )

    def execute(self, sql, params=None):
        if params is not None:
            i = iter(range(1, len(params) + 1))
            sql = re.sub("%s", lambda _: "$" + str(next(i)), sql)
        self.process.stdin.write(json.dumps({"sql": sql, "params": params}) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError(
                "PGlite bridge stopped. Install npm dependency or set TEST_DATABASE_URL."
            )
        r = json.loads(line)
        if not r["ok"]:
            raise RuntimeError(r["error"])
        return Result(r)

    def rollback(self):
        self.execute("rollback")

    def commit(self):
        self.execute("commit")

    @contextmanager
    def transaction(self):
        self.execute("savepoint nested_test")
        try:
            yield self
            self.execute("release savepoint nested_test")
        except BaseException:
            self.execute("rollback to savepoint nested_test")
            raise

    def close(self):
        self.process.stdin.close()
        self.process.wait(timeout=10)


@pytest.fixture(scope="session")
def database():
    if os.getenv("TEST_DATABASE_URL"):
        import psycopg

        db = psycopg.connect(os.environ["TEST_DATABASE_URL"], autocommit=True)
    else:
        db = WasmDB()
    for role in ("anon", "authenticated", "service_role"):
        db.execute(
            f"do $$ begin create role {role}; exception when duplicate_object then null; end $$"
        )
    db.execute((ROOT / "tests/schema_before.sql").read_text())
    db.execute(
        "insert into users(user_id,is_paid,subscription_tier) values(99,true,'forever')"
    )
    db.execute((ROOT / "migrations/001_victoria_v4.sql").read_text())
    yield db
    db.close()


@pytest.fixture
def db(database):
    database.execute("begin")
    yield database
    database.execute("rollback")
