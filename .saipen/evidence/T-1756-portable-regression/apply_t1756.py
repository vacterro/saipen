"""Apply the T-1756 change set: exact replacements, counts asserted, endings kept.

Run from the repository root:
    python -B .saipen/evidence/T-1756-portable-regression/apply_t1756.py [--check]
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


ENGINE = "tools/saipen_engine/regression_execution.py"

edit(
    ENGINE,
    "def _load(root, path, *, closed=False):\n",
    "#: A recorded environment digest; anything else is not trusted as one.\n"
    '_ENVIRONMENT_DIGEST = re.compile(r"[0-9a-f]{64}")\n'
    "\n"
    "\n"
    "def _load(root, path, *, closed=False, environment_digest=None):\n",
)
edit(
    ENGINE,
    "    runtime, argv, environment = _runtime(command)\n"
    "    verifier = _sha(\n"
    "        _json(\n"
    "            {\n"
    '                "command": command,\n'
    '                "format": value["format"],\n'
    '                "timeout": value["timeout"],\n'
    '                "runtime": runtime,\n'
    '                "oracle": {key: _sha(context[key]) for key in oracle},\n'
    '                "environment_digest": _sha(_json(environment)),\n'
    "            }\n"
    "        )\n"
    "    )\n",
    "    runtime, argv, environment = _runtime(command)\n"
    "    # T-1756: the environment a pair RAN under belongs to its record. A gate\n"
    "    # judging that record passes it in; hashing the environment of whichever\n"
    "    # process asks made every pair stale in the next host session, whose\n"
    "    # session id, process id and sockets always differ. Oracle, runtime,\n"
    "    # command and timeout are still read here, from the tree and interpreter.\n"
    "    recorded = str(environment_digest or \"\")\n"
    "    environment_sha = (\n"
    "        recorded\n"
    "        if _ENVIRONMENT_DIGEST.fullmatch(recorded)\n"
    "        else _sha(_json(environment))\n"
    "    )\n"
    "    verifier = _sha(\n"
    "        _json(\n"
    "            {\n"
    '                "command": command,\n'
    '                "format": value["format"],\n'
    '                "timeout": value["timeout"],\n'
    '                "runtime": runtime,\n'
    '                "oracle": {key: _sha(context[key]) for key in oracle},\n'
    '                "environment_digest": environment_sha,\n'
    "            }\n"
    "        )\n"
    "    )\n",
)
edit(
    ENGINE,
    '        "verifier": verifier,\n'
    '        "environment": environment,\n'
    "    }\n",
    '        "verifier": verifier,\n'
    '        "environment": environment,\n'
    '        "environment_digest": environment_sha,\n'
    "    }\n",
)
edit(
    ENGINE,
    '        material = _load(Path(root), Path(root) / value["contract_path"])\n',
    "        material = _load(\n"
    "            Path(root),\n"
    '            Path(root) / value["contract_path"],\n'
    '            environment_digest=value.get("environment_digest"),\n'
    "        )\n",
)
edit(
    ENGINE,
    '            "context_digest": _sha(_json(_manifest(material["context"]))),\n'
    '            "before": before,\n',
    '            "context_digest": _sha(_json(_manifest(material["context"]))),\n'
    '            "environment_digest": material["environment_digest"],\n'
    '            "before": before,\n',
)

# The T-1711 control pinned the defect: it asked that a variable set AFTER the
# pair ran unbind the measured pair. The environment still configures the
# verifier: measured under another environment, a pair records another one.
edit(
    "tools/test_t1711_regression_execution.py",
    "    def test_environment_changes_invalidate_the_configured_verifier(self):\n"
    "        self.assertTrue(self.execute().ok)\n"
    '        with patch.dict(os.environ, {"REGRESSION_CONTROL_ENV": "changed"}):\n'
    "            before = self.canonical_digest()\n"
    "            self.assertFalse(self.to_review().ok)\n"
    "            self.assertEqual(self.canonical_digest(), before)\n",
    "    def test_environment_changes_reconfigure_the_verifier_they_measure(self):\n"
    "        # T-1756: the environment a pair ran under is bound to its record, so a\n"
    "        # later session does not unbind it; measured under another environment\n"
    "        # the verifier is another one.\n"
    "        first = self.execute()\n"
    "        self.assertTrue(first.ok)\n"
    '        with patch.dict(os.environ, {"REGRESSION_CONTROL_ENV": "changed"}):\n'
    "            self.assertTrue(self.to_review().ok)\n"
    "            changed = EXECUTION._load(self.project, self.contract_path)\n"
    '        record = json.loads((self.project / first.data["record"]).read_text(encoding="utf-8"))\n'
    '        self.assertNotEqual(changed["verifier"], record["verifier"])\n',
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
    target = ROOT / "tools" / "test_t1756_portable_regression_evidence.py"
    shutil.copyfile(HERE / "draft" / "test_t1756_portable_regression_evidence.py", target)
    print(f"wrote {target.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
