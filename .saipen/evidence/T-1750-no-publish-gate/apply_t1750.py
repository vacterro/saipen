"""Apply the T-1750 change set: exact replacements, counts asserted, endings kept.

Run from the repository root:
    python -B .saipen/evidence/T-1750-no-publish-gate/apply_t1750.py [--check]
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path.cwd()
HERE = Path(__file__).resolve().parent
EDITS: list[tuple[str, str, str]] = []


def edit(path: str, old: str, new: str) -> None:
    EDITS.append((path, old, new))


RELEASE = "tools/saipen_engine/release.py"

edit(
    RELEASE,
    '    """Local validation + canonical closure for no-publish (zero git)."""\n'
    '    gate = _run_gate(root, "core")\n'
    '    if not gate["ok"]:\n'
    "        raise ReleaseRefusal(\n"
    '            "VALIDATION_FAILED", f"no-publish local validation failed: {gate[\'detail\']}"\n'
    "        )\n",
    '    """Local validation + canonical closure for no-publish (zero git)."""\n'
    '    gate = _run_gate(root, "core")\n'
    '    if not gate["ok"]:\n'
    "        # T-1750: nothing has landed -- the gate runs before the first closure\n"
    "        # target is appended -- so the refusal settles its own operation the\n"
    "        # way recovery settles a PREPARED op with zero targets. Left PREPARED,\n"
    "        # it made the next release answer RECOVERY_REQUIRED until `recover`\n"
    "        # aborted what nothing had started. A refusal after a target landed\n"
    "        # still leaves the op to recovery.\n"
    '        _try_journal(journal, "mark", "ABORTED")\n'
    "        raise ReleaseRefusal(\n"
    '            "VALIDATION_FAILED", f"no-publish local validation failed: {gate[\'detail\']}"\n'
    "        )\n",
)
edit(
    RELEASE,
    "    the validator is the one beside this engine, bound to the project by\n"
    "    `--project-root` -- the same authority `conformance` resolves.\n"
    '    """\n'
    '    local = root / "tools" / "validate.py"\n'
    "    if local.is_file():\n"
    '        return [sys.executable, str(local), "--gate", gate]\n'
    '    canonical = Path(__file__).resolve().parent.parent / "validate.py"\n'
    '    return [sys.executable, str(canonical), "--project-root", str(root), "--gate", gate]\n',
    "    the validator is the one beside this engine, bound to the project by\n"
    "    `--project-root` -- the same authority `conformance` resolves.\n"
    "\n"
    "    T-1750: a project file named `tools/validate.py` is that project's own\n"
    "    business. It is this release's gate only when it IS the validator beside\n"
    "    this engine; a managed project owning an unrelated script of that name\n"
    "    would otherwise have run it as its release gate.\n"
    '    """\n'
    '    canonical = Path(__file__).resolve().parent.parent / "validate.py"\n'
    '    local = root / "tools" / "validate.py"\n'
    "    try:\n"
    "        own = local.is_file() and os.path.samefile(local, canonical)\n"
    "    except OSError:\n"
    "        own = False\n"
    "    if own:\n"
    '        return [sys.executable, str(local), "--gate", gate]\n'
    '    return [sys.executable, str(canonical), "--project-root", str(root), "--gate", gate]\n',
)

# T-1746 controls that pinned the two defects.
T1746 = "tools/test_t1746_crew_terminal_outcome.py"
edit(
    T1746,
    "        self.assertFalse(refused[\"ok\"], refused)\n"
    "        self.assertEqual(refused[\"stage\"], \"NO_PUBLISH\", refused)\n"
    "        self.assertEqual(self._refusal().code, \"RECOVERY_REQUIRED\")\n"
    "        aborted = release.recover_release_op(self.root, plan.op_id)\n"
    "        self.assertEqual((aborted[\"ok\"], aborted[\"code\"]), (True, \"ABORTED\"), aborted)\n"
    "        closed, _result = self._close()\n",
    "        self.assertFalse(refused[\"ok\"], refused)\n"
    "        self.assertEqual(refused[\"stage\"], \"NO_PUBLISH\", refused)\n"
    "        # T-1750: the refusal settled its own operation; the next plan needs no recover.\n"
    "        self.assertTrue(self._plan().op_id)\n"
    "        closed, _result = self._close()\n",
)
edit(
    T1746,
    "    def test_a_source_tree_keeps_validating_itself(self):\n"
    "        self._shape()\n"
    '        (self.root / "tools").mkdir(exist_ok=True)\n'
    '        local = self.root / "tools" / "validate.py"\n'
    '        local.write_text("raise SystemExit(0)\\n", encoding="utf-8")\n'
    '        command = release._gate_command(self.root, "ship")\n'
    '        self.assertEqual(command[1:], [str(local), "--gate", "ship"])\n'
    '        self.assertEqual(release._run_gate(self.root, "ship"), {"ok": True})\n',
    "    def test_a_project_script_named_validate_is_not_the_release_gate(self):\n"
    "        # T-1750: the project's own tools/validate.py is its own business.\n"
    "        self._shape()\n"
    '        (self.root / "tools").mkdir(exist_ok=True)\n'
    '        local = self.root / "tools" / "validate.py"\n'
    '        local.write_text("raise SystemExit(0)\\n", encoding="utf-8")\n'
    '        command = release._gate_command(self.root, "ship")\n'
    '        validator = fixtures.ROOT / "tools" / "validate.py"\n'
    "        self.assertEqual(\n"
    '            command[1:], [str(validator), "--project-root", str(self.root), "--gate", "ship"]\n'
    "        )\n"
    "\n"
    "    def test_a_source_tree_keeps_validating_itself(self):\n"
    '        command = release._gate_command(fixtures.ROOT, "ship")\n'
    '        validator = fixtures.ROOT / "tools" / "validate.py"\n'
    '        self.assertEqual(command[1:], [str(validator), "--gate", "ship"])\n',
)


def main() -> int:
    planned: dict[str, bytes] = {}
    for rel, old, new in EDITS:
        data = planned.get(rel) or (ROOT / rel).read_bytes()
        crlf = b"\r\n" in data
        old_b, new_b = old.encode("utf-8"), new.encode("utf-8")
        if crlf:
            old_b, new_b = old_b.replace(b"\n", b"\r\n"), new_b.replace(b"\n", b"\r\n")
        count = data.count(old_b)
        if count != 1:
            print(f"ABORT: {rel}: expected exactly one match, found {count}:\n{old[:200]}")
            return 1
        planned[rel] = data.replace(old_b, new_b, 1)
    if "--check" in sys.argv:
        print(f"CHECK OK: {len(EDITS)} edits in {len(planned)} files match exactly once")
        return 0
    for rel, data in planned.items():
        (ROOT / rel).write_bytes(data)
        print(f"patched {rel}")
    target = ROOT / "tools" / "test_t1750_no_publish_gate.py"
    shutil.copyfile(HERE / "draft" / "test_t1750_no_publish_gate.py", target)
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
