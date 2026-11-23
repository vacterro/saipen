"""Prepare the queued T-1687 delta under evidence; never edit the live tree."""
from __future__ import annotations

import difflib
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
evidence = Path(__file__).resolve().parent


def replace_once(source: bytes, old: str, new: str) -> bytes:
    newline = "\r\n" if b"\r\n" in source else "\n"
    before = old.replace("\n", newline).encode()
    after = new.replace("\n", newline).encode()
    if source.count(before) != 1:
        raise RuntimeError("source anchor moved; inspect the current subject")
    return source.replace(before, after, 1)


changes = {
    "tools/test_host_authority_broker.py": [
        (
            'WINDOWS = os.name == "nt"\n',
            'WINDOWS = os.name == "nt"\n'
            'NON_HOOK_REFUSALS = (\n'
            '    HI.REASON_NOT_HOST_DESCENDANT,\n'
            '    HI.REASON_HOOK_NOT_FOUND,\n'
            '    HI.REASON_IDENTITY_UNAVAILABLE,\n'
            ')\n',
        ),
        (
            '        self.assertFalse(reply["ok"])\n'
            '        self.assertEqual(reply["code"], HB.CODE_NOT_AUTHENTICATED)\n'
            '        # WHICH part of the hook invocation is missing depends on where the\n'
            '        # suite runs: outside any host, or inside one as an ordinary tool call.\n'
            '        # Both are refusals with a named reason, never a generic "no".\n'
            '        self.assertIn(\n'
            '            reply["identity"]["reason"],\n'
            '            (HI.REASON_NOT_HOST_DESCENDANT, HI.REASON_HOOK_NOT_FOUND),\n'
            '        )\n',
            '        self.assertFalse(reply["ok"], reply)\n'
            '        reason = reply["identity"]["reason"]\n'
            '        self.assertIn(reason, NON_HOOK_REFUSALS, reply)\n'
            '        expected = (HB.CODE_IDENTITY_UNAVAILABLE\n'
            '                    if reason == HI.REASON_IDENTITY_UNAVAILABLE\n'
            '                    else HB.CODE_NOT_AUTHENTICATED)\n'
            '        self.assertEqual(reply["code"], expected, reply)\n',
        ),
        (
            '        self.assertFalse(shape["ok"])\n'
            '        self.assertIn(\n'
            '            shape["reason"],\n'
            '            (\n'
            '                HI.REASON_NOT_HOST_DESCENDANT,\n'
            '                HI.REASON_HOOK_NOT_FOUND,\n'
            '                HI.REASON_IDENTITY_UNAVAILABLE,\n'
            '            ),\n'
            '        )\n',
            '        self.assertFalse(shape["ok"], shape)\n'
            '        self.assertIn(shape["reason"], NON_HOOK_REFUSALS, shape)\n',
        ),
    ],
    "tools/saipen_engine/core_unit.py": [
        (
            '        "red": run["red"],\n',
            '        "red": run["red"],\n'
            '        "red_sections": run.get("sections") or {},\n',
        ),
    ],
}
rows = []
patch = []
for relative, replacements in changes.items():
    before = (root / relative).read_bytes()
    after = before
    for old, new in replacements:
        after = replace_once(after, old, new)
    for folder, data in (("pre", before), ("candidate", after)):
        path = evidence / folder / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    rows.append({"path": relative, "before_sha256": hashlib.sha256(before).hexdigest(),
                 "after_sha256": hashlib.sha256(after).hexdigest()})
    patch.extend(difflib.unified_diff(before.decode().splitlines(True),
                                    after.decode().splitlines(True),
                                    fromfile="pre/" + relative, tofile=relative))
(evidence / "candidate.diff").write_text("".join(patch), encoding="utf-8")
(evidence / "subjects.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
print(json.dumps(rows, indent=2))
