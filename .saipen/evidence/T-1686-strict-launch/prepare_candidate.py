"""Prepare strict-policy launch changes in evidence, never the frozen tree."""
import difflib
import hashlib
import json
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
evidence = Path(__file__).resolve().parent
changes = {
    "tools/saipen_engine/host_launch.py": [
        (
            '    Read from the registry (`degraded_mode`): a host whose integration degrades\n',
            '    Operator STRICT policy refuses every runtime gap. Otherwise the registry\n'
            '    (`degraded_mode`) decides whether a host whose integration degrades\n',
        ),
        (
            '    for item in _registry_adapters():\n'
            '        if str(item.get("id")) == host_id:\n',
            '    from .host_authority_client import authority_mode\n'
            '    from .host_taxonomy import MODE_STRICT\n\n'
            '    if authority_mode() == MODE_STRICT:\n'
            '        return False\n'
            '    for item in _registry_adapters():\n'
            '        if str(item.get("id")) == host_id:\n',
        ),
        (
            'class HostLaunchRefusal(ValueError):\n'
            '    """The requested launch cannot establish an explicit bounded envelope."""\n',
            'class HostLaunchRefusal(ValueError):\n'
            '    """The requested launch cannot establish an explicit bounded envelope."""\n\n'
            '    def __init__(self, message: str, *, operator_action: str | None = None):\n'
            '        super().__init__(message)\n'
            '        self.operator_action = operator_action\n',
        ),
        (
            '    env = build_launch_environment(project_root, seat, base_env=base_env)\n'
            '    if prelaunch:\n',
            '    env = build_launch_environment(project_root, seat, base_env=base_env)\n'
            '    may_degrade = launch_degrades(host_id)\n'
            '    if prelaunch or not may_degrade:\n',
        ),
        (
            '            if not launch_degrades(host_id):\n'
            '                raise\n',
            '            if not may_degrade:\n'
            '                from .host_taxonomy import REPAIR\n\n'
            '                raise HostLaunchRefusal(\n'
            '                    f"{exc}; recover with: {REPAIR}", operator_action=REPAIR\n'
            '                ) from exc\n',
        ),
    ],
    "tools/saipen.py": [
        (
            '            _emit({"ok": False, "code": "HOST_LAUNCH_REFUSED", "detail": str(exc)}, as_json)\n',
            '            _emit(\n'
            '                {"ok": False, "code": "HOST_LAUNCH_REFUSED", "detail": str(exc),\n'
            '                 **({"operator_action": exc.operator_action} if exc.operator_action else {})},\n'
            '                as_json,\n'
            '            )\n',
        ),
    ],
}
rows, patch = [], []
for relative, replacements in changes.items():
    before = (root / relative).read_bytes()
    after = before
    newline = "\r\n" if b"\r\n" in before else "\n"
    for old, new in replacements:
        old_bytes, new_bytes = (value.replace("\n", newline).encode() for value in (old, new))
        if after.count(old_bytes) != 1:
            raise ValueError(f"source anchor moved: {relative}")
        after = after.replace(old_bytes, new_bytes, 1)
    for folder, content in (("pre", before), ("candidate", after)):
        target = evidence / folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    rows.append({"path": relative, "before_sha256": hashlib.sha256(before).hexdigest(),
                 "after_sha256": hashlib.sha256(after).hexdigest()})
    patch.extend(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
                                    fromfile="pre/" + relative, tofile=relative))
(evidence / "subjects.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
(evidence / "candidate.diff").write_text("".join(patch), encoding="utf-8")
print(json.dumps(rows, indent=2))
