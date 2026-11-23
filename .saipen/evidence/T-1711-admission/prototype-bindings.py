"""Try two admission corrections in a disposable, hash-checked subject."""
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OUTPUT = HERE / "prototype-bindings.json"
if OUTPUT.exists():
    raise SystemExit("Existing prototype evidence is immutable")
CONTROLS = ROOT / ".saipen/evidence/T-1709-review"
ARCHIVE = CONTROLS / "control-subjects.zip"
MANIFEST = json.loads((CONTROLS / "control-subjects.manifest.json").read_text())
if hashlib.sha256(ARCHIVE.read_bytes()).hexdigest() != MANIFEST["archive_sha256"]:
    raise SystemExit("Control archive identity changed")

TEST = '''import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "tools"))
from test_regression_gate import RegressionGateFixture, V1, S1, S2, _evidence
from saipen_engine.operations import attempt_lifecycle
from saipen_engine.oracle import parse_identity

class IdentityTests(unittest.TestCase):
    def test_conflicting_verifier_has_no_identity(self):
        self.assertEqual(parse_identity("verifier:1111aaaa oracle:9999dddd subject:2222bbbb"), {})
    def test_equal_aliases_keep_one_identity(self):
        self.assertEqual(parse_identity("verifier:1111aaaa oracle:1111aaaa subject:2222bbbb"),
                         {"verifier": "1111aaaa", "subject": "2222bbbb"})

class BindingTests(RegressionGateFixture):
    def attempt(self, action, **kwargs):
        result = attempt_lifecycle(self.project, "tester", action, **kwargs)
        self.assertTrue(result.ok, result.to_dict())
    def pair(self):
        self.record(_evidence("FAIL", V1, S1))
        self.record(_evidence("PASS", V1, S2))
    def refused_without_writes(self):
        before = self.canonical_digest()
        self.assertFalse(self.to_review().ok)
        self.assertEqual(self.canonical_digest(), before)
    def test_conflicting_tokens_cannot_pass_the_real_gate(self):
        self.record(_evidence("FAIL", V1, S1) + " oracle:9999dddd")
        self.record(_evidence("PASS", V1, S2))
        self.refused_without_writes()
    def test_distinct_real_attempts_cannot_supply_the_halves(self):
        self.attempt("open")
        self.record(_evidence("FAIL", V1, S1))
        self.attempt("close", result="failed", stop="validation_failure")
        self.attempt("open")
        self.record(_evidence("PASS", V1, S2))
        self.attempt("close", result="yielded", stop="deliberate_handoff")
        self.refused_without_writes()
    def test_a_new_attempt_spends_the_prior_attempt_pair(self):
        self.attempt("open")
        self.pair()
        self.attempt("close", result="candidate", stop="completed_execution")
        self.attempt("open")
        self.refused_without_writes()
    def test_an_open_attempt_and_absent_attempt_are_distinct(self):
        self.attempt("open")
        self.record(_evidence("FAIL", V1, S1))
        self.attempt("close", result="failed", stop="validation_failure")
        self.record(_evidence("PASS", V1, S2))
        self.refused_without_writes()
    def test_same_attempt_pair_remains_admissible(self):
        self.attempt("open")
        self.pair()
        self.assertTrue(self.to_review().ok)
    def test_legacy_absent_attempt_pair_remains_admissible(self):
        self.pair()
        self.assertTrue(self.to_review().ok)

if __name__ == "__main__": unittest.main()
'''

