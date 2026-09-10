import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
lock = json.loads((root / "infra/supabase/upstream.lock.json").read_text())
for name, digest in lock["sha256"].items():
    assert (
        hashlib.sha256(
            (root / "infra/supabase/upstream" / name).read_bytes()
        ).hexdigest()
        == digest
    ), name
print("PASS: upstream byte integrity (" + str(len(lock["sha256"])) + " files)")
