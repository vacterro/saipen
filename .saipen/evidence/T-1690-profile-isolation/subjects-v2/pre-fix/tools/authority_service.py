"""Process entry for the SAIPEN host-authority broker.

This is the artifact the hook starts when no authority answers. It carries no
admission logic of its own: it resolves the SAIPEN home, then hands control to
`saipen_engine.host_authority_broker`, which owns the key, the ledger and every
trust decision.

Ordinary use of a host needs none of this: the prompt boundary starts the
service by itself and the operator surface is `saipen host doctor` and
`saipen host repair`. What is here is the low-level diagnostic surface of the
service process:

    authority_service.py serve            run the broker in this process
    authority_service.py start [--force]  start it detached and wait for health
    authority_service.py stop             ask the running broker to shut down
    authority_service.py status --json    health, generation and policy
    authority_service.py identify --json  what THIS process is to a host application
    authority_service.py install-startup  optional per-user login autostart
    authority_service.py remove-startup   remove that login entry

`start` without `--force` starts the service only for a host application's own
hook invocation, which is what the prompt path does: a process that merely has
a host somewhere above it (a shell-tool command, a test suite an agent runs)
is a caller the service would refuse, so nothing is started on its behalf.
`--force` is the operator's own explicit repair and needs no such reason.
Starting it admits nobody: the service authenticates every client itself.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import host_authority_broker as broker  # noqa: E402
from saipen_engine import host_authority_client as client  # noqa: E402

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
RUN_VALUE = "SaipenAuthority"


def _emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return
    for key, value in payload.items():
        if key in ("ok", "code"):
            continue
        print(f"{key}: {value}")
    print(f"ok: {payload.get('ok')}")


def _startup_command(saipen_root: Path | None, runtime: Path | None) -> str:
    argv = [sys.executable, str(Path(__file__).resolve()), "serve"]
    if saipen_root is not None:
        argv += ["--saipen-root", str(saipen_root)]
    if runtime is not None:
        argv += ["--runtime", str(runtime)]
    return " ".join(f'"{part}"' if " " in part else part for part in argv)


def install_startup(saipen_root: Path | None, runtime: Path | None) -> dict:
    """Register a per-user login entry. The operator stays able to remove it,
    and nothing about this entry grants admission on its own."""
    if os.name != "nt":
        return {
            "ok": False,
            "code": "UNSUPPORTED_PLATFORM",
            "detail": "login autostart is implemented for Windows runs only",
        }
    try:
        import winreg
    except ImportError:
        return {"ok": False, "code": "UNSUPPORTED_PLATFORM", "detail": "winreg unavailable"}
    command = _startup_command(saipen_root, runtime)
    try:
        with winreg.CreateKeyEx(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.SetValueEx(key, RUN_VALUE, 0, winreg.REG_SZ, command)
    except OSError as exc:
        return {"ok": False, "code": "IO_FAILED", "detail": str(exc)}
    return {"ok": True, "code": "AUTHORITY_STARTUP_INSTALLED", "command": command}


def remove_startup() -> dict:
    if os.name != "nt":
        return {
            "ok": False,
            "code": "UNSUPPORTED_PLATFORM",
            "detail": "login autostart is implemented for Windows runs only",
        }
    try:
        import winreg
    except ImportError:
        return {"ok": False, "code": "UNSUPPORTED_PLATFORM", "detail": "winreg unavailable"}
    try:
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE
        ) as key:
            winreg.DeleteValue(key, RUN_VALUE)
    except FileNotFoundError:
        return {"ok": True, "code": "AUTHORITY_STARTUP_ABSENT", "removed": False}
    except OSError as exc:
        return {"ok": False, "code": "IO_FAILED", "detail": str(exc)}
    return {"ok": True, "code": "AUTHORITY_STARTUP_REMOVED", "removed": True}


def status_view(runtime: Path | None) -> dict:
    live = client.status(runtime)
    policy = client.policy()
    if live:
        return {"ok": True, **live, "policy": policy}
    stored = broker.read_status(runtime)
    return {
        "ok": False,
        "code": "BROKER_UNREACHABLE",
        "detail": broker.AUTHORITY_HINT,
        "runtime_root": str(broker.runtime_root(runtime)),
        "endpoint": broker.endpoint_name(runtime),
        "log": str(broker.log_path(runtime)),
        "last_status": stored,
        "identity": client.identify_self(),
        "policy": policy,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "command",
        choices=(
            "serve",
            "start",
            "stop",
            "status",
            "identify",
            "install-startup",
            "remove-startup",
        ),
    )
    parser.add_argument("--saipen-root", type=Path, default=None)
    parser.add_argument("--runtime", type=Path, default=None)
    parser.add_argument("--idle-seconds", type=int, default=None)
    parser.add_argument("--max-requests", type=int, default=None, help="diagnostic bound")
    parser.add_argument("--wait", type=float, default=6.0)
    parser.add_argument("--force", action="store_true", help="start even outside a host")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.command == "serve":
        return broker.run_service(
            saipen_root=args.saipen_root,
            runtime=args.runtime,
            idle_seconds=args.idle_seconds,
            max_requests=args.max_requests,
        )
    if args.command == "start":
        report = client.ensure(
            args.saipen_root if args.saipen_root is not None else ROOT,
            runtime=args.runtime,
            wait=args.wait,
            force=args.force,
        )
        _emit(report, args.json)
        return 0 if report.get("ok") else 1
    if args.command == "stop":
        report = client.shutdown(args.runtime)
        _emit(report, args.json)
        return 0 if report.get("ok") else 1
    if args.command == "status":
        _emit(status_view(args.runtime), args.json)
        return 0
    if args.command == "identify":
        report = client.identify_self()
        report["is_host_client"] = report.pop("ok")
        report["pid"] = os.getpid()
        _emit(report, args.json)
        return 0 if report.get("is_host_client") else 1
    if args.command == "install-startup":
        report = install_startup(args.saipen_root, args.runtime)
        _emit(report, args.json)
        return 0 if report.get("ok") else 1
    report = remove_startup()
    _emit(report, args.json)
    return 0 if report.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
