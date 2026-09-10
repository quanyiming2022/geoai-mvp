"""Generate only local .env files. Never print secrets or overwrite an existing file."""

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import time

root = Path(__file__).resolve().parents[1]
dest = root / ".env"
if dest.exists():
    raise SystemExit(".env already exists; refusing to rotate persisted credentials")
values = {}
for line in (root / ".env.example").read_text().splitlines():
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        values[k] = v
for key in [
    "POSTGRES_PASSWORD",
    "JWT_SECRET",
    "DASHBOARD_PASSWORD",
    "PG_META_CRYPTO_KEY",
    "S3_PROTOCOL_ACCESS_KEY_SECRET",
    "LOGFLARE_PUBLIC_ACCESS_TOKEN",
    "LOGFLARE_PRIVATE_ACCESS_TOKEN",
]:
    values[key] = secrets.token_hex(32)
values["SECRET_KEY_BASE"] = secrets.token_hex(48)
values["VAULT_ENC_KEY"] = secrets.token_hex(16)
values["REALTIME_DB_ENC_KEY"] = secrets.token_hex(8)
values["S3_PROTOCOL_ACCESS_KEY_ID"] = secrets.token_hex(16)


def b64(data):
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


for key, role in [("ANON_KEY", "anon"), ("SERVICE_ROLE_KEY", "service_role")]:
    payload = {
        "role": role,
        "iss": "supabase",
        "iat": int(time.time()),
        "exp": int(time.time()) + 31536000,
    }
    token = (
        b64(b'{"alg":"HS256","typ":"JWT"}') + "." + b64(json.dumps(payload).encode())
    )
    values[key] = (
        token
        + "."
        + b64(
            hmac.new(
                values["JWT_SECRET"].encode(), token.encode(), hashlib.sha256
            ).digest()
        )
    )
fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
with os.fdopen(fd, "w") as out:
    out.write("".join(f"{k}={v}\n" for k, v in values.items()))
web_env = root / "apps/web/.env.local"
if not web_env.exists():
    fd = os.open(web_env, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write("GEOAI_API_URL=http://127.0.0.1:" + values["GEOAI_API_PORT"] + "\n")
print("Local configuration created with mode 0600; no secrets printed.")
