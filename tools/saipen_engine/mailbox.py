"""First-run SAIMAIL mailbox binding (SRC-136, T-1557).

A new user's ZAICODE session reaches SAIPEN through the launcher; SAIMAIL
is the transport that lets seats exchange sealed letters. The missing leg
was that nothing on the SAIPEN side ever named a mailbox: the turn-entry
read stayed NOT_CONFIGURED until the operator manually exported
``SAIMAIL_WORKSPACE``. This module is that leg, and nothing more:

* ``default_workspace()`` -- the per-user machine mailbox root. One user,
  one mailbox, shared by every project on the machine, so agents in
  different projects are reachable under one identity.
* ``bound_workspace()`` -- the pure resolution the turn-entry read uses:
  an explicit ``SAIMAIL_WORKSPACE`` always wins (an operator's own binding
  is never silently replaced), else the default root when SAIMAIL already
  initialized it, else nothing.
* ``provision()`` -- the one EFFECT: ask ``saimail-local saipen init`` to
  create the mailbox for the acting seat. Idempotent by SAIMAIL's own
  ALREADY_EXISTS answer; never raises, never writes inside any project.

SAIMAIL carries internal letters only; electronic mail is not part of this
binding and never implied by it.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

EXECUTABLE = "saimail-local"
WORKSPACE_ENV = "SAIMAIL_WORKSPACE"
#: The file SAIMAIL's `init` writes at a workspace root; its presence is
#: the cheap stat that says "this root is a real initialized mailbox".
MARKER_NAME = "saimail-workspace.json"
PROVISION_TIMEOUT_S = 60


def default_workspace() -> Path | None:
    """The per-user machine mailbox root, or None where no user home exists.

    Windows: ``%LOCALAPPDATA%/saipen/saimail`` -- the same per-user runtime
    dir the scheduled injector already owns (``autoinject.scheduler_log``),
    so machine-level SAIPEN state stays in one place. Everywhere else the
    XDG state home, defaulting under ``~/.local/state``.
    """
    base = os.environ.get("LOCALAPPDATA")
    if base:
        return Path(base) / "saipen" / "saimail"
    xdg = os.environ.get("XDG_STATE_HOME")
    if xdg:
        return Path(xdg) / "saipen" / "saimail"
    home = Path.home()
    return home / ".local" / "state" / "saipen" / "saimail"


def is_initialized(workspace: Path | str | None) -> bool:
    """True when `workspace` is an already-initialized SAIMAIL mailbox."""
    if workspace is None:
        return False
    return (Path(workspace) / MARKER_NAME).is_file()


def bound_workspace() -> tuple[Path, str] | None:
    """(mailbox root, where the binding came from), or None.

    Resolution order: the explicit ``SAIMAIL_WORKSPACE`` environment value,
    then the per-user default root when SAIMAIL has already initialized it.
    An environment value is taken as-is -- an operator who points somewhere
    that is not yet initialized did so on purpose, and SAIMAIL answers that
    honestly at read time; inventing a "not initialized, ignore it" silent
    fallback here would hide the operator's own mistake.
    """
    explicit = str(os.environ.get(WORKSPACE_ENV) or "").strip()
    if explicit:
        return Path(explicit), "environment"
    default = default_workspace()
    if default is not None and is_initialized(default):
        return default, "default"
    return None


def provision(
    project_root: Path | str,
    seat: str,
    *,
    workspace: Path | str | None = None,
    timeout_s: int = PROVISION_TIMEOUT_S,
) -> dict:
    """Create (or confirm) the acting seat's mailbox via `saimail-local`.

    Runs ``saimail-local saipen init`` against the caller-supplied or
    default workspace root, bound to the enclosing SAIPEN project so the
    mailbox knows this seat's lineage. Returns a schema-stable dict and
    never raises: provisioning is an attachment to first-run, not a
    dependency of it.
    """
    root = default_workspace() if workspace is None else Path(workspace)
    executable = shutil.which(EXECUTABLE)
    if root is None:
        return {
            "ok": False,
            "code": "MAILBOX_NO_HOME",
            "detail": "no per-user home to place the mailbox in",
        }
    if executable is None:
        return {
            "ok": False,
            "code": "MAILBOX_UNAVAILABLE",
            "workspace": str(root),
            "detail": f"{EXECUTABLE} is not on PATH; install SAIMAIL to bind a mailbox",
        }
    command = [
        executable,
        "--json",
        "saipen",
        "init",
        "--workspace",
        str(root),
        "--project-root",
        str(Path(project_root)),
        "--seat",
        str(seat),
    ]
    try:
        proc = subprocess.run(
            command,
            capture_output=True,
            timeout=timeout_s,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "code": "MAILBOX_TIMEOUT",
            "workspace": str(root),
            "detail": f"{EXECUTABLE} did not answer in {timeout_s} s",
        }
    except OSError as exc:
        return {
            "ok": False,
            "code": "MAILBOX_UNAVAILABLE",
            "workspace": str(root),
            "detail": f"{EXECUTABLE} could not run: {exc}"[:300],
        }
    try:
        answer = json.loads(proc.stdout.decode("utf-8", errors="replace"))
    except ValueError:
        answer = None
    status = answer.get("status") if isinstance(answer, dict) else None
    detail = answer.get("detail") if isinstance(answer, dict) else None
    ok = proc.returncode == 0 and isinstance(answer, dict) and answer.get("ok") is True
    if ok and not is_initialized(root):
        # SAIMAIL said yes but the marker the read side keys on is absent:
        # report the disagreement instead of claiming a bound mailbox.
        ok = False
    return {
        "ok": ok,
        "code": "MAILBOX_BOUND" if ok else "MAILBOX_REFUSED",
        "workspace": str(root),
        "status": status,
        "detail": detail or (proc.stderr.decode("utf-8", errors="replace")[:300] or None),
    }
