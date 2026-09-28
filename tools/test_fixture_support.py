"""Shared authority for fixtures that model the current installed STYLE."""

from __future__ import annotations

from pathlib import Path

from saipen_engine.state import running_style_token, style_contract_token


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