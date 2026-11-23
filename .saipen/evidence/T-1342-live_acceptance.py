"""T-1342 Target H: bounded live acceptance against the INSTALLED OpenCode runtime.

Read-only toward every real home: the installed engine is EXECUTED, never
written. Stale/current delegated-root cases run against disposable copies under
a disposable USERPROFILE. Fixture projects are disposable. Prints one JSON
document of observed facts; exit 0 only when every expectation holds.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN")
HOME = Path(os.path.expanduser("~"))
INSTALLED = HOME / ".config" / "opencode" / "skills" / "saipen"
PLUGIN = HOME / ".config" / "opencode" / "plugins" / "saipen-guard.js"
SNAPSHOT = Path(os.environ["LOCALAPPDATA"]) / "saipen" / "scheduled-source"
CLI = INSTALLED / "tools" / "saipen.py"
PY = sys.executable
SCRATCH = Path(tempfile.mkdtemp(prefix="saipen-t1342-live-"))

sys.path.insert(0, str(REPO / "tools"))
from saipen_engine import runtime_surface as RS  # noqa: E402
from test_guard_hostile_matrix import fresh_project, recovery_debt_project  # noqa: E402
from test_hermetic_env import hermetic_env  # noqa: E402

facts: dict = {"scratch": str(SCRATCH)}
failures: list[str] = []


def expect(name: str, ok: bool, detail: object) -> None:
    facts[name] = {"ok": bool(ok), "detail": detail}
    if not ok:
        failures.append(name)


def run(argv: list[str], *, cwd: Path, env: dict | None = None, stdin: str | None = None,
        timeout: int = 180) -> tuple[int, str, str, float]:
    started = time.perf_counter()
    proc = subprocess.run(
        argv, cwd=str(cwd), env=env or hermetic_env(), input=stdin,
        capture_output=True, text=True, timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr, round(time.perf_counter() - started, 2)


def parse(stdout: str) -> dict | None:
    try:
        value = json.loads(stdout)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


# 11 -- source and installed runtime generation identity agree ---------------
source_id = RS.runtime_generation_identity(REPO)
installed_id = RS.runtime_generation_identity(INSTALLED)
snapshot_id = RS.runtime_generation_identity(SNAPSHOT)
expect(
    "11_source_installed_snapshot_identity_agree",
    source_id is not None and source_id == installed_id == snapshot_id,
    {"source": source_id, "installed": installed_id, "snapshot": snapshot_id},
)

# 1 -- installed runtime boots ------------------------------------------------
project = fresh_project(phase="BUILD", task="T-9001", next_action="PHASE BUILD T-9001",
                        agent="live-agent")
(project / ".saipen" / "BOARD.md").write_text(
    "## DOING\n- [/] T-9001 live acceptance | verify: x | owner: live-agent | "
    "claim_time: 2026-09-15T08:00:00Z\n## TODO\n## DONE\n## BLOCKED\n",
    encoding="utf-8",
)
rc, out, err, secs = run([PY, str(CLI), "status", "--json"], cwd=project)
status = parse(out)
expect("1_installed_runtime_boots", rc == 0 and status is not None and status.get("ok") is True,
       {"rc": rc, "seconds": secs, "stderr_tail": err[-300:]})

# 2/3 -- fleet preflight parseable, valid project BOUND_VALID -----------------
rc, out, err, secs = run([PY, str(CLI), "fleet", "preflight", "--cwd", str(project), "--json"],
                         cwd=project)
preflight = parse(out)
expect("2_fleet_preflight_bounded_json", preflight is not None and len(out) < 65536,
       {"rc": rc, "bytes": len(out), "seconds": secs})
expect("3_valid_project_bound_valid",
       preflight is not None and preflight.get("classification") == "BOUND_VALID",
       {"classification": (preflight or {}).get("classification"), "code": (preflight or {}).get("code")})


def guard(event: dict, cwd: Path) -> tuple[int, dict | None]:
    rc_, out_, _err, _secs = run([PY, str(CLI), "guard", "--event-json", "-", "--json"],
                                 cwd=cwd, stdin=json.dumps(event))
    return rc_, parse(out_)


# 5 -- read-only commands remain allowed --------------------------------------
rc, verdict = guard({"event": "before_tool", "host": "opencode", "cwd": str(project),
                     "tool_name": "read", "actor": "live-agent",
                     "tool_input": {"filePath": str(project / ".saipen" / "STATE.md")}}, project)
expect("5_read_only_allowed", rc == 0 and (verdict or {}).get("admitted") is True,
       {"rc": rc, "code": (verdict or {}).get("code")})

# 6 -- forbidden canonical direct mutation remains refused --------------------
rc, verdict = guard({"event": "before_tool", "host": "opencode", "cwd": str(project),
                     "tool_name": "write", "actor": "live-agent",
                     "tool_input": {"filePath": str(project / ".saipen" / "STATE.md"),
                                    "content": "phase: DONE\n"}}, project)
expect("6_canonical_direct_mutation_refused",
       rc != 0 and (verdict or {}).get("admitted") is False,
       {"rc": rc, "code": (verdict or {}).get("code")})

# 7 -- exact canonical recovery remains admitted ------------------------------
debt = recovery_debt_project()
rc, verdict = guard({"event": "before_tool", "host": "opencode", "cwd": str(debt),
                     "tool_name": "bash",
                     "tool_input": {"command": "saipen recover --json"}}, debt)
expect("7_exact_canonical_recovery_admitted",
       rc == 0 and (verdict or {}).get("admitted") is True,
       {"rc": rc, "code": (verdict or {}).get("code")})

# 8/9 -- installed validator: no FINDINGS_CAPTURE_FAILED, no layout error -----
rc, out, err, secs = run([PY, str(INSTALLED / "tools" / "validate.py")], cwd=project, timeout=300)
combined = out + err
expect("8_no_findings_capture_failed", "FINDINGS_CAPTURE_FAILED" not in combined,
       {"rc": rc, "seconds": secs})
expect("9_no_source_vs_flattened_path_error",
       "FileNotFoundError" not in combined and "No such file" not in combined
       and "Traceback" not in combined,
       {"tail": combined.strip().splitlines()[-1:] if combined.strip() else []})

# 10 -- no external package shadows the local engine --------------------------
shadow = SCRATCH / "shadow"
(shadow / "saipen_engine").mkdir(parents=True)
sentinel = SCRATCH / "foreign-executed.txt"
(shadow / "saipen_engine" / "__init__.py").write_text(
    f"from pathlib import Path\nPath(r'{sentinel}').write_text('executed')\n"
    "raise RuntimeError('foreign saipen_engine executed')\n",
    encoding="utf-8",
)
env = hermetic_env(PYTHONPATH=str(shadow))
rc, out, err, secs = run([PY, str(CLI), "status", "--json"], cwd=project, env=env)
expect("10_no_external_package_shadows_engine",
       rc == 0 and not sentinel.exists() and parse(out) is not None,
       {"rc": rc, "sentinel": sentinel.exists()})

# 4 -- stale delegated root is rejected (disposable USERPROFILE copy) ---------


def disposable_home(label: str) -> Path:
    home = SCRATCH / label
    skill = home / ".config" / "opencode" / "skills" / "saipen"
    shutil.copytree(INSTALLED, skill, ignore=shutil.ignore_patterns("__pycache__"))
    plugin = home / ".config" / "opencode" / "plugins" / "saipen-guard.js"
    plugin.parent.mkdir(parents=True)
    shutil.copyfile(PLUGIN, plugin)
    cli = (skill / "tools" / "saipen.py").resolve()
    (skill / "bin" / "saipen").write_text(f'#!/bin/sh\nexec "{PY}" "{cli}" "$@"\n', "utf-8")
    (skill / "bin" / "saipen.cmd").write_text(f'@echo off\r\n"{PY}" "{cli}" %*\r\n', "utf-8")
    return home


def prelaunch_in(home: Path) -> dict | None:
    env_ = hermetic_env(USERPROFILE=str(home), HOME=str(home))
    rc_, out_, err_, _secs = run(
        [PY, str(CLI), "runtime", "--prelaunch", "--adapter", "opencode", "--no-resync", "--json"],
        cwd=SCRATCH, env=env_,
    )
    payload = parse(out_)
    if payload is not None:
        payload["_rc"] = rc_
    return payload


current_home = disposable_home("home-current")
current = prelaunch_in(current_home)
stale_home = disposable_home("home-stale")
engine = stale_home / ".config" / "opencode" / "skills" / "saipen" / "tools" / "saipen_engine" / "admission.py"
engine.write_bytes(engine.read_bytes() + b"\n# stale delegated engine\n")
stale = prelaunch_in(stale_home)
extra_home = disposable_home("home-extra")
(extra_home / ".config" / "opencode" / "skills" / "saipen" / "tools" / "saipen_engine"
 / "leftover.py").write_text("# stray module\n", encoding="utf-8")
extra = prelaunch_in(extra_home)
expect("4a_current_delegated_root_current",
       current is not None and current.get("code") == "RUNTIME_CURRENT",
       {k: (current or {}).get(k) for k in ("code", "fingerprint_match", "engine_diff",
                                             "hook_problems", "launcher_problems",
                                             "provenance_problems")})
expect("4b_stale_delegated_root_rejected",
       stale is not None and stale.get("code") == "RUNTIME_STALE" and not stale.get("ok"),
       {k: (stale or {}).get(k) for k in ("code", "fingerprint_match", "engine_diff")})
expect("4c_extra_installed_module_rejected",
       extra is not None and extra.get("code") == "RUNTIME_STALE",
       {k: (extra or {}).get(k) for k in ("code", "fingerprint_match", "engine_diff")})
expect("4d_real_home_untouched_by_probes",
       RS.runtime_generation_identity(INSTALLED) == installed_id, installed_id)

facts["failures"] = failures
print(json.dumps(facts, indent=2))
raise SystemExit(1 if failures else 0)
