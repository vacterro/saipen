"""Expose the real validator findings in the regression runner's own layout."""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.regression_execution import _load

material = _load(root, Path(__file__).with_name("regression.json"))
with tempfile.TemporaryDirectory(prefix="saipen-pair-diagnosis-") as temp:
    sandbox = Path(temp)
    for relative, body in material["context"].items():
        if body is not None:
            target = sandbox / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(body)
    probe = (
        "import sys,json;sys.path.insert(0,'tools');"
        "import test_t1412_conformance_truth as f;"
        "case=f.T1412Base();case.setUp();"
        "project=case.make_project('probe');"
        "rc,data,_=case.run_cli(project,'validate');"
        "print(json.dumps({'rc':rc,'code':data.get('code'),"
        "'findings':data.get('conformance_status',{}).get('receipt',{}).get('blocking_findings')}));"
        "case.doCleanups()"
    )
    # Match _measure's actual root spool files, without modifying any verifier.
    with (sandbox / ".stdout").open("wb") as stdout, (sandbox / ".stderr").open("wb") as stderr:
        result = subprocess.run(
            [sys.executable, "-B", "-c", probe], cwd=sandbox,
            env=material["environment"], stdout=stdout, stderr=stderr, timeout=120,
        )
    output = (sandbox / ".stdout").read_text(encoding="utf-8")
    error = (sandbox / ".stderr").read_text(encoding="utf-8")
    evidence = {"exit_code": result.returncode, "stdout": output, "stderr": error,
                "layout": "unchanged native regression root spool placement"}
    Path(__file__).with_name("pair-diagnosis.json").write_text(
        json.dumps(evidence, indent=2) + "\n", encoding="utf-8"
    )
    print(output)
    if error:
        print(error)
