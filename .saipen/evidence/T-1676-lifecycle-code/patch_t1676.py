"""T-1676: the lifecycle refusal gets its own registered code.

Usage: patch_t1676.py <tree-root>   (asserts every anchor occurs exactly once)
"""
import json
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])


def patch(rel: str, edits: list[tuple[str, str]]) -> None:
    path = ROOT / rel
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        assert text.count(old) == 1, (rel, text.count(old), old[:80])
        text = text.replace(old, new)
    path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
    print("patched", rel, "crlf" if crlf else "lf")


patch("tools/saipen_engine/lifecycle_authority.py", [(
'''#: The refusal CODE. Deliberately the registered code every consumer already
#: routes to recovery, not a new one: `command_resolution` (REGISTRY.json +
#: COMMANDS.md) stands 10 bytes under its budget and a registry code costs
#: 34, so the class rides the detail until that budget is decided (T-1639).
CODE = "PROTOCOL_STATE_INVALID"
''',
'''#: The refusal CODE: the class itself, registered in REGISTRY.json
#: `error_codes` (T-1676). Until the route budgets replaced the aggregate cap
#: (T-1670) it rode PROTOCOL_STATE_INVALID and named the class only in the
#: detail; a host now routes on the code alone.
CODE = CLASS
'''),
])

patch("saipen/REGISTRY.json", [(
'''  "UNHANDLED_ACTION",
  "UNKNOWN_ACTION",
  "UNSEATED_MUTATION",
''',
'''  "UNAUTHORIZED_LIFECYCLE_WRITE",
  "UNHANDLED_ACTION",
  "UNKNOWN_ACTION",
  "UNSEATED_MUTATION",
'''),
])
json.loads((ROOT / "saipen/REGISTRY.json").read_text(encoding="utf-8-sig"))

patch("tools/saipen_engine/fleet.py", [
(
'''        "PROTOCOL_MODE_READONLY",
        "PROTOCOL_STATE_INVALID",
    }
)
_AUTO_RECOVERY_CODES''',
'''        "PROTOCOL_MODE_READONLY",
        "PROTOCOL_STATE_INVALID",
        # T-1676: recovery reopens what no operation closed, on an approved repair.
        "UNAUTHORIZED_LIFECYCLE_WRITE",
    }
)
_AUTO_RECOVERY_CODES'''),
(
'''    "PROTOCOL_STATE_INVALID": "state",
    "PROTOCOL_MODE_READONLY": "state",
''',
'''    "PROTOCOL_STATE_INVALID": "state",
    "PROTOCOL_MODE_READONLY": "state",
    "UNAUTHORIZED_LIFECYCLE_WRITE": "state",
'''),
])
