"""Prepare the queued audit repair without editing the tree under test."""
import hashlib
import inspect
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import audit_checks as audit
from saipen_engine import codec, journal
from saipen_engine.log import parse_log_line
from test_orchestration_repair import OrchestrationFixture

source = ROOT / "tools/audit_checks.py"
original = source.read_text(encoding="utf-8")
updated = original.replace("import datetime\n", "import datetime\nimport errno\n", 1)
updated = updated.replace('''#: The agent name the probe's own journal entry is attributed to.
WARN_PROBE_AGENT = "claude"

''', "", 1)
anchor = "def symlink_restore_probe(tmp: Path) -> str | None:\n"
updated = updated.replace(anchor, '''class ProbeUnavailable(RuntimeError):
    """A required host capability is unavailable; no PASS may be claimed."""


''' + anchor, 1)
updated = updated.replace('''    except (OSError, NotImplementedError) as exc:
        return f"cannot construct symlink red control: {exc}"
''', '''    except NotImplementedError as exc:
        raise ProbeUnavailable(f"symlink control unavailable: {exc}") from exc
    except OSError as exc:
        if getattr(exc, "winerror", None) == 1314 or exc.errno in {
            errno.ENOSYS, errno.EOPNOTSUPP,
        }:
            raise ProbeUnavailable(f"symlink control unavailable: {exc}") from exc
        return f"cannot construct symlink red control: {exc}"
''', 1)
start = updated.index("def journal_probe_allocation(")
end = updated.index("\ndef warn_probe_board(", start)
updated = updated[:start] + '''def journal_probe_allocation(tree: Path, ticket: str) -> str | None:
    """Journal fixture allocation through the canonical writer and provenance."""
    from saipen_engine.operations import checkpoint
    from saipen_engine.state import parse_state

    state = parse_state(codec.read_doc(tree / STATE))
    result = checkpoint(tree, state["agent"], "DEC", ticket,
                        "allocated for the warn-ownership probe fixture")
    return None if result.ok else f"fixture allocation refused: {result.code}: {result.message}"

''' + updated[end:]
updated = updated.replace("from saipen_engine.paths import project_lineage_identity\n",
                          "from saipen_engine import codec\nfrom saipen_engine.paths import project_lineage_identity\n", 1)
allocation = '''    alloc_error = journal_probe_allocation(tree, WARN_PROBE_TICKET)
    if alloc_error:
        return alloc_error

'''
if updated.count(allocation) != 1:
    raise RuntimeError("allocation anchor changed")
updated = updated.replace(allocation, "", 1)
needle = '    board.write_text(neutral_board, encoding="utf-8", newline="\\n")\n'
if updated.count(needle) != 1:
    raise RuntimeError("neutral board anchor changed")
updated = updated.replace(needle, needle + allocation, 1)
warn_start = updated.index("def warn_ownership_probe(")
warn_end = updated.index("\ndef phase_rename_probe(", warn_start)
warn_body = updated[warn_start:warn_end].replace(
    '("config", "user.email", "warn-probe@example.invalid"),',
    '("config", "user.email", "warn-probe@example.invalid"),\n'
    '        ("config", "core.longpaths", "true"),', 1)
updated = updated[:warn_start] + warn_body + updated[warn_end:]
updated = updated.replace('''        try:
            sandbox.mkdir(parents=True, exist_ok=True)
            error = probe.run(context)
        except Exception as exc:  # a probe that explodes is a failed probe
''', '''        unavailable = None
        try:
            sandbox.mkdir(parents=True, exist_ok=True)
            error = probe.run(context)
        except ProbeUnavailable as exc:
            unavailable = str(exc)
            error = None
        except Exception as exc:  # a probe that explodes is a failed probe
''', 1)
updated = updated.replace('''        if error:
            verdicts[probe.name] = "FAIL"
''', '''        if unavailable is not None:
            verdicts[probe.name] = "UNPROVEN"
            out(f"UNPROVEN: {probe.name} -- {unavailable}")
        elif error:
            verdicts[probe.name] = "FAIL"
''', 1)
updated = updated.replace("Returns {probe name: PASS|FAIL|SKIP}.",
                          "Returns {probe name: PASS|FAIL|SKIP|UNPROVEN}.", 1)
updated = updated.replace('''            out(f"SKIP: {probe.name} because prerequisite {blocked} failed")
''', '''            reason = "unproven" if verdicts.get(blocked) == "UNPROVEN" else "failed"
            out(f"SKIP: {probe.name} because prerequisite {blocked} {reason}")
''', 1)
updated = updated.replace('''    if failed or skipped:
        print(
            f"AUDIT: {len(verdicts) - len(failed) - len(skipped)} of {len(verdicts)} "
''', '''    unproven = sorted(name for name, verdict in verdicts.items() if verdict == "UNPROVEN")
    if failed or skipped or unproven:
        print(
            f"AUDIT: {sum(value == 'PASS' for value in verdicts.values())} of {len(verdicts)} "
''', 1)
updated = updated.replace('''            f"skipped: {', '.join(skipped) or 'none'}"
''', '''            f"skipped: {', '.join(skipped) or 'none'}; "
            f"unproven: {', '.join(unproven) or 'none'}"
''', 1)
candidate = ROOT / ".saipen/evidence/T-1561-audit-candidate"
candidate.mkdir(parents=True, exist_ok=True)
(candidate / "audit_checks.py.draft").write_text(updated, encoding="utf-8", newline="")
(candidate / "manifest.json").write_text(json.dumps({
    "path": "tools/audit_checks.py",
    "before_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
}, indent=2) + "\n", encoding="utf-8")

