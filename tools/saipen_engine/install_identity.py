"""Canonical Install Identity & Divergence Doctor (SRC-258 / T-1798).

Eliminates divergence and ambiguous execution across multiple SAIPEN installs
(such as installed skills ~/.agents/skills/saipen vs source repositories).
Implements:
- Cryptographic install content fingerprinting (install_fingerprint) invariant across
  source repo layout (saipen/*.md) and flat installed skill layout (*.md).
- Precise divergence classification (MATCH, COPIES_IDENTICAL, DIVERGENT).
- Blocking mutating operations when running under an install that diverges from STATE.saipen_home.
- Non-destructive auto-convergence onto the proven running runtime.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

STATUS_MATCH = "MATCH"
STATUS_COPIES_IDENTICAL = "COPIES_IDENTICAL"
STATUS_DIVERGENT = "DIVERGENT"
STATUS_PERSISTED_HOME_UNREADABLE = "PERSISTED_HOME_UNREADABLE"
STATUS_PROTOCOL_ONLY = "PROTOCOL_ONLY"


def normalize_install_frames(root_path: Path | str) -> list[tuple[str, bytes]]:
    """Collect canonical framed records for an install, normalized across layouts.

    Supports:
    1. Repository clone layout (protocol docs under root/saipen/)
    2. Flat installed skill layout (protocol docs directly under root/)

    Ignores host-local metadata dotfiles (.saipen_runtime.json, .saipen_install.json),
    temporary files, and cache directories.
    """
    root = Path(root_path)
    try:
        if not root.exists() or not root.is_dir():
            return []
    except OSError:
        return []

    frames: list[tuple[str, bytes]] = []

    # 1. VERSION
    try:
        vp = root / "VERSION"
        if vp.is_file():
            frames.append(("VERSION", vp.read_bytes()))
    except OSError:
        return []

    # 2. Protocol documents & schemas (*.md, *.json, phases/*.md)
    try:
        has_saipen_dir = (root / "saipen").is_dir()
    except OSError:
        return []
    proto_root = root / "saipen" if has_saipen_dir else root

    for pattern in ("*.md", "*.json", "phases/*.md"):
        try:
            candidates = sorted(proto_root.glob(pattern))
        except OSError:
            return []
        for p in candidates:
            try:
                if not p.is_file() or p.name.startswith("."):
                    continue
                # Normalize to canonical 'saipen/<rel>' relative identifier
                rel = "saipen/" + p.relative_to(proto_root).as_posix()
                frames.append((rel, p.read_bytes()))
            except OSError:
                return []

    # 3. Engine tools (**/*.py)
    try:
        tools_root = root / "tools"
        if tools_root.is_dir():
            for p in sorted(tools_root.glob("**/*.py")):
                try:
                    if not p.is_file() or p.name.startswith(".") or "__pycache__" in p.parts:
                        continue
                    rel = p.relative_to(root).as_posix()
                    frames.append((rel, p.read_bytes()))
                except OSError:
                    return []
    except OSError:
        return []

    frames.sort(key=lambda x: x[0])
    return frames


def _fingerprint_frames(frames: list[tuple[str, bytes]]) -> str:
    if not frames:
        return "missing-v1"
    digest = hashlib.sha256()
    for rel, blob in frames:
        digest.update(rel.encode("utf-8") + b"\0" + str(len(blob)).encode("ascii") + b"\0" + blob)
    return "install-v1:" + digest.hexdigest()


def install_fingerprint(home: Path | str | None = None) -> str:
    """Generate cryptographic content fingerprint for an install.

    Returns 'install-v1:<sha256>' or 'missing-v1' if unreadable.
    """
    if home is None:
        from .state import running_home

        root = running_home()
    else:
        root = Path(home)

    frames = normalize_install_frames(root)
    return _fingerprint_frames(frames)


def diagnose_install_mismatch(
    persisted_home: object,
    running_home_path: Path | str | None = None,
) -> dict[str, Any]:
    """Classify install divergence between persisted STATE.saipen_home and running engine."""
    from .state import is_absolute_home, running_home

    running = (
        Path(running_home_path).resolve()
        if running_home_path is not None
        else running_home().resolve()
    )
    running_frames = normalize_install_frames(running)
    running_fp = _fingerprint_frames(running_frames)

    if persisted_home is None or not str(persisted_home).strip():
        return {
            "status": STATUS_MATCH,
            "running_home": str(running),
            "persisted_home": None,
            "running_fingerprint": running_fp,
            "persisted_fingerprint": None,
            "is_blocking": False,
            "detail": None,
        }

    raw_text = str(persisted_home).strip()
    if not is_absolute_home(raw_text):
        return {
            "status": STATUS_MATCH,
            "running_home": str(running),
            "persisted_home": raw_text,
            "running_fingerprint": running_fp,
            "persisted_fingerprint": None,
            "is_blocking": False,
            "detail": None,
        }

    try:
        named = Path(raw_text).expanduser().resolve()
    except OSError:
        return {
            "status": STATUS_PERSISTED_HOME_UNREADABLE,
            "running_home": str(running),
            "persisted_home": raw_text,
            "running_fingerprint": running_fp,
            "persisted_fingerprint": "missing-v1",
            "is_blocking": True,
            "detail": f"STATE.saipen_home path {raw_text!r} cannot be resolved",
            "remediation_command": None,
        }

    if named == running:
        return {
            "status": STATUS_MATCH,
            "running_home": str(running),
            "persisted_home": str(named),
            "running_fingerprint": running_fp,
            "persisted_fingerprint": running_fp,
            "is_blocking": False,
            "detail": None,
        }

    from . import machine_runtime

    try:
        reg = machine_runtime.executing()
        if reg is not None and machine_runtime.projects(reg, named):
            return {
                "status": STATUS_MATCH,
                "running_home": str(running),
                "persisted_home": str(named),
                "running_fingerprint": running_fp,
                "persisted_fingerprint": running_fp,
                "is_blocking": False,
                "detail": None,
            }
    except Exception:
        pass

    named_frames = normalize_install_frames(named)
    named_fp = _fingerprint_frames(named_frames)

    if named_fp == "missing-v1":
        from .state import HOME_DEAD, persisted_home_access

        access, access_reason = persisted_home_access(named)
        return {
            "status": STATUS_PERSISTED_HOME_UNREADABLE,
            "running_home": str(running),
            "persisted_home": str(named),
            "running_fingerprint": running_fp,
            "persisted_fingerprint": named_fp,
            "is_blocking": True,
            "detail": access_reason
            or f"STATE.saipen_home {named} has no complete readable identity",
            "remediation_command": "saipen rebind-home --auto" if access == HOME_DEAD else None,
        }

    if running_fp == named_fp:
        return {
            "status": STATUS_COPIES_IDENTICAL,
            "running_home": str(running),
            "persisted_home": str(named),
            "running_fingerprint": running_fp,
            "persisted_fingerprint": named_fp,
            "is_blocking": False,
            "detail": (
                f"the RUNNING install is {running} but STATE.saipen_home names {named} -- "
                f"both paths carry identical content fingerprint ({running_fp}). "
                f"Safe to converge with `saipen rebind-home --auto`."
            ),
            "remediation_command": "saipen rebind-home --auto",
        }

    # Protocol-only homes and transport shims do not carry a second engine.
    # Keep their distinct fingerprints visible without inventing an equality
    # or deriving execution authority from text inside a script.
    named_has_engine = any(rel.startswith("tools/saipen_engine/") for rel, _ in named_frames)
    if not named_has_engine:
        return {
            "status": STATUS_PROTOCOL_ONLY,
            "running_home": str(running),
            "persisted_home": str(named),
            "running_fingerprint": running_fp,
            "persisted_fingerprint": named_fp,
            "is_blocking": False,
            "detail": (
                f"STATE.saipen_home {named} carries protocol documents or transport, "
                "without an independent engine"
            ),
        }

    return {
        "status": STATUS_DIVERGENT,
        "running_home": str(running),
        "persisted_home": str(named),
        "running_fingerprint": running_fp,
        "persisted_fingerprint": named_fp,
        "is_blocking": True,
        "detail": (
            f"the RUNNING install is {running} (fingerprint: {running_fp}) but "
            f"STATE.saipen_home names {named} (fingerprint: {named_fp}) -- "
            f"the installs carry different protocol or engine bytes. "
            f"Evidence produced now is attributable to the running engine, not the named one. "
            "Run saipen through the install STATE names, "
            "or converge with `saipen rebind-home --auto`."
        ),
        "remediation_command": "saipen rebind-home --auto",
    }


def is_install_divergent(
    persisted_home: object,
    running_home_path: Path | str | None = None,
) -> bool:
    """True if persisted home is divergent in content fingerprint from the running engine."""
    diag = diagnose_install_mismatch(persisted_home, running_home_path)
    return diag["status"] == STATUS_DIVERGENT
