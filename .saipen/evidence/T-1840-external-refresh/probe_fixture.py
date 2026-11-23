"""Real positive/negative admission on one newly owned disposable fixture."""
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root / "tools"))
from saipen_engine.init_project import bootstrap_project
from saipen_engine.process_tree import run

engine = Path(os.environ.get("ProgramData", "C:/ProgramData")) / "SAI/Accounts/bin/sai-accounts.exe"
parent = Path(tempfile.gettempdir()).resolve()
owner = Path(tempfile.mkdtemp(prefix="saipen-t1840-admission-", dir=parent)).resolve()
if owner.parent != parent or not owner.name.startswith("saipen-t1840-admission-"):
    raise RuntimeError("fixture is outside its newly owned temporary root")
project = owner / "project"
project.mkdir()
report = {"scope": "new disposable project; no production project changes", "owner": str(owner), "probes": []}
granted = False


def ask(*arguments):
    result = run([str(engine), *arguments], capture_output=True, text=True, timeout=240)
    value = json.loads(result.stdout)
    return {"argv": list(arguments), "exit_code": result.returncode, "result": value}


def hashes():
    return {name: hashlib.sha256((project / ".saipen" / name).read_bytes()).hexdigest()
            for name in ("STATE.md", "BOARD.md", "LOG.md")}


try:
    bootstrap_project(project, agent="saipen-cli", mode="no-publish")
    granted_result = ask("grant-workdir", "AG3", "--workdir", str(project))
    report["grant"] = granted_result
    if granted_result["exit_code"] != 0:
        raise RuntimeError("private fixture grant was unavailable")
    granted = True
    for label in ("valid-home", "unlisted-home"):
        if label == "unlisted-home":
            # Intentional test-subject corruption, limited to this disposable
            # fixture. Never a mutation of live project memory or lifecycle.
            state = project / ".saipen/STATE.md"
            text = state.read_text(encoding="utf-8")
            foreign = Path(os.environ["USERPROFILE"]) / ".codex"
            text, count = re.subn(r"(?m)^saipen_home:.*$", "saipen_home: " + json.dumps(foreign.as_posix()), text)
            if count != 1:
                raise RuntimeError("fixture home is not uniquely declared")
            state.write_text(text, encoding="utf-8")
        before = hashes()
        probe = ask("saipen-readiness", "AG3", "--workdir", str(project))
        probe.update(label=label, canonical_unchanged=(before == hashes()))
        report["probes"].append(probe)
        print(json.dumps({"label": label, "exit_code": probe["exit_code"],
                          "verdict": probe["result"].get("verdict"),
                          "admission": probe["result"].get("facts", {}).get("project_admission"),
                          "canonical_unchanged": probe["canonical_unchanged"]}), flush=True)
finally:
    if granted:
        revoked = ask("revoke-workdir", "AG3", "--workdir", str(project))
        report["revoke"] = revoked
        if revoked["exit_code"] != 0:
            report["fixture_retained"] = True
    if not report.get("fixture_retained"):
        if owner.parent != parent or not owner.name.startswith("saipen-t1840-admission-"):
            raise RuntimeError("refusing cleanup outside the owned temporary root")
        shutil.rmtree(owner)
        report["removed"] = not owner.exists()
    (root / ".saipen/evidence/T-1840-external-refresh/disposable-admission.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
