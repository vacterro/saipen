"""Build the T-1557 candidate without modifying repository source files."""

from __future__ import annotations

import difflib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
SOURCE = ROOT / "tools" / "saipen_engine" / "subs.py"


def replace_once(text: str, before: str, after: str) -> str:
    if text.count(before) != 1:
        raise AssertionError(f"expected one replacement anchor: {before!r}")
    return text.replace(before, after, 1)


original = SOURCE.read_text(encoding="utf-8")
candidate = replace_once(
    original,
    "from .state import patch_state\n",
    "from .state import parse_state_or_error, patch_state, running_style_token\n",
)
candidate = replace_once(
    candidate,
    '    now = _utc_iso()\n    template_state_doc = codec.read_document(template_paths["STATE.md"])\n',
    '    style_token = running_style_token()\n'
    '    if style_token is None:\n'
    '        return _refuse(\n'
    '            "VALIDATION_FAILED", "running install has no readable STYLE.md", name=name\n'
    '        )\n'
    '    now = _utc_iso()\n    template_state_doc = codec.read_document(template_paths["STATE.md"])\n',
)
candidate = replace_once(
    candidate,
    '            "updated": now,\n            "role_revision": role_revision,\n',
    '            "updated": now,\n            "role_revision": role_revision,\n'
    '            "style_contract": style_token,\n',
)
candidate = replace_once(
    candidate,
    '    from .state import parse_state as _parse_sub_state_text\n\n'
    '    proposed_state = _parse_sub_state_text(state)\n'
    '    state_errors = validate_sub_state(proposed_state)\n',
    '    # Use the same strict read as health before committing a new worker.\n'
    '    proposed_state, state_error = parse_state_or_error(state)\n'
    '    state_errors = [state_error] if state_error else validate_sub_state(proposed_state)\n',
)
candidate = replace_once(
    candidate,
    '    doc = codec.read_document(state_path)\n'
    '    rel = f"{SUBS_REL}/{name}/STATE.md"\n'
    '    new_text = patch_state(\n'
    '        doc.text_norm,\n'
    '        {\n'
    '            "role_revision": role_revision,\n'
    '            "updated": _utc_iso(),\n'
    '        },\n'
    '    )\n',
    '    style_token = running_style_token()\n'
    '    if style_token is None:\n'
    '        return _refuse(\n'
    '            "VALIDATION_FAILED", "running install has no readable STYLE.md", name=name\n'
    '        )\n'
    '    doc = codec.read_document(state_path)\n'
    '    rel = f"{SUBS_REL}/{name}/STATE.md"\n'
    '    new_text = patch_state(\n'
    '        doc.text_norm,\n'
    '        {\n'
    '            "role_revision": role_revision,\n'
    '            "updated": _utc_iso(),\n'
    '            "style_contract": style_token,\n'
    '        },\n'
    '    )\n'
    '    proposed_state, state_error = parse_state_or_error(new_text)\n'
    '    state_errors = [state_error] if state_error else validate_sub_state(proposed_state)\n'
    '    if state_errors:\n'
    '        return _refuse(\n'
    '            "VALIDATION_FAILED",\n'
    '            "proposed worker STATE fails lifecycle grammar: " + "; ".join(state_errors[:3]),\n'
    '            name=name,\n'
    '        )\n',
)
(HERE / "subs.py.candidate").write_text(candidate, encoding="utf-8", newline="\n")
patch = "".join(
    difflib.unified_diff(
        original.splitlines(keepends=True),
        candidate.splitlines(keepends=True),
        fromfile="a/tools/saipen_engine/subs.py",
        tofile="b/tools/saipen_engine/subs.py",
    )
)
test_source = (HERE / "test_sub_style_contract.py").read_text(encoding="utf-8")
patch += "".join(
    difflib.unified_diff(
        [], test_source.splitlines(keepends=True),
        fromfile="/dev/null", tofile="b/tools/test_sub_style_contract.py",
    )
)
(HERE / "candidate.patch").write_text(patch, encoding="utf-8", newline="\n")
print(f"candidate patch: {HERE / 'candidate.patch'}")
