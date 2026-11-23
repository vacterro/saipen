"""Fixed external oracle for the T-1603 scenario-harness subject."""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import sys
import time
import types
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tools"))
from test_hermetic_env import hermetic_env


def main():
    label, subject_path = sys.argv[1:3]
    subject = Path(subject_path).resolve()
    module = types.ModuleType("scenario_subject")
    # Both subjects use the same installed-home context. The preserved copy
    # lives under evidence, where deriving HOME from its physical path is wrong.
    module.__file__ = str(ROOT / "tools/run_scenarios.py")
    sys.modules[module.__name__] = module
    started = time.monotonic()
    output = io.StringIO()
    with patch.dict("os.environ", hermetic_env(), clear=True), contextlib.redirect_stdout(output):
        exec(compile(subject.read_bytes(), str(subject), "exec"), module.__dict__)
        module.HOME = ROOT
        module.VALIDATOR = ROOT / "tools/validate.py"
        module.SCENARIOS = ROOT / "tests/scenarios"
        controls = []
        authority = contextlib.nullcontext()
        if label == "bad-authority":
            from saipen_engine import operator_task
            real = operator_task.authority_for_provenance
            def unsafe(provenance):
                result = real(provenance)
                result.update(goal_pivot=True, user_explicit=True, preempt_active_work=True)
                return result
            authority = patch.object(operator_task, "authority_for_provenance", unsafe)
        if label == "bad-conflict":
            from saipen_engine import journal
            real_inspect = journal.inspect_op
            def old_inspect(*args, **kwargs):
                result = real_inspect(*args, **kwargs)
                result["safe_resolution_classes"] = ["accept_live", "replan"]
                return result
            authority = patch.object(journal, "inspect_op", old_inspect)
        with authority:
            names = ["run_nitro_m3_probes", "run_nitro_integrity_probes"]
            if label == "bad-authority":
                names = names[:1]
            elif label == "bad-conflict":
                names = names[1:]
            for name in names:
                problems, checked, *extra = getattr(module, name)()
                controls.append({"function": name, "checked": checked, "failures": problems,
                                 "extra": extra})
    failures = [problem for control in controls for problem in control["failures"]]
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    record = {"label": label, "verifier_sha256": digest(Path(__file__)),
              "subject": str(subject), "subject_sha256": digest(subject),
              "production_sha256": {path: digest(ROOT / path) for path in (
                  "tools/saipen_engine/operations.py", "tools/saipen_engine/operator_task.py",
                  "tools/saipen_engine/journal.py", "tools/test_fixture_support.py")},
              "checks": sum(control["checked"] for control in controls),
              "failures": len(failures), "controls": controls,
              "seconds": round(time.monotonic() - started, 3)}
    (HERE / f"{label}.txt").write_text(output.getvalue(), encoding="utf-8")
    (HERE / f"{label}.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: record[key] for key in (
        "label", "verifier_sha256", "subject_sha256", "checks", "failures", "seconds")}))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
