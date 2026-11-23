"""T-1654 on the REAL machine runtime: the projected engine reports and repairs.

Run after `saipen host machine install` refreshed the machine runtime from the
final tree. A disposable project carries the measured legacy block between
bytes that must survive; every command goes through the machine launcher with
`saipen` absent from PATH, exactly as an account without the operator's
install would run it. Nothing outside the disposable project is written.

usage: e2e_machine_launcher.py <repo>
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(REPO / "tools"))

import test_t1614_future_gate as H  # noqa: E402
from saipen_engine import machine_runtime, project_block  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "t1654-legacy-block" / "AGENTS.md.measured"
PREFIX = b"\xef\xbb\xbf# Rules of this project\r\n\r\nKeep the \xe4 byte.\n"
SUFFIX = b"\r\n## After the block\nlast line without a newline \xe4"


def main() -> int:
    # The harness isolation points fixtures at a machine root that does not
    # exist; this probe is about the real one, so it is named explicitly.
    real_root = Path(os.environ.get("ProgramData") or r"C:\ProgramData") / "SAI" / "SAIPEN"
    isolate_host_session()
    launcher = machine_runtime.launcher_path(real_root)
    held: list[tuple[str, bool, str]] = []

    def expect(name: str, ok: bool, detail: object = "") -> None:
        held.append((name, bool(ok), str(detail)[:160]))

    expect("a machine runtime is registered", bool(launcher), launcher)
    if not launcher:
        return report(held)
    status = machine_runtime.status(real_root, canonical=REPO)
    expect("it is this source's generation", status.get("code") == "MACHINE_RUNTIME_READY",
           status.get("code"))

    base, project = H._project()
    try:
        raw = FIXTURE.read_bytes()
        begin, end = b"<!-- SAIPEN:BEGIN -->", b"<!-- SAIPEN:END -->"
        legacy = raw[raw.index(begin): raw.index(end) + len(end)]
        target = project / "AGENTS.md"
        target.write_bytes(PREFIX + legacy + SUFFIX)

        env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("SAIPEN", "PYTHON"))}
        env["PATH"] = str(Path(os.environ.get("SYSTEMROOT", "C:/Windows")) / "System32")

        def ask(*args: str) -> tuple[int, dict]:
            proc = subprocess.run(
                ["cmd", "/c", launcher, *args, "--project-root", str(project), "--json"],
                capture_output=True, env=env, cwd=str(base), timeout=300, check=False,
            )
            try:
                return proc.returncode, json.loads(proc.stdout.decode("utf-8", "replace"))
            except ValueError:
                return proc.returncode, {
                    "code": f"UNPARSED rc={proc.returncode}",
                    "detail": (proc.stderr or proc.stdout).decode("utf-8", "replace")[-300:],
                }

        expect("saipen is not on PATH for these commands", shutil.which("saipen", path=env["PATH"]) is None)

        rc, before = ask("host", "instructions")
        expect("status reports another generation", (rc, before.get("code")) == (1, "PROJECT_BLOCK_STALE"),
               (rc, before.get("code"), before.get("detail")))
        expect("and names the one repair", before.get("action") == project_block.REPAIR_ACTION,
               before.get("action"))

        rc, bound = ask("host", "bootstrap")
        expect("host bootstrap binds and carries the verdict",
               bound.get("code") == "HOST_BOOTSTRAP_BOUND"
               and (bound.get("instructions") or {}).get("code") == "PROJECT_BLOCK_STALE",
               (bound.get("code"), bound.get("instructions")))

        rc, routed = ask("status")
        hint = (routed.get("cold_route") or {}).get("instructions") or {}
        expect("status names the stale block in its cold route",
               hint.get("action") == project_block.REPAIR_ACTION, hint)
        boot = (routed.get("cold_route") or {}).get("boot") or ""
        expect("and names a kernel this account can open",
               bool(boot) and Path(boot).is_file() and Path(boot).name == "BOOT.md", boot)

        rc, fixed = ask("host", "instructions", "repair")
        expect("repair succeeds", (rc, fixed.get("code")) == (0, "PROJECT_BLOCK_REPAIRED"),
               (rc, fixed.get("code"), fixed.get("detail")))
        data = target.read_bytes()
        expect("bytes before the block are identical", data.startswith(PREFIX))
        expect("bytes after the block are identical", data.endswith(SUFFIX))
        middle = data[len(PREFIX): len(data) - len(SUFFIX)]
        expect("the block is the current one", middle == project_block.current_block(b"\n"))
        expect("no clone and no private path remain",
               b"github.com" not in data and b"\\Users\\" not in data)

        rc, after = ask("host", "instructions")
        expect("status reads current", (rc, after.get("code")) == (0, "PROJECT_BLOCK_CURRENT"),
               (rc, after.get("code")))
        rc, routed = ask("status")
        expect("status no longer carries a hint",
               "instructions" not in (routed.get("cold_route") or {"instructions": 1}))
        rc, again = ask("host", "instructions", "repair")
        expect("a second repair writes nothing",
               again.get("code") == "PROJECT_BLOCK_CURRENT" and again.get("written") == []
               and target.read_bytes() == data, (again.get("code"), again.get("written")))
    finally:
        shutil.rmtree(base, True)
    return report(held)


def report(held: list[tuple[str, bool, str]]) -> int:
    for name, ok, detail in held:
        print(("held   " if ok else "BROKEN ") + name + ("" if ok or not detail else f"  <- {detail}"))
    kept = sum(1 for _name, ok, _detail in held if ok)
    print(f"{kept} of {len(held)} expectations held")
    return 0 if kept == len(held) else 1


if __name__ == "__main__":
    sys.exit(main())
