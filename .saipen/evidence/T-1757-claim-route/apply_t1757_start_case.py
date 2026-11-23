"""T-1757 oracle addition: START's own claim, end to end.

The five cases of tools/test_t1757_claim_follows_route.py call apply_claim
directly, so the entry.py half of the delta (START hands the claim its basis)
was proven by no test: reverting it left the module green. This adds the case
that fails on it, and the negative the route check owed: with the audit route
naming one Work, a claim of another still refuses (dropping the
`projection["work"] == ticket_id` comparison left the module green too).

    python .saipen/evidence/T-1757-claim-route/apply_t1757_start_case.py --check [target]
    python .saipen/evidence/T-1757-claim-route/apply_t1757_start_case.py [target]

The target defaults to the live test module. Line endings are preserved.
"""

from __future__ import annotations

import sys
from pathlib import Path

DEFAULT = Path("tools/test_t1757_claim_follows_route.py")

IMPORT_OLD = "from saipen_engine import audit_inbox  # noqa: E402\n"
IMPORT_NEW = IMPORT_OLD + "from saipen_engine.entry import start_work  # noqa: E402\n"

CASE_OLD = "    def test_a_bare_explicit_override_keeps_its_record(self):\n"
CASE_NEW = (
    "    def test_start_names_the_request_it_was_handed(self):\n"
    "        # The request names the lower Work, so START claims below the Pick\n"
    "        # Rule's top: the DEC states the request, never an override.\n"
    "        started = start_work(self.root, AGENT, actor_source=\"explicit\", text=\"lower probe\")\n"
    "        self.assertEqual(started.get(\"code\"), \"STARTED\", started)\n"
    "        self.assertEqual(started.get(\"ticket\"), \"T-2\", started)\n"
    "        claims = [\n"
    "            ln for ln in self.log_text().splitlines()\n"
    "            if \"[T-2]\" in ln and \"claimed via SAIOPS\" in ln\n"
    "        ]\n"
    "        self.assertEqual(len(claims), 1, claims)\n"
    "        self.assertIn(\n"
    "            f\"user request {started['receipt']}, ahead of PICK-01 topmost workable T-1\",\n"
    "            claims[0],\n"
    "        )\n"
    "        self.assertNotIn(\"EXPLICIT claim over PICK-01\", claims[0])\n"
    "\n"
    "    def test_the_route_admits_only_the_work_it_names(self):\n"
    "        # The audit route continues with T-1, so it lends T-2 nothing.\n"
    "        self.bind_audit_to(\"T-1\")\n"
    "        self.assertEqual(self.routed().get(\"action\"), \"PHASE SCOUT T-1\")\n"
    "        out = plan_claim(self.root, \"T-2\", AGENT)\n"
    "        self.assertFalse(out.get(\"ok\"))\n"
    "        self.assertEqual(out.get(\"code\"), \"NOT_TOP_WORKABLE\")\n"
    "\n"
) + CASE_OLD


def main(argv: list[str]) -> int:
    check = "--check" in argv
    names = [item for item in argv if item != "--check"]
    target = Path(names[0]) if names else DEFAULT
    raw = target.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    if "test_start_names_the_request_it_was_handed" in text:
        print(f"ALREADY_APPLIED {target}")
        return 0
    for old in (IMPORT_OLD, CASE_OLD):
        if text.count(old) != 1:
            print(f"REFUSE anchor not unique in {target}: {old.strip()!r}")
            return 1
    if check:
        print(f"CHECK_OK {target}")
        return 0
    text = text.replace(IMPORT_OLD, IMPORT_NEW).replace(CASE_OLD, CASE_NEW)
    if crlf:
        text = text.replace("\n", "\r\n")
    target.write_bytes(text.encode("utf-8"))
    print(f"APPLIED {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
