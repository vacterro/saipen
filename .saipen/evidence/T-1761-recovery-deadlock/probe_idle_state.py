"""T-1761 REVIEW probe: is the residue after the typed-duplicate route this Work's?

    python probe_idle_state.py <tools-dir>

No duplicate, no typed closure: only what the residue names. The T-1671
fixture leaves T-001 canonically claimed under DOING; a hand then idles STATE
(phase DONE, task none) and nothing else. If `recover` answers the same
RESIDUAL_DEFECTS with no command here, the stop belongs to the state-phase
rule and is reached by any hand-idled STATE, with or without a duplicate.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

TOOLS = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(TOOLS))

import continuity_probes as probes  # noqa: E402
import test_t1671_lifecycle_authority as t1671  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def main() -> int:
    isolate_host_session()
    root = t1671._project()
    t1671._state_field(root, "phase", "DONE")
    t1671._state_field(root, "transition_from", "SHIP")
    t1671._state_field(root, "task", "none")
    t1671._state_field(root, "next_action", '"saipen continue"')
    out = {}
    for name, args in (("recover", ("recover",)), ("continue", ("continue",))):
        before = t1671._bytes(root)
        answer = probes.cli(root, t1671.AGENT, *args)
        after = t1671._bytes(root)
        out[name] = {
            "code": answer.get("code"),
            "detail": str(answer.get("detail") or answer.get("message") or "")[:220],
            "canonical_next_command": answer.get("canonical_next_command"),
            "moved": sorted(k for k in before if before[k] != after[k]),
        }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
