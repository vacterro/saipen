"""Execute moved command-reference mutation controls in a generated fixture."""
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools"))
import audit_checks as audit
from test_t1586_scenario_inputs import source_runtime_fixture

names = (
    "the registered command inventory disappears",
    "a future verb stops being published",
    "COMMANDS.md shortcut row leaves the registry behind",
)
rows = []
with tempfile.TemporaryDirectory(prefix="saipen-reference-controls-") as temporary:
    tree = Path(temporary) / "subject"
    source_runtime_fixture(ROOT, tree)

    def validate():
        return subprocess.run(
            [sys.executable, "-B", str(tree / "tools/validate.py"),
             "--project-root", str(tree)], cwd=tree,
            env=audit.hermetic_child_env(), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=180,
        )

    control = validate()
    if control.returncode != 0:
        raise AssertionError("Known-good fixture failed: " + control.stdout[-3500:])
    for label in names:
        matches = [case for case in audit.CASES if case[0] == label]
        assert len(matches) == 1, label
        _, relative, mutate, expected, _, _ = audit.case_parts(matches[0])
        target = tree / relative
        original = target.read_bytes()
        try:
            assert audit.apply_case(tree, relative, mutate) is True, label
            bad = validate()
            assert bad.returncode != 0 and expected in bad.stdout, (label, bad.stdout[-3500:])
            rows.append({"case": label, "path": relative,
                         "known_good_exit": control.returncode, "mutated_exit": bad.returncode,
                         "expected": expected,
                         "original_sha256": hashlib.sha256(original).hexdigest()})
        finally:
            target.write_bytes(original)
        restored = validate()
        assert restored.returncode == 0, (label, restored.stdout[-3500:])
        assert target.read_bytes() == original
        rows[-1]["restored_exit"] = restored.returncode

result = {"scope": "Generated disposable source fixture, not original-history recovery or live host proof",
          "controls": rows}
Path(__file__).with_name("reference-controls.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
print(json.dumps(result, indent=2))
