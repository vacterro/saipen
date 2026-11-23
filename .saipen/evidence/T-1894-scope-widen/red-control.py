"""T-1894 red control: the declaration, not the code, is the whole delta.

Three phases over the real resolver (`saipen_engine.sandbox_scope.resolve`):

  1. PREFIX  -- the manifest as it stood before this ticket (six modules from
     T-1889/T-1891/T-1892/T-1893). `test_subprocess_utf8.py` resolves to FULL,
     so the shard still copies 1815 MiB of history the module never reads.
     This is the red half: the ticket's claim ("copies the source tree only")
     is false against these bytes.
  2. NOW     -- the widened manifest. The same module resolves to DECLARED with
     `trees == []`, which is the source tree only.
  3. LEGIT   -- a module that really reads `.saipen` history is still FULL under
     the widened manifest, so the change cannot narrow a subject that needs the
     trees it declares away.

Phase 3 is the control that makes phase 1 meaningful: if the resolver returned
DECLARED for everything, phase 2 would prove nothing about this ticket.

Run from the project root:  python .saipen/evidence/T-1894-scope-widen/red-control.py
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))

from saipen_engine import sandbox_scope  # noqa: E402

SUBJECT = "test_subprocess_utf8.py"
#: A module whose own source reads `.saipen` history; it must never be narrowed.
LEGIT = "test_closure_provenance.py"


def resolve_under(manifest: dict, patterns: list[str]) -> dict:
    """Run the real resolver with `manifest` installed as the project's own."""
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch)
        (base / "tools").mkdir(parents=True, exist_ok=True)
        (base / ".saipen").mkdir(exist_ok=True)
        (base / "tools" / "sandbox_scope.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        return sandbox_scope.resolve(base, patterns)


def main() -> int:
    control = json.loads(
        (ROOT / ".saipen/evidence/T-1894-scope-widen/control/sandbox_scope.prefix.json")
        .read_text(encoding="utf-8")
    )
    current = json.loads((ROOT / "tools/sandbox_scope.json").read_text(encoding="utf-8"))

    before = resolve_under(control, [SUBJECT])
    after = resolve_under(current, [SUBJECT])
    legit = resolve_under(current, [LEGIT])

    print(f"phase 1 PREFIX {SUBJECT}: mode={before['mode']} trees={before['trees']} "
          f"undeclared={before['undeclared']}")
    print(f"phase 2 NOW    {SUBJECT}: mode={after['mode']} trees={after['trees']} "
          f"undeclared={after['undeclared']}")
    print(f"phase 3 LEGIT  {LEGIT}: mode={legit['mode']} undeclared={legit['undeclared']}")

    red_half = before["mode"] == sandbox_scope.FULL and SUBJECT in before["undeclared"]
    green_half = after["mode"] == sandbox_scope.DECLARED and after["trees"] == []
    control_ok = bool(legit["mode"] == sandbox_scope.FULL and legit["undeclared"])

    print()
    print(f"pre-fix tree  narrowed False  (want False: copies everything)")
    print(f"current tree  narrowed {green_half}   (want True: source tree only)")
    print(f"legit module  stays FULL {control_ok}   (want True: history-reader keeps everything)")
    verdict = green_half and control_ok and red_half
    print(f"CONTROL {'OK' if verdict else 'INVALID'}")
    return 0 if verdict else 1


if __name__ == "__main__":
    raise SystemExit(main())
