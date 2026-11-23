"""SRC-026:R005 -- does validate_project still dereference a history it could not read?"""
import sys
import traceback
from pathlib import Path

TOOLS = Path(sys.argv[1]) / "tools"
sys.path.insert(0, str(TOOLS))

from test_hermetic_env import isolate_host_session  # noqa: E402

isolate_host_session()

from test_guard_hostile_matrix import fresh_project  # noqa: E402
from saipen_engine.fast_check import validate_project  # noqa: E402
from saipen_engine import journal  # noqa: E402

cases = {
    "active LOG carries a UTF-8 BOM": lambda root: (root / ".saipen" / "LOG.md").write_bytes(
        b"\xef\xbb\xbf" + (root / ".saipen" / "LOG.md").read_bytes()
    ),
    "logs container is a regular file": lambda root: (root / ".saipen" / "logs").write_bytes(b"x"),
}
for label, damage in cases.items():
    root = fresh_project()
    damage(root)
    try:
        errors = validate_project(root)
        print(f"{label}: returned {len(errors)} error(s): {errors[:2]}")
    except Exception as exc:  # noqa: BLE001 - the probe reports what escaped
        print(f"{label}: RAISED {type(exc).__name__}: {exc}")
        print("    ", traceback.format_exc().strip().splitlines()[-3].strip())
    print("    through the journal's boundary:", journal._run_verifier(root, [], "core_fast")[:1])
