"""Shared authority for fixtures that model the current installed STYLE."""

from __future__ import annotations

import re
import os
from pathlib import Path
from unittest.mock import patch

from saipen_engine.state import running_style_token, style_contract_token

#: The placeholder a scenario STATE fixture carries where a real install
#: carries its live marker (T-1555). A fixture that hardcoded the marker went
#: stale the moment STYLE.md was edited -- a global chokepoint of 13 red
#: fixtures -- so fixture bytes never claim a specific install; every
#: materialization site resolves THIS to the live marker instead.
LIVE_PLACEHOLDER = "ded-0facade0"

_ANY_MARKER_RE = re.compile(r"style_contract: ded-[0-9a-f]{8}")


def resolve_live_style(text: str, install_root: str | Path | None = None) -> str:
    """Restamp every `style_contract:` marker line in STATE text to live.

    Replaces ANY hex marker (the placeholder, or a token retired by a later
    STYLE.md edit) with the current installation's marker. Deliberately-wrong
    hostile fixtures are simply never routed through here -- their wrongness
    is their assertion.
    """
    live = current_style_contract(install_root)
    return _ANY_MARKER_RE.sub(f"style_contract: {live}", text)


def read_scenario_state(name: str, *rel: str) -> str:
    """One scenario fixture STATE.md, resolved to the live marker.

    The one way test code should materialize a fixture's STATE text: raw
    `read_text` froze whatever marker the fixture shipped with and red the
    suite the moment STYLE.md moved.
    """
    root = Path(__file__).resolve().parent.parent
    path = root / "tests" / "scenarios" / name / ".saipen"
    path = path.joinpath(*rel) if rel else path / "STATE.md"
    return resolve_live_style(path.read_text(encoding="utf-8-sig"))


def restamp_live_style(root: Path, install_root: str | Path | None = None) -> int:
    """Restamp every STATE.md under `root`; returns how many files changed."""
    changed = 0
    for state in Path(root).rglob("STATE.md"):
        text = state.read_text(encoding="utf-8-sig")
        resolved = resolve_live_style(text, install_root)
        if resolved != text:
            state.write_text(resolved, encoding="utf-8", newline="")
            changed += 1
    return changed


def current_style_contract(install_root: str | Path | None = None) -> str:
    """Return the STYLE marker owned by the current or explicit installation."""
    if install_root is None:
        token = running_style_token()
        if token is None:
            raise RuntimeError("running installation has no readable STYLE.md")
        return token

    root = Path(install_root)
    if root.name == "STYLE.md":
        style_path = root
    else:
        candidates = (root / "saipen" / "STYLE.md", root / "STYLE.md")
        style_path = next((path for path in candidates if path.is_file()), None)
        if style_path is None:
            raise FileNotFoundError(f"STYLE.md not found beneath {root}")
    return style_contract_token(style_path.read_text(encoding="utf-8-sig"))


CURRENT_STYLE_CONTRACT = current_style_contract()


def operator_request_env(text: str) -> dict[str, str]:
    """An external fixture launcher witnesses these exact human-request bytes.

    Use only for a test's explicit operator ingress. Model-supplied and
    transport-obligation controls must keep their carrier-free environment.
    """
    from saipen_engine.operator_task import ENV_TASK_SHA256
    from saipen_engine.pending_ingress import ingress_digest

    return {ENV_TASK_SHA256: ingress_digest(text)}


def witnessed_operator(text: str):
    """Scoped operator carrier for direct engine calls in a disposable fixture."""
    return patch.dict(os.environ, operator_request_env(text))
