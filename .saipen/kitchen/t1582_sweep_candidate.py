"""Same sweep oracle against the current broken caller and candidate."""
from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import audit_checks as A

OUT = ROOT / ".saipen/evidence/T-1582-sweep-candidate"
OUT.mkdir(parents=True, exist_ok=True)
subject = ROOT / "tools/audit_checks.py"
oracle = ROOT / "tools/test_t1582_sweep_skip_reason.py"
before = subject.read_bytes()
text = before.decode("utf-8")
old = '''                    if not applied:
                        # T-1582: a non-empty string is a reason the case could
                        # not be built (a host capability), not a silent skip.
                        local_skipped.append((label, applied if applied is not True else None))'''
new = '''                    if applied is not True:
                        # A reason string denotes an unconstructed control;
                        # truthiness must never admit it as successful setup.
                        local_skipped.append((label, applied if isinstance(applied, str) else None))'''
if old not in text:
    old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
assert text.count(old) == 1
text = text.replace(old, new)
old = '''    broken = len(dead) + len(always) + len(skipped)
    context.extra.extend(sweep_report(context.changed, len(cases), live, len(skipped), broken))
    if broken:
        return f"{broken} of {len(cases)} mutation control(s) no longer prove anything"
    return None'''
new = '''    capability = [(label, reason) for label, reason in skipped if reason]
    broken = len(dead) + len(always) + len(skipped) - len(capability)
    if capability:
        # Continue all other cases, and refuse any real dead/missing control.
        # Host absence is UNPROVEN, never the full-sweep success sentence.
        context.extra.append(
            f"PROVEN: {live} of {len(cases)} mutation controls; "
            f"host capability unproven: {len(capability)}; broken: {broken}"
        )
    else:
        context.extra.extend(sweep_report(context.changed, len(cases), live, len(skipped), broken))
    if broken:
        return f"{broken} of {len(cases)} mutation control(s) no longer prove anything"
    if capability:
        raise ProbeUnproven("; ".join(f"{label}: {reason}" for label, reason in capability))
    return None'''
if old not in text:
    old, new = old.replace("\n", "\r\n"), new.replace("\n", "\r\n")
assert text.count(old) == 1
after = text.replace(old, new).encode("utf-8")

