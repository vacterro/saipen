"""Observe installed response transports without granting host trust/admission.

OpenCode runs the installed plugin AND installed delegated engine in native
Node module loading. Codex/Claude events are synthetic standalone invocations,
never evidence that a live host trusted or loaded a hook.
"""

from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
DEST = Path(__file__).parent / "installed-dogfood"
sys.path.insert(0, str(ROOT / "tools"))

from autoinject import _expand_home, _hook_state, load_adapter_registry
from install_host_guard import install
from test_guard_hostile_matrix import active_project, fresh_project
from test_codex_stop_hook import wait_project
from test_hermetic_env import isolate_host_session
from test_opencode_adapter import PYTHON, run_cases


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    isolate_host_session()
    DEST.mkdir(parents=True, exist_ok=True)
    adapters = {a["id"]: a for a in load_adapter_registry()["adapters"]}
    results = {"kind": "installed-transport-synthetic-controls", "hosts": {}}
    opencode = adapters["opencode"]
    plugin = _expand_home(opencode["install"]["hook"])
    skill = _expand_home(opencode["install"]["skill"])
    native = _hook_state(opencode)
    assert native["status"] == "current", native
    waiting = wait_project()
    active = active_project()
    ordinary = fresh_project()
    cases = []
    for number, pressure in enumerate((30, 30, 300), 1):
        cases.append({
            "id": f"installed-fresh-{number}",
            "project": str(waiting),
            "session_id": f"installed-digest-fresh-{number}",
            "user_request": "saipen status",
            "operational_command": "saipen status",
            "text_complete": "Peatusin. Täiesti lõpetatud on T-1598.\n" * pressure,
        })
    cases.extend([
        {
            "id": "installed-silent-continue",
            "project": str(active),
            "session_id": "installed-silent-continue",
            "user_request": "continue",
            "operational_command": "saipen continue",
            "text_complete": "Töö jätkub.\n" * 80,
        },
        {
            "id": "installed-explicit-artifact",
            "project": str(ordinary),
            "session_id": "installed-explicit-artifact",
            "user_request": "write a specification",
            "text_complete": "```text\n" + "Explicit specification.\n" * 80 + "```",
        },
        {
            "id": "installed-artifact-at-control-boundary",
            "project": str(waiting),
            "session_id": "installed-artifact-at-control-boundary",
            "user_request": "write a specification",
            "text_complete": "```text\n" + "Explicit specification.\n" * 80 + "```",
        },
    ])
    env = {
        "SAIPEN_SKILL_ROOT": str(skill),
        "SAIPEN_PYTHON": PYTHON,
        "SAIPEN_AGENT": "test-agent",
    }
    for case in cases:
        case["env"] = env
    records = run_cases(plugin, cases, DEST / "opencode")
    (DEST / "opencode/results.json").write_text(
        json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    for record in records[:3]:
        assert record["outcome"] == "allowed", record
        assert len(record["delivered"].splitlines()) <= 8, record
        assert len(record["delivered"]) <= 1200, record
        assert "Peatusin." not in record["delivered"], record
    silent = records[3]
    assert (
        silent["outcome"] == "allowed" and silent.get("delivered") == ""
    ) or (
        silent["outcome"] == "blocked"
        and "eligible autonomous action remains; continue silently" in silent.get("message", "")
        and "delivered" not in silent
    ), silent
    assert records[4]["outcome"] == "allowed" and "Explicit specification." in records[4]["delivered"], records[4]
    assert records[5]["outcome"] == "blocked" and "INVALID_OPERATIONAL_PROSE" in records[5].get("message", ""), records[5]
    results["hosts"]["opencode"] = {
        "installation": native,
        "plugin_sha256": sha(plugin),
        "source_plugin_sha256": sha(ROOT / opencode["hook_artifact"]),
        "delegated_engine": str(skill / "tools/saipen.py"),
        "cases": records,
        "live_process_reload": "NOT_PROVEN",
    }
    for name in ("codex", "claude"):
        observed = install(name, Path.home(), ROOT, check=True)
        assert observed["current"] and observed["configured"], observed
        artifact = Path(observed["artifact"])
        events = []
        for number, pressure in enumerate((30, 30, 300), 1):
            payload = {
                "hook_event_name": "Stop",
                "session_id": f"installed-{name}-{number}",
                "cwd": str(waiting),
                "last_assistant_message": "Peatusin. Täiesti lõpetatud on T-1598.\n" * pressure,
                "stop_hook_active": False,
            }
            child_env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
            run = subprocess.run(
                [sys.executable, "-B", str(artifact), "--host", name, "--saipen-root", str(ROOT)],
                input=json.dumps(payload).encode("utf-8"),
                capture_output=True,
                timeout=90,
                env=child_env,
            )
            stdout = run.stdout.decode("utf-8", errors="replace")
            stderr = run.stderr.decode("utf-8", errors="replace")
            event = {"turn": number, "returncode": run.returncode, "stdout": stdout, "stderr": stderr}
            (DEST / f"{name}-turn-{number}.json").write_text(
                json.dumps(event, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
            )
            assert stdout.strip(), event
            verdict = json.loads(stdout)
            assert verdict.get("decision") == "block", event
            events.append(event)
        results["hosts"][name] = {
            "installation": observed,
            "artifact_sha256": sha(artifact),
            "source_artifact_sha256": sha(ROOT / adapters[name]["hook_artifact"]),
            "synthetic_stop_events": events,
            "live_host_execution": "NOT_PROVEN",
            "trust_or_admission_granted": False,
        }
    (DEST / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "hosts": list(results["hosts"]), "record": str(DEST / "results.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
