"""T-1647 / SRC-188 acceptance on the REAL machine runtime, asked by a
principal that is not the operator.

Usage: python -B e2e_another_principal.py <saipen home>

What runs the commands: a process started under the operator's own token with
the operator's SID and every group a fresh local account lacks made deny-only
(`tools/test_t1647_machine_runtime.another_principal_token`). The kernel
answers it as an authenticated local user that is not the operator. It is NOT
a second Windows account: the run as `antigravity_b` needs that account's
logon and stays a manual check.

What is real here: the operator's profile, the operator's SAIPEN home, the
operator's private interpreter, and the machine runtime installed under
%ProgramData%\\SAI\\SAIPEN. Only the project is a fixture -- one whose STATE
records the real home, granted to `Users` the way an account manager grants a
workdir.

Exit status 0 only when every expectation holds.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

HOME = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(HOME / "tools"))

import test_t1614_future_gate as H  # noqa: E402
import test_t1647_machine_runtime as T  # noqa: E402
from saipen_engine import machine_runtime, state as ST  # noqa: E402

ROOT = machine_runtime.default_root(os.environ)
LAUNCHER = ROOT / "bin" / "saipen.cmd"
results: list = []


def expect(name: str, holds: bool, seen: object) -> None:
    results.append(bool(holds))
    print(f"{'PASS' if holds else 'FAIL'}  {name}")
    print(f"      {str(seen)[:260]}")


def main() -> int:
    base = Path(tempfile.mkdtemp(prefix="saipen-t1647-e2e-"))
    token = T.another_principal_token()
    try:
        profile = base / "managed-profile"
        (profile / "Temp").mkdir(parents=True)
        T.grant_users_modify(profile)
        fixture_base, project = H._project(intent="goal")
        tid = H._add(project, "the current work of the managed account")
        state = project / ".saipen" / "STATE.md"
        recorded = 'saipen_home: "' + str(HOME).replace("\\", "\\\\") + '"'
        lines = [
            recorded if line.startswith("saipen_home:") else line
            for line in state.read_text(encoding="utf-8").splitlines()
        ]
        state.write_text("\n".join(lines) + "\n", encoding="utf-8")
        T.grant_users_modify(project)
        system_root = os.environ.get("SYSTEMROOT", "C:/Windows")
        env = {
            "SystemRoot": system_root,
            "windir": system_root,
            "SystemDrive": os.environ.get("SYSTEMDRIVE", "C:"),
            "ComSpec": str(Path(system_root) / "System32" / "cmd.exe"),
            "PATH": str(Path(system_root) / "System32"),
            "PATHEXT": ".COM;.EXE;.BAT;.CMD",
            "ProgramData": os.environ.get("PROGRAMDATA", "C:/ProgramData"),
            "USERPROFILE": str(profile),
            "APPDATA": str(profile / "AppData" / "Roaming"),
            "LOCALAPPDATA": str(profile / "AppData" / "Local"),
            "TEMP": str(profile / "Temp"),
            "TMP": str(profile / "Temp"),
        }

        def shell(command: str, cwd: Path = profile) -> tuple:
            code, out, err = T.run_as(token, command, cwd, env, base / "captured")
            return code, out.decode("utf-8", "replace"), err.decode("cp866", "replace").strip()

        def saipen(*args: str) -> dict:
            code, out, err = shell(f'"{LAUNCHER}" {" ".join(args)} --json', cwd=project)
            try:
                return json.loads(out)
            except ValueError:
                return {"code": f"UNPARSED rc={code}", "detail": (err or out)[-400:]}

        print(f"machine runtime : {ROOT}")
        print(f"recorded home   : {HOME}")
        print(f"fixture project : {project}  (ticket {tid})")
        code, out, _err = shell("whoami /groups /fo csv /nh")
        held = [row.split('","')[0].strip('"') for row in out.splitlines() if "Enabled group" in row]
        denied = [row.split('","')[0].strip('"') for row in out.splitlines() if "deny only" in row]
        print(f"principal holds : {', '.join(held)}")
        print(f"deny-only       : operator SID, {', '.join(denied)}")
        print()

        operator = Path(os.environ["USERPROFILE"])
        for label, command in (
            ("operator profile file is closed", f'type "{operator}\\.claude\\CLAUDE.md"'),
            ("operator SAIPEN home is closed", f'type "{HOME}\\saipen\\BOOT.md"'),
            ("operator interpreter is closed", f'"{sys.executable}" --version'),
            ("saipen is not on PATH", "where saipen"),
        ):
            code, out, err = shell(command)
            expect(label, code != 0 and not out.strip(), f"rc={code} {err}")

        answer = saipen("host", "machine", "status")
        expect(
            "it proves the machine runtime itself",
            answer.get("code") == "MACHINE_RUNTIME_READY" and answer.get("saipen_runtime_ready"),
            {k: answer.get(k) for k in ("code", "saipen_runtime_ready", "root")},
        )
        answer = saipen("host", "bootstrap")
        binding = answer.get("binding") or {}
        expect(
            "the binding is the machine runtime, the pointer is kept",
            answer.get("code") == "HOST_BOOTSTRAP_BOUND"
            and answer.get("runtime_source") == "MACHINE_RUNTIME"
            and binding.get("persisted_home_inaccessible") is True
            and binding.get("legacy_saipen_home") == "INACCESSIBLE_BUT_REPLACED"
            and str(answer.get("python") or "").lower().startswith(str(ROOT).lower()),
            {
                "code": answer.get("code"),
                "runtime_source": answer.get("runtime_source"),
                "legacy_saipen_home": binding.get("legacy_saipen_home"),
                "python": answer.get("python"),
            },
        )
        answer = saipen("continue")
        expect(
            "continue resumes the exact current work",
            answer.get("ok") is True
            and answer.get("action") == f"PHASE SCOUT {tid}"
            and str(answer.get("load_path") or "").lower().startswith(str(ROOT).lower()),
            {k: answer.get(k) for k in ("ok", "action", "load_path")},
        )
        answer = saipen("checkpoint", "DEC", "note-from-another-principal")
        log = (project / ".saipen" / "LOG.md").read_text(encoding="utf-8")
        expect(
            "a checkpoint lands in the granted project",
            answer.get("code") == "CHECKPOINTED" and "note-from-another-principal" in log,
            {k: answer.get(k) for k in ("ok", "code", "event_id")},
        )
        answer = saipen("rebind-home", "--auto")
        fields, _error = ST.parse_frontmatter(state.read_text(encoding="utf-8"))
        expect(
            "the recorded home is never rebound",
            answer.get("code") == "HOME_ALREADY_BOUND"
            and str((fields or {}).get("saipen_home")) == str(HOME),
            {"code": answer.get("code"), "saipen_home": (fields or {}).get("saipen_home")},
        )
        planted = ROOT / "bin" / "planted.cmd"
        code, _out, err = shell(f'echo planted> "{planted}"')
        expect(
            "the runtime it runs is closed to its writes",
            code != 0 and not planted.exists(),
            f"rc={code} {err}",
        )
        code, out, err = shell(f'type "{operator}\\.claude\\CLAUDE.md"')
        expect(
            "after all of it the operator profile is still closed",
            code != 0 and not out.strip(),
            f"rc={code} {err}",
        )
        status = machine_runtime.status(canonical=HOME)
        acl = status.get("acl") or {}
        expect(
            "the machine runtime is unchanged: no other writer, no other owner",
            status.get("code") == machine_runtime.CODE_READY
            and acl.get("writable_by") == []
            and acl.get("foreign_owners") == []
            and machine_runtime.projects(status.get("registration"), HOME),
            {"code": status.get("code"), "acl": acl},
        )
        shutil.rmtree(fixture_base, True)
    finally:
        T._win()[1].CloseHandle(token)
        T.reset_access(base)
        shutil.rmtree(base, True)
    print()
    print(f"expectations: {len(results)}, held: {sum(results)}")
    print("VERDICT: " + ("PASS" if results and all(results) else "NOT PASS"))
    return 0 if results and all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