tests = r'''

class ActualSweepCapabilityTests(unittest.TestCase):
    """Exercise the actual worker, restoration and probe verdict routing."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="saipen-sweep-capability-")
        self.addCleanup(temp.cleanup)
        self.tmp = Path(temp.name)
        self.source = self.tmp / "pristine"
        self.source.mkdir()
        (self.source / "IDENTITY.md").write_bytes(b"authority\n")
        (self.source / "plain.txt").write_bytes(b"good\n")
        self.link_case = (
            "portable project identity", "IDENTITY.md", audit_checks.SYMLINK_EXTERNAL,
            "identity symlink refused",
        )
        self.dead_case = (
            "genuine missing anchor", "plain.txt", lambda text: text,
            "missing anchor finding",
        )
        self.red_case = (
            "ordinary red control", "plain.txt", lambda text: text.replace("good", "bad"),
            "ordinary finding",
        )

    def run_sweep(self, cases, *, refusal=True, report_red=True):
        context = audit_checks.ProbeContext(self.tmp, cases, None)
        context.pristine = self.source
        context.control = ""
        lines = []

        def validate(root, gate=None):
            identity = root / "IDENTITY.md"
            if identity.is_file() and identity.read_bytes() == b"synthetic symlink\n":
                return "FAIL: identity symlink refused"
            if report_red and (root / "plain.txt").read_bytes() == b"bad\n":
                return "FAIL: ordinary finding"
            return ""

        exc = OSError(errno.EPERM, "symlink privilege unavailable")
        exc.winerror = 1314

        def construct(external, target):
            Path(target).write_bytes(b"synthetic symlink\n")

        probe = audit_checks.Probe(
            "sweep", audit_checks.mutation_sweep_probe, "all controls constructed and proven"
        )
        with mock.patch.object(audit_checks.os, "symlink", side_effect=exc if refusal else construct), \
             mock.patch.object(audit_checks, "validator_output", side_effect=validate):
            verdict = audit_checks.run_probes((probe,), context, out=lines.append)
        self.assertEqual((self.source / "IDENTITY.md").read_bytes(), b"authority\n")
        self.assertEqual((self.source / "plain.txt").read_bytes(), b"good\n")
        return verdict["sweep"], "\n".join(lines)

    def test_capability_reason_reaches_skip_and_unproven_runner(self):
        verdict, text = self.run_sweep([self.link_case])
        self.assertEqual(verdict, "UNPROVEN", text)
        self.assertIn("SKIP: portable project identity -- this host cannot create a symlink", text)
        self.assertIn("1314", text)
        self.assertNotIn("the validator did not report", text)
        self.assertNotIn(audit_checks.FULL_SWEEP_PHRASE, text)

    def test_other_controls_continue_but_missing_capability_is_never_pass(self):
        verdict, text = self.run_sweep([self.link_case, self.red_case])
        self.assertEqual(verdict, "UNPROVEN", text)
        self.assertIn("PROVEN: 1 of 2", text)
        self.assertIn("broken: 0", text)

    def test_a_real_missing_anchor_still_fails_alongside_host_absence(self):
        verdict, text = self.run_sweep([self.link_case, self.dead_case])
        self.assertEqual(verdict, "FAIL", text)
        self.assertIn("its anchor text is", text)
        self.assertIn("1 of 2 mutation control(s) no longer prove anything", text)
        self.assertIn("cannot create a symlink", text)

    def test_a_constructed_dead_control_is_not_softened_by_host_absence(self):
        verdict, text = self.run_sweep([self.link_case, self.red_case], report_red=False)
        self.assertEqual(verdict, "FAIL", text)
        self.assertIn("FAIL: ordinary red control", text)

    def test_constructed_control_still_requires_the_validator_finding(self):
        verdict, text = self.run_sweep([self.link_case], refusal=False)
        self.assertEqual(verdict, "PASS", text)
        self.assertIn(audit_checks.FULL_SWEEP_PHRASE, text)
        self.assertNotIn("UNPROVEN", text)

    def test_real_missing_anchor_alone_still_uses_generic_skip_and_fail(self):
        verdict, text = self.run_sweep([self.dead_case])
        self.assertEqual(verdict, "FAIL", text)
        self.assertIn("its anchor text is", text)
        self.assertNotIn("cannot create a symlink", text)
'''
original_oracle = oracle.read_bytes()
anchor = b'\nif __name__ == "__main__":'
assert original_oracle.count(anchor) == 1
new_oracle = original_oracle.replace(anchor, tests.encode("utf-8") + anchor)
(OUT / "audit_checks.before.py").write_bytes(before)
(OUT / "audit_checks.py").write_bytes(after)
(OUT / oracle.name).write_bytes(new_oracle)
spec = importlib.util.spec_from_file_location("t1582_fixed_oracle", OUT / oracle.name)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
original_function = A.mutation_sweep_probe
results = {}
for variant in ("before", "candidate"):
    if variant == "candidate":
        import ast
        function = next(n for n in ast.parse(after.decode()).body
                        if isinstance(n, ast.FunctionDef) and n.name == "mutation_sweep_probe")
        exec(compile(ast.Module(body=[function], type_ignores=[]), str(subject), "exec"), A.__dict__)
    else:
        A.mutation_sweep_probe = original_function
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromModule(module)
    )
    (OUT / f"oracle-{variant}.txt").write_text(stream.getvalue(), encoding="utf-8")
    results[variant] = {"ran": result.testsRun, "failures": len(result.failures),
                        "errors": len(result.errors), "skipped": len(result.skipped),
                        "ok": result.wasSuccessful()}
A.mutation_sweep_probe = original_function
manifest = {
    "subject": "tools/audit_checks.py", "oracle": "tools/" + oracle.name,
    "before_sha256": hashlib.sha256(before).hexdigest(),
    "after_sha256": hashlib.sha256(after).hexdigest(),
    "oracle_before_sha256": hashlib.sha256(original_oracle).hexdigest(),
    "oracle_sha256": hashlib.sha256(new_oracle).hexdigest(),
    "runs": results,
}
(OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
print(json.dumps(manifest, indent=2))
sys.exit(0 if not results["before"]["ok"] and results["candidate"]["ok"] else 1)
