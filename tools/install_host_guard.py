"""Install native Kiro/Gemini hooks without replacing unrelated user hooks.

Reports artifact/config freshness separately from runtime health. Installation
cannot prove host execution; health and effective enforcement remain UNKNOWN.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
NAME = "saipen-guard"


def command(host: str, artifact: Path, root: Path) -> str:
    argv = [sys.executable, str(artifact), "--host", host, "--saipen-root", str(root)]
    if os.name == "nt":
        # Hook commands are interpreted by cmd.exe on this platform. Refuse
        # expansion/control characters rather than invent shell escaping.
        if any(any(c in arg for c in "%!&|<>^\r\n") for arg in argv):
            raise ValueError("hook command path contains Windows shell control characters")
        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == data:
        return
    fd, temp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def install(host: str, home: Path, root: Path = ROOT, *, check: bool = False) -> dict:
    registry = json.loads((root / "extensions/adapters/registry.json").read_text())
    entry = next(item for item in registry["adapters"] if item["id"] == host)
    artifact = home / entry["hook_install_surface"].removeprefix("~/")
    config = home / entry["hook_config_surface"].removeprefix("~/")
    invocation = command(host, artifact, root)
    original = config.read_bytes() if config.exists() else None
    data = json.loads(original.decode("utf-8-sig")) if original is not None else {}
    if not isinstance(data, dict):
        raise ValueError("hook config must be a JSON object")
    if host == "gemini":
        hooks = data.setdefault("hooks", {})
        if not isinstance(hooks, dict):
            raise ValueError("hooks must be an object")
        groups = hooks.setdefault("BeforeTool", [])
        if not isinstance(groups, list):
            raise ValueError("BeforeTool must be an array")
        expected = {
            "matcher": ".*",
            "hooks": [
                {
                    "name": NAME,
                    "type": "command",
                    "command": invocation,
                    "timeout": 30000,
                }
            ],
        }
        preserved = []
        owned = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                raise ValueError("malformed BeforeTool hook group")
            remaining = []
            for hook in group["hooks"]:
                if not isinstance(hook, dict):
                    raise ValueError("malformed hook entry")
                if hook.get("name") == NAME:
                    owned.append((group.get("matcher"), hook))
                else:
                    remaining.append(hook)
            if remaining or not group["hooks"]:
                preserved.append({**group, "hooks": remaining})
        configured = owned == [(".*", expected["hooks"][0])]
        hooks["BeforeTool"] = [*preserved, expected]
    else:
        expected = {
            "version": "v1",
            "hooks": [
                {
                    "name": NAME,
                    "trigger": "PreToolUse",
                    "matcher": ".*",
                    "action": {"type": "command", "command": invocation},
                    "timeout": 30,
                }
            ],
        }
        if data and (
            data.get("version") != "v1" or any(h.get("name") != NAME for h in data.get("hooks", []))
        ):
            raise ValueError("reserved SAIPEN hook file contains unrelated configuration")
        configured = data == expected
        data = expected
    shipped = (root / entry["hook_artifact"]).read_bytes()
    installed = artifact.is_file()
    current = installed and artifact.read_bytes() == shipped and configured
    if not check:
        # Preserve original settings once by content identity; never overwrite
        # a user's earlier backup. Malformed config is refused before writes.
        encoded = (json.dumps(data, indent=2) + "\n").encode("utf-8")
        if original is not None and original != encoded:
            import hashlib

            backup = config.with_name(
                config.name + "." + hashlib.sha256(original).hexdigest()[:16] + ".bak"
            )
            if not backup.exists():
                atomic_write(backup, original)
        atomic_write(artifact, shipped)
        atomic_write(config, encoded)
        installed = current = configured = True
    return {
        "host": host,
        "capability": True,
        "installed": installed,
        "current": current,
        "configured": configured,
        "health": None,
        "effective": "UNKNOWN" if current else "ENFORCEMENT_GAP",
        "artifact": str(artifact),
        "config": str(config),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", choices=("kiro", "gemini"))
    parser.add_argument("--home", type=Path, default=Path.home())
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    try:
        print(json.dumps(install(args.host, args.home, check=args.check), indent=2))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"effective": "UNKNOWN", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
