"""Keep the same oracle/fixtures while changing only the production subject."""
from pathlib import Path
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
VERIFIER = ROOT / "tools/test_response_surface_contract.py"
CURRENT = ROOT / "tools/saipen_engine/response_surface.py"
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "hotswitch"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(label, command, *, cwd, subject=None):
    env = dict(os.environ)
    env.pop("SAIPEN_DIAGNOSIS_SUBJECT", None)
    if subject is not None:
        env["SAIPEN_DIAGNOSIS_SUBJECT"] = str(subject)
    result = subprocess.run(
        command, cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=600,
    )
    output = result.stdout + result.stderr
    name = PREFIX + "-" + label + ".out.txt"
    (OUT / name).write_text(output, encoding="utf-8")
    totals = re.findall(r"Ran (\d+) tests?", output)
    record = {
        "label": label, "command": command, "cwd": str(cwd),
        "exit_code": result.returncode, "ran": int(totals[-1]) if totals else None,
        "output": name, "output_sha256": digest(OUT / name),
        "verifier_sha256": digest(VERIFIER),
        "subject": str(subject or CURRENT), "subject_sha256": digest(subject or CURRENT),
    }
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return record, output


if sys.argv[1] == "pair":
    pre = OUT / "pre-response_surface.py"
    assert digest(pre) == json.loads((OUT / "pre-source.json").read_text())["sha256"]
    old = ast.parse((OUT / "original-standalone-verifier.py").read_text(encoding="utf-8"))
    new = ast.parse(VERIFIER.read_text(encoding="utf-8"))
    old_class = next(node for node in old.body if isinstance(node, ast.ClassDef)
                     and node.name == "DiagnosisTests")
    new_class = next(node for node in new.body if isinstance(node, ast.ClassDef)
                     and node.name == "DiagnosisTests")
    new_methods = {node.name: ast.dump(node, include_attributes=False)
                   for node in new_class.body if isinstance(node, ast.FunctionDef)}
    assert all(ast.dump(node, include_attributes=False) == new_methods[node.name]
               for node in old_class.body if isinstance(node, ast.FunctionDef))
    records = []
    groups = [
        ("fixed", pre, ["test_a_inventory_cannot_replace_diagnosis",
                        "test_b_generic_handoff_cannot_replace_diagnosis"],
         "FAILED (failures=2)"),
        ("robust", OUT / "pre-layout-response_surface.py",
         ["test_source_and_flattened_installs_use_the_same_owner",
          "test_deep_json_refuses_instead_of_crashing"],
         "FAILED (failures=1, errors=1)"),
    ]
    for group, before, cases, expected in groups:
        command = [sys.executable, "-B", "-m", "unittest"] + [
            "test_response_surface_contract.DiagnosisTests." + case for case in cases
        ] + ["-v"]
        for label, subject in [("pre", before), ("post", None)]:
            record, output = run(group + "-" + label, command, cwd=ROOT / "tools",
                                 subject=subject)
            records.append(record)
            assert record["ran"] == 2
            if label == "pre":
                assert record["exit_code"] == 1 and expected in output
            else:
                assert record["exit_code"] == 0 and "\nOK" in output
    record, output = run("diagnosis", [sys.executable, "-B", "-m", "unittest",
                        "test_response_surface_contract.DiagnosisTests", "-v"],
                        cwd=ROOT / "tools")
    records.append(record)
    assert record["exit_code"] == 0 and record["ran"] == 22
    payload = {"timestamp": datetime.now(timezone.utc).isoformat(), "records": records,
               "original_case_asts_unchanged": True,
               "limits": "API controls; original human/native FreeBuff transcripts are absent; "
                         "synthetic request witnesses are not production authority."}
    (OUT / (PREFIX + "-pair.json")).write_text(json.dumps(payload, indent=2) + "\n",
                                            encoding="utf-8")
elif sys.argv[1] == "cheap":
    commands = [
        ("focused", [sys.executable, "-B", "-m", "unittest",
                     "test_response_surface_contract", "test_refusal_registry",
                     "test_canonical_command_reachability", "test_subprocess_utf8"], ROOT / "tools"),
        ("lint", [sys.executable, "-m", "ruff", "check", "tools/", "tests/"], ROOT),
        ("whitespace", ["git", "-c", "core.safecrlf=false", "diff", "--check"], ROOT),
        ("core", [sys.executable, "-B", "tools/validate.py", "--gate", "core"], ROOT),
    ]
    records = []
    for label, command, cwd in commands:
        record, output = run(label, command, cwd=cwd)
        records.append(record)
        if record["exit_code"]:
            (OUT / (PREFIX + "-cheap.json")).write_text(json.dumps(records, indent=2) + "\n",
                                                     encoding="utf-8")
            raise SystemExit(record["exit_code"])
    (OUT / (PREFIX + "-cheap.json")).write_text(json.dumps(records, indent=2) + "\n",
                                             encoding="utf-8")
else:
    raise SystemExit("expected pair or cheap")
