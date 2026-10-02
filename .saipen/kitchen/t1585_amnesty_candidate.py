import hashlib
import importlib.util
import io
import json
import sys
import types
import unittest
from pathlib import Path

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "tools"))
out = root / ".saipen/evidence/T-1585-amnesty-candidate"
out.mkdir(parents=True, exist_ok=True)
subject = root / "tools/audit_checks.py"
oracle_rel = "tools/test_t1585_amnesty_control.py"
assert not (root / oracle_rel).exists()
before = subject.read_bytes()
text = before.decode("utf-8")

def replace_once(old, new):
    global text
    if old not in text:
        old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
    assert text.count(old) == 1, old[:60]
    text = text.replace(old, new)

replace_once('SWAP = "<swap the last two log entries>"',
             'SWAP = "<swap the last two log entries>"\n'
             'DEMOTE_AMNESTIES = "<demote all anchored timestamp amnesties>"')
replace_once('''def mutation_files(root: Path, rel: str, mutation) -> list[Path]:
    """Every physical file a logical mutation will edit, for save/restore."""''',
'''def mutation_files(root: Path, rel: str, mutation) -> list[Path]:
    """Every physical file a logical mutation will edit, for save/restore."""
    if mutation == DEMOTE_AMNESTIES:
        from saipen_engine.log import history_paths

        return history_paths(root)''')
replace_once('''        "an amnesty demoted to prose stops suppressing",
        ".saipen/logs/LOG-017.md",
        replace(
            "DEC: observed historical timestamp inversions",
            "DEC: a note about observed historical timestamp inversions",
        ),''',
'''        "an amnesty demoted to prose stops suppressing",
        LOG,
        DEMOTE_AMNESTIES,''')
anchor = '\ndef apply_case(root: Path, rel: str, mutation) -> bool | str:'
helper = '''
def demote_amnesty_control(root: Path) -> bool:
    """Change only actual grants in the disposable complete history (T-1585)."""
    from saipen_engine.log import parse_log_line

    marker = "observed historical timestamp inversions"
    changed = False
    for path in mutation_files(root, LOG, DEMOTE_AMNESTIES):
        original = path.read_text(encoding="utf-8-sig")
        lines = []
        for line in original.splitlines(keepends=True):
            event = parse_log_line(line.rstrip("\\r\\n"))
            updated_line = line
            if event and event["taxonomy"] == "DEC" and event["text"].startswith(marker):
                updated_line = line.replace("DEC: " + marker, "DEC: a note about " + marker, 1)
            lines.append(updated_line)
        updated = "".join(lines)
        if updated != original:
            path.write_text(updated, encoding="utf-8", newline="\\n")
            changed = True
    return changed

'''
replace_once(anchor, '\n' + helper + anchor)
replace_once('''    p = case_target(root, rel, mutation)
    if mutation == SYMLINK_EXTERNAL:''',
'''    if mutation == DEMOTE_AMNESTIES:
        return demote_amnesty_control(root)
    p = case_target(root, rel, mutation)
    if mutation == SYMLINK_EXTERNAL:''')
replace_once('''    if isinstance(mutation, tuple) and mutation and mutation[0] == "MULTI":
        return {str(r).replace("\\\\", "/") for r, _ in mutation[1]}
    return {str(rel).replace("\\\\", "/")}''',
'''    if mutation == DEMOTE_AMNESTIES:
        return {LOG, ".saipen/logs/"}
    if isinstance(mutation, tuple) and mutation and mutation[0] == "MULTI":
        return {str(r).replace("\\\\", "/") for r, _ in mutation[1]}
    return {str(rel).replace("\\\\", "/")}''')
replace_once('''        _, rel, mutation, _, _ = case_parts(case)
        if case_declared_paths(rel, mutation) & changed:''',
'''        _, rel, mutation, _, _ = case_parts(case)
        if (mutation == DEMOTE_AMNESTIES and any(
            path == LOG or re.fullmatch(r"\\.saipen/logs/LOG-\\d+\\.md", path)
            for path in changed
        )) or case_declared_paths(rel, mutation) & changed:''')
