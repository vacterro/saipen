"""Effect-aware protected-root write refusal (SRC-275 R006 / DRIFT-01).

The measured defect: an engine refused a project root with
``FORENSICALLY_UNRECOVERABLE`` / ``READ_ONLY_DIAGNOSIS_ONLY`` and listed
``Bash``, ``Edit``, ``Write`` as forbidden probes -- and the next turn wrote
``LOG.md`` and ``STATE.md`` with an embedded Python script anyway. The refusal was
attached to a VERB NAME. The mutation arrived through an interpreter. Nothing in
the engine connected "this root is on hold" to "these exact files may not change",
so the hold was advisory prose.

That is the same class of mistake ``effects`` exists to fix
(INC-PERMISSION-EFFECT-BYPASS-001), one layer down: ``effects`` answers *what an
operation exercises*; this module answers *is this target under a hold*. A shell
carrying an interpreter is POTENTIALLY mutating, but the gate must not depend on
recognising the command -- it depends on the TARGET. Renaming the verb, nesting a
subshell, or importing ``pathlib`` inside ``python -c`` changes nothing, because
the decision is a function of (root, hold, target path), never of the tool name.

Two records, deliberately separate:

* the HOLD -- ``.saipen/HOLD.json``, written only by a canonical operation. It
  names the root, the reason, the protected paths, and the one command that could
  lift it. It is DURABLE, because the defect was exactly that a transient refusal
  left no durable marker for the next process to read.
* the VERDICT -- a pure function of that hold and a target. It is
  ``REFUSE`` by default and fails closed on every unreadable or ambiguous input.

Fail-closed rules, each of which is a negative control in
``tools/test_t1816_protected_root_hold.py``:

* no hold file -> ``ALLOW`` (an ordinary project is untouched by this gate);
* hold file present but unparseable -> ``REFUSE``, because a corrupt hold is not
  evidence of no hold;
* hold file with an unknown ``mode`` -> ``REFUSE``;
* target under a protected path -> ``REFUSE`` regardless of tool or verb;
* a caller-declared read-only intent does NOT bypass the gate. Intent is not an
  effect; the whole point is that the actor's belief about a command cannot
  authorize it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .effects import FS_DELETE, FS_WRITE, MUTATING_EFFECTS

HOLD_FILE = ".saipen/HOLD.json"

#: Hold modes. Only one is defined today; an unknown mode refuses rather than
#: guessing, so a future mode cannot silently weaken an existing hold.
MODE_READ_ONLY = "READ_ONLY_DIAGNOSIS_ONLY"
HOLD_MODES = (MODE_READ_ONLY,)

ALLOW = "ALLOW"
REFUSE = "REFUSE"

#: What a verdict may NOT be derived from. Recorded in the response so a caller
#: can see the gate ignored the tempting-but-wrong signals.
NON_SIGNALS = ("tool_name", "verb", "declared_intent", "command_text")

#: The files a hold protects when the hold does not name its own set. These are
#: the append-only/mutable memory surfaces; code and docs stay writable so a
#: read-only forensic pass can still produce evidence.
DEFAULT_PROTECTED = (
    ".saipen/LOG.md",
    ".saipen/STATE.md",
    ".saipen/BOARD.md",
    ".saipen/MANIFEST.json",
    ".saipen/IDENTITY.md",
)


def _norm(path: str | os.PathLike) -> str:
    return str(path).replace("\\", "/").strip()


def load_hold(root: Path | str) -> dict:
    """Read the hold, or report why there is none. Never raises.

    ``state`` is one of ``ABSENT`` / ``ACTIVE`` / ``UNREADABLE``. ``UNREADABLE``
    is NOT ``ABSENT``: a hold file that exists but cannot be parsed must refuse,
    because deleting or corrupting the file would otherwise lift the hold.
    """
    path = Path(root) / HOLD_FILE
    if not path.is_file():
        return {"state": "ABSENT", "path": HOLD_FILE, "hold": None, "detail": "no hold file"}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as error:  # unreadable is a verdict, not a crash
        return {
            "state": "UNREADABLE",
            "path": HOLD_FILE,
            "hold": None,
            "detail": f"hold file exists but cannot be parsed: {type(error).__name__}",
        }
    if not isinstance(data, dict):
        return {
            "state": "UNREADABLE",
            "path": HOLD_FILE,
            "hold": None,
            "detail": "hold file is not a JSON object",
        }
    return {"state": "ACTIVE", "path": HOLD_FILE, "hold": data, "detail": "hold is active"}


def protected_paths(hold: dict | None) -> tuple[str, ...]:
    """The protected path set a hold declares, normalized, or the default set."""
    if isinstance(hold, dict):
        declared = hold.get("protected_paths")
        if isinstance(declared, list):
            paths = tuple(
                _norm(item) for item in declared if isinstance(item, str) and item.strip()
            )
            if paths:
                return paths
    return tuple(DEFAULT_PROTECTED)


def _matches(target: str, protected: str) -> bool:
    """Is `target` the protected path, or inside it if it is a directory?

    Plain prefix matching is wrong in one direction that matters: a hold on
    ``.saipen/LOG.md`` must not protect ``.saipen/LOG.md.bak``, and a hold on
    ``.saipen/`` must protect everything under it. Both forms are supported.
    """
    target = _norm(target)
    protected = _norm(protected)
    if not protected:
        return False
    if protected.endswith("/"):
        return target.startswith(protected) or target == protected.rstrip("/")
    return target == protected or target.startswith(protected + "/")


def targets_held(targets: list[str] | tuple[str, ...], hold: dict | None) -> list[str]:
    """The subset of `targets` a hold protects, in input order."""
    protected = protected_paths(hold)
    hits: list[str] = []
    for target in targets:
        if not isinstance(target, str) or not target.strip():
            continue
        if any(_matches(target, item) for item in protected):
            hits.append(_norm(target))
    return list(dict.fromkeys(hits))


def _relative_to_root(path: str, root: Path | str) -> str:
    """Express `path` relative to `root` when it lies inside it, else unchanged.

    A caller may hand over an absolute Windows path. Comparing that against the
    hold's relative entries would silently mismatch and ALLOW the write, so the
    normalization happens here rather than trusting the caller.
    """
    raw = _norm(path)
    try:
        base = Path(root).resolve()
        candidate = Path(path)
        if not candidate.is_absolute():
            return raw
        return _norm(candidate.resolve().relative_to(base))
    except Exception:  # a foreign path stays foreign, never crashes
        return raw


def check(
    root: Path | str,
    targets: list[str] | tuple[str, ...],
    *,
    effect: str = FS_WRITE,
    command: str | None = None,
    tool: str | None = None,
) -> dict:
    """Should this operation proceed? A pure, fail-closed verdict.

    Returns ``{"verdict", "code", "held", "hold_state", "detail", ...}``. The
    response names the signals it IGNORED (``tool``, ``command``) so a reviewer can
    see the gate did not decide on a verb name.

    A non-mutating effect is allowed through: reading a held root is the entire
    purpose of a read-only forensic pass. A mutating effect on a held target
    refuses, whatever produced the call.
    """
    loaded = load_hold(root)
    state = loaded["state"]
    base = {
        "root": _norm(root),
        "effect": effect,
        "hold_state": state,
        "hold_path": HOLD_FILE,
        "non_signals": list(NON_SIGNALS),
        "tool": tool,
        "command_present": bool(command),
    }

    if effect not in MUTATING_EFFECTS:
        return {
            **base,
            "verdict": ALLOW,
            "code": "NON_MUTATING",
            "held": [],
            "detail": f"{effect} does not change project state; a hold governs mutation",
        }

    if state == "ABSENT":
        return {
            **base,
            "verdict": ALLOW,
            "code": "NO_HOLD",
            "held": [],
            "detail": "no hold is declared for this root",
        }

    if state == "UNREADABLE":
        return {
            **base,
            "verdict": REFUSE,
            "code": "HOLD_UNREADABLE",
            "held": list(targets),
            "detail": loaded["detail"] + "; fail closed rather than assume no hold",
        }

    hold = loaded["hold"] or {}
    mode = str(hold.get("mode") or "")
    if mode not in HOLD_MODES:
        return {
            **base,
            "verdict": REFUSE,
            "code": "HOLD_MODE_UNKNOWN",
            "held": list(targets),
            "detail": f"hold mode {mode!r} is not one of {list(HOLD_MODES)}; fail closed",
        }

    relative = [_relative_to_root(item, root) for item in targets]
    held = targets_held(relative, hold)
    if held:
        return {
            **base,
            "verdict": REFUSE,
            "code": "PROTECTED_TARGET",
            "held": held,
            "reason": hold.get("reason"),
            "lift_command": hold.get("lift_command"),
            "detail": (
                f"{effect} targets protected memory under an active {mode} hold; "
                "rename the verb, wrap it in a shell, or reinterpret it in an "
                "interpreter and the verdict is unchanged"
            ),
        }
    return {
        **base,
        "verdict": ALLOW,
        "code": "TARGET_NOT_HELD",
        "held": [],
        "detail": "the hold is active but none of these targets is protected by it",
    }


def delete_effect_for(target: str) -> str:
    """The effect a deletion of `target` carries. Kept for callers that only
    know the path and must still be judged as a mutation, not a write."""
    return FS_DELETE