class AuditRepairControls(OrchestrationFixture):
    def test_privilege_gap_is_unproven_and_next_probe_runs(self):
        error = OSError("missing Windows symlink privilege")
        error.winerror = 1314
        probes = (
            audit.Probe("symlink-restore", lambda ctx: audit.symlink_restore_probe(ctx.sandbox), "symlink checked"),
            audit.Probe("after", lambda ctx: None, "next probe ran"),
        )
        with tempfile.TemporaryDirectory() as location, patch.object(audit.os, "symlink", side_effect=error):
            lines = []
            verdicts = audit.run_probes(probes, audit.ProbeContext(Path(location), [], None), out=lines.append)
        self.assertEqual(verdicts, {"symlink-restore": "UNPROVEN", "after": "PASS"})
        self.assertTrue(any(line.startswith("UNPROVEN: symlink-restore") for line in lines))

    def test_unexpected_symlink_io_failure_remains_a_failure(self):
        probes = (audit.Probe("symlink-restore", lambda ctx: audit.symlink_restore_probe(ctx.sandbox), "symlink checked"),)
        with tempfile.TemporaryDirectory() as location, patch.object(audit.os, "symlink", side_effect=OSError("bad path")):
            verdicts = audit.run_probes(probes, audit.ProbeContext(Path(location), [], None), out=lambda line: None)
        self.assertEqual(verdicts, {"symlink-restore": "FAIL"})

    def test_capability_dependent_probe_is_skipped_without_a_false_failure(self):
        error = OSError("missing Windows symlink privilege")
        error.winerror = 1314
        probes = (
            audit.Probe("symlink-restore", lambda ctx: audit.symlink_restore_probe(ctx.sandbox), "symlink checked"),
            audit.Probe("dependent", lambda ctx: self.fail("unproven prerequisite was treated as PASS"),
                        "must not run", requires=("symlink-restore",)),
            audit.Probe("after", lambda ctx: None, "independent probe ran"),
        )
        with tempfile.TemporaryDirectory() as location, patch.object(audit.os, "symlink", side_effect=error):
            lines = []
            verdicts = audit.run_probes(probes, audit.ProbeContext(Path(location), [], None), out=lines.append)
        self.assertEqual(verdicts, {"symlink-restore": "UNPROVEN", "dependent": "SKIP", "after": "PASS"})
        self.assertIn("SKIP: dependent because prerequisite symlink-restore unproven", lines)

    def test_fixture_allocation_has_resolvable_canonical_provenance(self):
        project = self.make_project(active=True)
        board = project / audit.BOARD
        neutral = audit.warn_probe_board(board.read_text(encoding="utf-8"), audit.WARN_PROBE_NEUTRAL_SLUG)
        board.write_text(neutral, encoding="utf-8")
        self.assertIsNone(audit.journal_probe_allocation(project, audit.WARN_PROBE_TICKET))
        tail = (project / audit.LOG).read_text(encoding="utf-8").splitlines()[-1]
        event = parse_log_line(tail)
        self.assertEqual(event["ticket"], audit.WARN_PROBE_TICKET)
        self.assertEqual(journal.op_id_provenance(event["op_id"]), "canonical")
        self.assertIn(event["op_id"], journal.resolvable_op_ids(project),
                      "allocation was fabricated without a canonical operation record")

if "--candidate" in sys.argv:
    exec(compile(updated, str(source), "exec"), audit.__dict__)
if "--live-symlink" in sys.argv:
    probes = (audit.Probe("symlink-restore", lambda ctx: audit.symlink_restore_probe(ctx.sandbox),
                          "symlink restoration control passed"),)
    with tempfile.TemporaryDirectory(prefix="saipen-audit-symlink-") as location:
        verdicts = audit.run_probes(probes, audit.ProbeContext(Path(location), [], None))
    sys.exit(0 if verdicts["symlink-restore"] in {"PASS", "UNPROVEN"} else 1)
if "--live-warn" in sys.argv:
    probes = (
        audit.Probe("pristine-fixture", audit.build_pristine, "copy created"),
        audit.Probe("warn-slug-ownership", lambda ctx: audit.warn_ownership_probe(ctx.pristine, ctx.sandbox),
                    "warn ownership red and green controls passed", requires=("pristine-fixture",)),
    )
    with tempfile.TemporaryDirectory(prefix="saipen-audit-warn-") as location:
        verdicts = audit.run_probes(probes, audit.ProbeContext(Path(location), [], None))
    sys.exit(0 if all(value == "PASS" for value in verdicts.values()) else 1)
output = io.StringIO()
result = unittest.TextTestRunner(stream=output, verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(AuditRepairControls))
print(output.getvalue())
proof = {"oracle_sha256": hashlib.sha256(inspect.getsource(AuditRepairControls).encode("utf-8")).hexdigest(),
         "subject_sha256": hashlib.sha256((updated if "--candidate" in sys.argv else original).encode("utf-8")).hexdigest(),
         "tests": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
         "status": "PASS" if result.wasSuccessful() else "FAIL", "output": output.getvalue()}
(candidate / ("oracle-green.json" if "--candidate" in sys.argv else "oracle-red.json")).write_text(
    json.dumps(proof, indent=2) + "\n", encoding="utf-8")
sys.exit(0 if result.wasSuccessful() else 1)