after = text.encode("utf-8")
tests = r'''"""T-1585: later genuine grants cannot mask an amnesty prose control."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import audit_checks as A  # noqa: E402
from saipen_engine.log import (  # noqa: E402
    history_paths, parse_log_line, structural_marker_events,
)

LABEL = "an amnesty demoted to prose stops suppressing"
MARKER = "observed historical timestamp inversions"


class AmnestyControlTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-amnesty-control-")
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.root = self.tmp / "source"
        (self.root / ".saipen/logs").mkdir(parents=True)
        self.segment = self.root / ".saipen/logs/LOG-017.md"
        self.segment.write_bytes(
            b"- 01.10.26 00:20 [E-1] RUN: before inversion\r\n"
            b"- 01.10.26 00:00 [E-2] RUN: historical inversion\r\n"
            b"- 01.10.26 00:21 [E-3] DEC: observed historical timestamp inversions -- first\r\n"
        )
        self.later_segment = self.root / ".saipen/logs/LOG-018.md"
        self.later_segment.write_bytes(
            b"- 01.10.26 00:22 [E-4] RUN: discussion of observed historical timestamp inversions\n"
            b"- 01.10.26 00:23 [E-5] DEC: observed historical timestamp inversions -- later\n"
        )
        self.active = self.root / ".saipen/LOG.md"
        self.active.write_bytes(
            b"- 01.10.26 00:24 [E-6] DEC: observed historical timestamp inversions -- latest\n"
            b"- 01.10.26 00:25 [E-7] DEC: discussion of observed historical timestamp inversions\n"
        )
        self.case = next(case for case in A.CASES if case[0] == LABEL)

    def grants(self, root):
        events = [parse_log_line(line) for path in history_paths(root)
                  for line in path.read_text(encoding="utf-8").splitlines()]
        return structural_marker_events([event for event in events if event], MARKER, ("DEC",))

    def apply(self):
        _label, rel, mutation, _expected, _gate = A.case_parts(self.case)
        return A.apply_case(self.root, rel, mutation)

    def test_all_actual_grants_are_demoted_across_complete_history(self):
        self.assertEqual(self.grants(self.root), [3, 5, 6])
        self.assertIs(self.apply(), True)
        self.assertEqual(self.grants(self.root), [])
        self.assertIn("RUN: discussion of " + MARKER,
                      self.later_segment.read_text(encoding="utf-8"))
        self.assertIn("DEC: discussion of " + MARKER,
                      self.active.read_text(encoding="utf-8"))

    def test_save_restore_declares_every_touched_file_and_preserves_raw_bytes(self):
        _label, rel, mutation, _expected, _gate = A.case_parts(self.case)
        paths = A.mutation_files(self.root, rel, mutation)
        self.assertEqual(set(paths), set(history_paths(self.root)))
        saved = [(path, path.read_bytes()) for path in paths]
        originals = {path: path.read_bytes() for path in history_paths(self.root)}
        self.assertIs(self.apply(), True)
        A.restore_case_files(saved)
        self.assertEqual({path: path.read_bytes() for path in history_paths(self.root)}, originals)

    def test_actual_sweep_restores_all_sources_after_seeing_the_unsuppressed_condition(self):
        context = A.ProbeContext(self.tmp, [self.case], None)
        context.pristine = self.root
        context.control = ""
        originals = {p: p.read_bytes() for p in history_paths(self.root)}

        def validator(root, gate=None):
            if max(self.grants(root), default=0) < 2:
                return "WARN: timestamp moves backwards by 20m"
            return ""

        with mock.patch.object(A, "validator_output", side_effect=validator):
            error = A.mutation_sweep_probe(context)
        self.assertIsNone(error, "\n".join(context.extra))
        self.assertIn(A.FULL_SWEEP_PHRASE, "\n".join(context.extra))
        self.assertEqual({p: p.read_bytes() for p in history_paths(self.root)}, originals)

    def test_active_log_change_selects_the_control(self):
        self.assertEqual([c[0] for c in A.select_cases([self.case], frozenset({".saipen/LOG.md"}))],
                         [LABEL])

    def test_future_sealed_log_changes_select_the_control_without_disk_guessing(self):
        for path in (".saipen/logs/LOG-018.md", ".saipen/logs/LOG-999.md"):
            self.assertEqual([c[0] for c in A.select_cases([self.case], frozenset({path}))],
                             [LABEL])
        self.assertEqual(A.select_cases([self.case], frozenset({"other/LOG-999.md"})), [])

    def test_no_actual_grant_is_a_no_op_instead_of_fake_evidence(self):
        for path in history_paths(self.root):
            path.write_text("- 01.10.26 00:00 [E-1] RUN: mention " + MARKER + "\n",
                            encoding="utf-8")
        self.assertIs(self.apply(), False)
'''
oracle = tests.encode("utf-8")
(out / "audit_checks.before.py").write_bytes(before)
(out / subject.name).write_bytes(after)
(out / Path(oracle_rel).name).write_bytes(oracle)
spec = importlib.util.spec_from_file_location("t1585_final_oracle", out / Path(oracle_rel).name)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
runs = {}
for variant, code in (("before", before), ("candidate", after)):
    name = "t1585_audit_" + variant
    implementation = types.ModuleType(name)
    implementation.__file__ = str(subject)
    sys.modules[name] = implementation
    exec(compile(code.decode("utf-8"), str(subject), "exec"), implementation.__dict__)
    module.A = implementation
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(module)
    )
    (out / f"oracle-{variant}.txt").write_text(stream.getvalue(), encoding="utf-8")
    runs[variant] = {"ran": result.testsRun, "failures": len(result.failures),
                     "errors": len(result.errors), "ok": result.wasSuccessful()}
manifest = {"subject": "tools/audit_checks.py", "oracle": oracle_rel,
            "before_sha256": hashlib.sha256(before).hexdigest(),
            "after_sha256": hashlib.sha256(after).hexdigest(),
            "oracle_before_sha256": None,
            "oracle_sha256": hashlib.sha256(oracle).hexdigest(), "runs": runs}
(out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2))
sys.exit(0 if not runs["before"]["ok"] and runs["before"]["errors"] == 0
         and runs["candidate"]["ok"] else 1)
