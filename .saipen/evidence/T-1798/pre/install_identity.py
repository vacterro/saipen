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
        pass

    # 2. Protocol documents & schemas (*.md, *.json, phases/*.md)
    try:
        has_saipen_dir = (root / "saipen").is_dir()
    except OSError:
        has_saipen_dir = False
    proto_root = root / "saipen" if has_saipen_dir else root

    for pattern in ("*.md", "*.json", "phases/*.md"):
        try:
            candidates = sorted(proto_root.glob(pattern))
        except OSError:
            continue
        for p in candidates:
            try:
                if not p.is_file() or p.name.startswith("."):
                    continue
                # Normalize to canonical 'saipen/<rel>' relative identifier
                rel = "saipen/" + p.relative_to(proto_root).as_posix()
                frames.append((rel, p.read_bytes()))
            except OSError:
                continue

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
                    continue
    except OSError:
        pass

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

    running = Path(running_home_path).resolve() if running_home_path is not None else running_home().resolve()
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
            "remediation_command": "saipen rebind-home --auto",
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

    # If named's tools/saipen.py is a delegation shim executing the running engine,
    # it is identical in execution authority to running.
    try:
        spy = named / "tools" / "saipen.py"
        if spy.is_file() and spy.stat().st_size < 4096:
            spy_text = spy.read_text(encoding="utf-8", errors="replace")
            if "runpy.run_path" in spy_text:
                import re
                norm_run = re.sub(r"[\\/]+", "/", str(running)).lower()
                norm_spy = re.sub(r"[\\/]+", "/", spy_text).lower()
                if norm_run in norm_spy:
                    return {
                        "status": STATUS_COPIES_IDENTICAL,
                        "running_home": str(running),
                        "persisted_home": str(named),
                        "running_fingerprint": running_fp,
                        "persisted_fingerprint": running_fp,
                        "is_blocking": False,
                        "detail": f"STATE.saipen_home {named} delegates to running engine",
                        "remediation_command": "saipen rebind-home --auto",
                    }
    except OSError:
        pass

    named_frames = normalize_install_frames(named)
    named_fp = _fingerprint_frames(named_frames)

    if named_fp == "missing-v1":
        return {
            "status": STATUS_PERSISTED_HOME_UNREADABLE,
            "running_home": str(running),
            "persisted_home": str(named),
            "running_fingerprint": running_fp,
            "persisted_fingerprint": named_fp,
            "is_blocking": True,
            "detail": f"STATE.saipen_home {named} has no readable protocol files",
            "remediation_command": "saipen rebind-home --auto",
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

    # If named is not an independent engine install (needs both tools/ and VERSION),
    # it cannot be a divergent engine install answering to the same version.
    try:
        named_has_tools = any(f[0].startswith("tools/") for f in named_frames)
        named_has_version = any(f[0] == "VERSION" for f in named_frames)
    except Exception:
        named_has_tools = False
        named_has_version = False

    if not (named_has_tools and named_has_version):
        return {
            "status": STATUS_COPIES_IDENTICAL,
            "running_home": str(running),
            "persisted_home": str(named),
            "running_fingerprint": running_fp,
            "persisted_fingerprint": named_fp,
            "is_blocking": False,
            "detail": f"STATE.saipen_home {named} is a doc-only or non-engine home; executing via running engine",
            "remediation_command": "saipen rebind-home --auto",
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
            f"two DIVERGENT installs answer to the same version! "
            f"Evidence produced now is attributable to the running engine, not the named one. "
            f"Run saipen through the install STATE names, or converge with `saipen rebind-home --auto`."
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
