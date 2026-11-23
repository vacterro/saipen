"""Known-bad preservation control against the isolated candidate oracle."""

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
HARNESS = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT
sys.path.insert(0, str(HARNESS / "tools"))
import run_scenarios as scenarios

# Exercise the selected oracle against the declared live installer source.
# The candidate differs only in harness code; compare the installed tree
# against the same source that its bootstrap command actually copies.
scenarios.HOME = ROOT

observations = []
real_run = scenarios.subprocess.run
with scenarios.session_carrier_isolation():
    for platform, executable in (("sh", scenarios.find_bash()),
                                 ("ps1", scenarios.find_powershell())):
        if executable is None:
            observations.append({"platform": platform, "available": False})
            continue
        with tempfile.TemporaryDirectory(prefix="t1726-installer-inspection-") as temporary:
            home = Path(temporary).resolve()
            assert home.parent == Path(tempfile.gettempdir()).resolve()
            destination = home / ".claude/skills/saipen"
            env = scenarios.bash_env(executable, home) if platform == "sh" else dict(os.environ)
            env.update({
                "HOME": str(home), "USERPROFILE": str(home),
                "APPDATA": str(home / "AppData/Roaming"),
                "LOCALAPPDATA": str(home / "AppData/Local"),
                "CLAUDE_CONFIG_DIR": str(home / ".claude"),
                "CODEX_HOME": str(home / ".codex"),
                "XDG_CONFIG_HOME": str(home / ".config"),
                "ZAICODE_HOME": str(home),
                "SAIPEN_USER_CONFIG_HOME": str(home / "user-config"),
                "SAIPEN_UNINSTALL_SKIP_TASK": "1",
            })
            for key in ("APPDATA", "LOCALAPPDATA"):
                Path(env[key]).mkdir(parents=True)
            record = {"platform": platform, "available": True}

            def observe(command, **kwargs):
                uninstall = any(Path(str(arg)).name == f"uninstall.{platform}" for arg in command)
                ledger = {}
                if uninstall:
                    ledger = json.loads((destination / ".saipen_install.json").read_text(
                        encoding="utf-8"))["files"]
                result = real_run(command, **kwargs)
                if any(Path(str(arg)).name == "validate.py" for arg in command):
                    (destination / "operator-data.txt").write_bytes(b"must survive uninstall\n")
                if uninstall:
                    lost = destination / "operator-data.txt"
                    assert lost.resolve().is_relative_to(home)
                    assert lost.is_file() and "operator-data.txt" not in ledger
                    lost.unlink()
                    record["deliberate_fault"] = "deleted an unowned installed file after uninstall"
                    record["uninstall_exit"] = result.returncode
                    record["leftovers"] = [
                        {"path": path.relative_to(destination).as_posix(),
                         "listed_in_ownership_ledger": path.relative_to(destination).as_posix() in ledger,
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                        for path in destination.rglob("*") if path.is_file()
                    ] if destination.exists() else []
                return result

            if platform == "sh":
                install = [executable, str(ROOT / "bootstrap/inject.sh")]
                uninstall = [executable, str(ROOT / "bootstrap/uninstall.sh")]
            else:
                install = [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                           str(ROOT / "bootstrap/inject.ps1")]
                uninstall = [executable, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                             str(ROOT / "bootstrap/uninstall.ps1")]
            with patch.object(scenarios.subprocess, "run", side_effect=observe):
                record["probe_problem"] = scenarios.run_injector_probe(
                    f"bootstrap/inject.{platform}", install, uninstall, env, home)
            observations.append(record)

assert HARNESS != ROOT, "negative control requires the candidate preservation oracle"
assert len(observations) == 2 and all(
    row.get("deliberate_fault") and "changed preserved files" in (row.get("probe_problem") or "")
    for row in observations
), observations
target = Path(__file__).with_name("injector-preservation-negative.json")
target.write_text(json.dumps({"acceptance_gate": False, "observations": observations},
                             indent=2) + "\n", encoding="utf-8")
print(json.dumps({"acceptance_gate": False, "record": str(target), "observations": [
    {"platform": item["platform"], "probe_problem": item.get("probe_problem"),
     "uninstall_exit": item.get("uninstall_exit"),
     "leftovers": len(item.get("leftovers", [])),
     "owned_leftovers": sum(row["listed_in_ownership_ledger"]
                            for row in item.get("leftovers", []))}
    for item in observations]}, indent=2))