TEMP_ROOT = Path(tempfile.gettempdir()).resolve()
with tempfile.TemporaryDirectory(prefix="saipen-t1711-bindings-", dir=TEMP_ROOT) as temporary:
    subject = Path(temporary).resolve()
    if not subject.is_relative_to(TEMP_ROOT):
        raise SystemExit("Temporary subject escaped its boundary")
    with zipfile.ZipFile(ARCHIVE) as archive:
        for prefix in ("base/", "subject-green-final/"):
            for name in archive.namelist():
                if not name.startswith(prefix):
                    continue
                target = subject / name.removeprefix(prefix)
                if not target.resolve().is_relative_to(subject):
                    raise SystemExit("Unsafe archive path")
                data = archive.read(name)
                if hashlib.sha256(data).hexdigest() != MANIFEST["files"][name]:
                    raise SystemExit("Archive member identity changed")
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
    for rel in ("tools/saipen_engine/oracle.py", "tools/saipen_engine/log.py",
                "tools/saipen_engine/operations.py", "tools/saipen_engine/attempt.py",
                "tools/test_regression_gate.py"):
        shutil.copy2(ROOT / rel, subject / rel)
    verifier = subject / "prototype_tests.py"
    verifier.write_text(TEST, encoding="utf-8")
    verifier_hash = hashlib.sha256(verifier.read_bytes()).hexdigest()
    runs = []

    def run(label):
        result = subprocess.run([sys.executable, "-B", str(verifier)], cwd=subject,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=180)
        runs.append({"stage": label, "exit_code": result.returncode,
                     "stdout": result.stdout, "stderr": result.stderr,
                     "verifier_sha256": hashlib.sha256(verifier.read_bytes()).hexdigest()})
        if runs[-1]["verifier_sha256"] != verifier_hash:
            raise SystemExit("Prototype oracle moved")

    run("current-control")
    oracle_path = subject / "tools/saipen_engine/oracle.py"
    oracle_before = oracle_path.read_bytes()
    oracle = oracle_path.read_text(encoding="utf-8")
    old = '    for token, value in _TOKEN.findall(text or ""):\n        found.setdefault(_TOKEN_KEY[token], value)\n'
    new = ('    for token, value in _TOKEN.findall(text or ""):\n'
           '        key = _TOKEN_KEY[token]\n'
           '        if key in found and found[key] != value:\n'
           '            return {}\n'
           '        found[key] = value\n')
    if oracle.count(old) != 1:
        raise SystemExit("Oracle prototype boundary changed")
    oracle_path.write_text(oracle.replace(old, new), encoding="utf-8")
    log_path = subject / "tools/saipen_engine/log.py"
    log_before = log_path.read_bytes()
    log = log_path.read_text(encoding="utf-8")
    start = log.index('    records = []\n', log.index('def regression_evidence('))
    end = log.index('\n\ndef structural_marker_events', start)
    replacement = '''    from .attempt import build_attempts
    attempts, errors = build_attempts(events)
    if errors:
        return False, "NOT_A_REGRESSION_PAIR: invalid producing attempt history"
    own = [value for value in attempts.values() if value.get("ticket") == ticket_id]
    latest_open = max((value["open_event"] for value in own), default=0)
    records = []
    for ev in events[boundary:]:
        if ev.get("ticket") != ticket_id or ev.get("taxonomy") != "RUN":
            continue
        if _hand_authored(ev) or ev.get("event", 0) < latest_open:
            continue
        record = parse_evidence(ev.get("text", ""))
        if record is not None:
            producing = [value["id"] for value in own
                         if value["open_event"] <= ev["event"]
                         and (value["close_event"] is None or ev["event"] <= value["close_event"])]
            record["attempt"] = producing[0] if len(producing) == 1 else None
            records.append(record)
    before = next((value for value in reversed(records) if value["result"] == "FAIL"), None)
    after = next((value for value in reversed(records) if value["result"] == "PASS"), None)
    if before is not None and after is not None and before["attempt"] != after["attempt"]:
        return False, "NOT_A_REGRESSION_PAIR: different producing attempts"
    verdict = regression_evidence_verdict(records)
    return bool(verdict.get("admissible")), f"{verdict['code']}: {verdict['reason']}"
'''
    log_path.write_text(log[:start] + replacement + log[end:], encoding="utf-8")
    run("prototype-control")
    oracle_path.write_bytes(oracle_before)
    log_path.write_bytes(log_before)
    run("restored-current-control")

record = {"scope": "two disposable identity/attempt corrections only; genuine-execution operation remains unimplemented",
          "production_changes": 0, "verifier_sha256": verifier_hash, "runs": runs}
OUTPUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"evidence": str(OUTPUT), "runs": [{"stage": entry["stage"],
                   "exit_code": entry["exit_code"]} for entry in runs]}))
for entry in runs:
    print(entry["stage"] + ": " + " | ".join(entry["stderr"].splitlines()[-4:]))
