"""Same final verifier/fixtures, green then restored pre-fix subject in a temp copy."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile

root = Path(__file__).resolve().parents[3]
evidence = Path(__file__).resolve().parent
sys.path.insert(0, str(root / "tools"))
from test_validator_layout_parity import _build_home
from test_hermetic_env import hermetic_env

target = Path(tempfile.mkdtemp(prefix="saipen-t1439-control-")).resolve()
assert target.parent == Path(tempfile.gettempdir()).resolve()
_build_home(target, flatten=False)
shutil.copytree(root / "tests", target / "tests", dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("__pycache__"))
env = hermetic_env()
for args in (["init", "-q"], ["add", "--all"],
             ["-c", "user.name=SAIPEN fixture", "-c", "user.email=fixture@saipen.local",
              "commit", "-q", "-m", "Disposable control subject"]):
    subprocess.run(["git", *args], cwd=target, env=env, check=True, capture_output=True)

verifier = target / "tools/test_conformance_repair_boundary.py"
digest = hashlib.sha256(verifier.read_bytes()).hexdigest()
command = [sys.executable, "-B", "-m", "unittest", "-v", "tools.test_conformance_repair_boundary"]

def run(name):
    with (evidence / name).open("w", encoding="utf-8") as output:
        return subprocess.run(command, cwd=target, env=env, stdout=output,
                              stderr=subprocess.STDOUT, timeout=180).returncode

green = run("t1439-control-green.log")
# These four implementation files were clean at entry; HEAD is their exact
# pre-fix subject. Leave all other current source and every test unchanged.
for rel in ("tools/saipen_engine/conformance.py", "tools/saipen_engine/router.py",
            "tools/saipen_engine/automation.py", "tools/validate.py"):
    previous = subprocess.run(["git", "show", "HEAD:" + rel], cwd=root, env=env,
                              capture_output=True, check=True).stdout
    (target / rel).write_bytes(previous)

# The CLI had earlier T-1437/T-1438 work. Reverse only this ticket's hunks.
cli_path = target / "tools/saipen.py"
cli = cli_path.read_text(encoding="utf-8")
replacements = [
    ('            command = decision["remediation_command"]\n',
     '            command = decision.get("remediation_command") or CONFORMANCE_REMEDIATION_COMMAND\n'),
    ('            payload["repair_status"] = decision["repair_status"]\n'
     '            payload["diagnostic"] = decision["diagnostic"]\n'
     '            payload["terminal"] = command is None\n', ''),
    ('            "repair_status": _conf_decision["repair_status"],\n'
     '            "diagnostic": _conf_decision["diagnostic"],\n', ''),
    ('        for key in ("conformance_status", "canonical_next_command", "remediation",\n'
     '                    "diagnostic", "repair_status", "terminal"):\n'
     '            if key in routed:\n',
     '        for key in ("conformance_status", "canonical_next_command", "remediation"):\n'
     '            if routed.get(key) is not None:\n'),
    ('        payload = dict(route["emitted"]) if route["emitted"] is not None else _route_payload(\n',
     '        payload = _route_payload(\n'),
    ('        payload["stop_reason"] = "refusal" if route["emitted"] is not None else "boundary"\n'
     '        _emit(payload, as_json)\n'
     '        return route["rc"]\n',
     '        payload["stop_reason"] = "boundary"\n'
     '        _emit(payload, as_json)\n'
     '        return 0\n'),
    ('            "terminal": bool(routed.get("terminal")),\n'
     '            "diagnostic": routed.get("diagnostic"),\n', ''),
]
for current, previous in replacements:
    assert cli.count(current) == 1, current
    cli = cli.replace(current, previous, 1)
cli_path.write_text(cli, encoding="utf-8")
assert hashlib.sha256(verifier.read_bytes()).hexdigest() == digest
red = run("t1439-control-red.log")
record = {"verifier_sha256": digest, "same_verifier_and_command": True,
          "command": command, "target": str(target), "green_exit": green, "red_exit": red,
          "restoration": "four initially clean files from HEAD; only T-1439 CLI hunks reversed"}
(evidence / "control-pair.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
print(json.dumps(record))
raise SystemExit(0 if green == 0 and red != 0 else 1)
