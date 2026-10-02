"""One-off diagnostic (not a test): what shell does OpenCode's bash tool run,
and is a `saipen` launcher resolvable there?  Reads only the host's own events.
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

REPO = Path(__file__).resolve().parents[2]
TOOLS = REPO / "tools"
sys.path.insert(0, str(TOOLS))

from saipen_engine.paths import identity_file_content, new_project_lineage  # noqa: E402

OPENCODE = shutil.which("opencode")
BASH = shutil.which("bash")
GIT = shutil.which("git")
AUTH = Path(os.environ.get("USERPROFILE") or Path.home()) / ".local" / "share" / "opencode" / "auth.json"
MODEL = os.environ.get("SAIPEN_LIVE_MODEL", "opencode/ling-3.0-flash-fin-free")

def _msys(path: Path) -> str:
    text = str(path).replace("\\", "/")
    if len(text) > 1 and text[1] == ":":
        text = "/" + text[0].lower() + text[2:]
    if text.lower().startswith("/v/_temp_"):
        text = "/tmp" + text[len("/v/_temp_"):]
    return text


def main() -> int:
    tmp = tempfile.TemporaryDirectory(prefix="saipen-shell-probe-", ignore_cleanup_errors=True)
    base = Path(tmp.name)
    home, cache, workdir = base / "home", base / "cache", base / "workdir"
    for directory in (home, cache, workdir):
        directory.mkdir(parents=True)
    (home / ".config" / "opencode").mkdir(parents=True)
    (home / ".local" / "share" / "opencode").mkdir(parents=True)
    shutil.copy2(AUTH, home / ".local" / "share" / "opencode" / "auth.json")

    bin_ = workdir / "bin"
    bin_.mkdir()
    shim = bin_ / "saipen"
    shim.write_text(
        "#!/bin/sh\nexec " + json.dumps(sys.executable) + " "
        + json.dumps(str(home / ".config" / "opencode" / "skills" / "saipen" / "tools" / "saipen.py"))
        + " \"$@\"\n",
        encoding="utf-8",
        newline="\n",
    )
    shim.chmod(0o755)

    env = {
        **os.environ,
        "HOME": str(home),
        "USERPROFILE": str(home),
        "XDG_CACHE_HOME": str(cache),
        "XDG_DATA_HOME": str(home / ".local" / "share"),
        "PATH": str(bin_) + os.pathsep + (os.environ.get("PATH") or ""),
    }
    for key in ("SAIPEN_PROJECT_ROOT", "SAIPEN_PROJECT_LINEAGE", "SAIPEN_AGENT", "SAIPEN_SKILL_ROOT"):
        env.pop(key, None)
    env.pop("PWD", None)
    env.pop("OLDPWD", None)

    proc = subprocess.run(
        [BASH, str(REPO / "bootstrap" / "inject.sh")], capture_output=True, text=True,
        env=env, timeout=900,
    )
    print("inject rc:", proc.returncode, "|", (proc.stdout + proc.stderr).strip().splitlines()[-1:])

    project = base / "proj"
    (project / ".saipen").mkdir(parents=True)
    (project / "src").mkdir()
    (project / ".saipen" / "IDENTITY.md").write_text(
        identity_file_content(new_project_lineage()), encoding="utf-8"
    )
    (project / ".saipen" / "STATE.md").write_text(
        "---\nphase: DONE\ntask: none\nnext_action: none\nblocker: \"\"\n"
        "transition_from: SHIP\nsaipen_version: 7\nschema_version: 3\nlast_event: 100\n"
        "mode: full\nupdated: 2026-09-13T00:00:00Z\nagent: probe\n---\n", encoding="utf-8"
    )
    (project / ".saipen" / "BOARD.md").write_text(
        "## DOING\n## TODO\n## DONE\n## BLOCKED\n", encoding="utf-8"
    )
    (project / ".saipen" / "LOG.md").write_text(
        "- 13.09.26 00:00 [E-100] [agent: probe] RUN: fixture\n", encoding="utf-8"
    )
    git_env = {
        **env,
        "GIT_AUTHOR_NAME": "fixture", "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
        "GIT_COMMITTER_NAME": "fixture", "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
    }
    subprocess.run([GIT, "init", "-q", str(project)], check=True, capture_output=True, env=git_env)
    subprocess.run([GIT, "-C", str(project), "add", "-A"], check=True, capture_output=True, env=git_env)
    subprocess.run([GIT, "-C", str(project), "commit", "-qm", "fixture"], check=True,
                   capture_output=True, env=git_env)

    bin_msys = _msys(bin_)
    local = subprocess.run(
        [BASH, "-c", f"ls -la {bin_msys}/ ; PATH={bin_msys}:$PATH command -v saipen || echo LOCAL_NOTFOUND"],
        cwd=str(project), env=env, capture_output=True, text=True, timeout=120,
    )
    print("local bash check:\n" + local.stdout.strip())

    prompt = (
        "Shell probe. Step 1: run the bash command command -v saipen and report its exact "
        "output verbatim, or say NOTFOUND if the output is empty. "
        "Step 2: run the bash command uname and report the exact output. "
        f"Step 3: run the bash command ls -la {bin_msys} and report the exact output. "
        "Step 4: run the bash command printenv PATH and report the first 300 characters. "
        "Do not ask the user any question. End with the line PROBE_DONE"
    )

    began = int(time.time() * 1000)
    run = subprocess.run(
        [OPENCODE, "run", prompt, "--format", "json", "--auto", "--model", MODEL],
        cwd=str(project), env=env, capture_output=True, text=True, timeout=900,
    )
    print("opencode rc:", run.returncode, "| elapsed ms:", int(time.time() * 1000) - began)
    for line in run.stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") == "tool_use":
            part = event.get("part") or {}
            state = part.get("state") or {}
            print("  TOOL", part.get("tool"), "|", state.get("status"),
                  "| in:", json.dumps(state.get("input"))[:200],
                  "| out:", json.dumps(state.get("output"))[:300],
                  "| err:", json.dumps(state.get("error"))[:200])
        elif event.get("type") == "text":
            print("  TEXT", json.dumps((event.get("part") or {}).get("text", ""))[:600])
    if run.stderr.strip():
        print("STDERR:", run.stderr[-800:])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
