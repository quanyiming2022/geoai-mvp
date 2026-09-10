"""Apply tracked migrations to the existing Supabase DB; never start a second database."""
import hashlib
from pathlib import Path
import psycopg
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def connection():
    env = dotenv_values(ROOT / ".env")
    return psycopg.connect(host="127.0.0.1", port=env["GEOAI_DB_PORT"],
        user="postgres", password=env["POSTGRES_PASSWORD"], dbname="postgres", connect_timeout=5)


def migrate():
    with connection() as conn:
        conn.execute("SELECT pg_advisory_xact_lock(72610401)")
        conn.execute("CREATE TABLE IF NOT EXISTS geoai_internal.schema_migrations (name text PRIMARY KEY, sha256 text NOT NULL, applied_at timestamptz NOT NULL DEFAULT now())")
        conn.execute("ALTER TABLE geoai_internal.schema_migrations ENABLE ROW LEVEL SECURITY")
        conn.execute("REVOKE ALL ON geoai_internal.schema_migrations FROM PUBLIC, anon, authenticated")
        for path in sorted((ROOT / "supabase/migrations").glob("*.sql")):
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            row = conn.execute("SELECT sha256 FROM geoai_internal.schema_migrations WHERE name=%s", (path.name,)).fetchone()
            if row:
                if row[0] != digest:
                    raise RuntimeError("Applied migration checksum changed: " + path.name)
                continue
            conn.execute(path.read_text())
            conn.execute("INSERT INTO geoai_internal.schema_migrations(name,sha256) VALUES (%s,%s)", (path.name,digest))
            print("Applied: " + path.name)
    print("PASS: migrations up to date")


if __name__ == "__main__":
    migrate()
