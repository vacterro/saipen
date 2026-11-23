"""T-1889: which heavy trees a focused check must copy into its sandbox.

A focused gate on this tree was measured at 71-80 s, of which 54-60 s was the
sandbox copy: 1815 MiB in 135450 files, `.saipen` 1474 MiB and `.git` 345 MiB,
while the selected tests executed in 1.5 s. Excluding both plus `audit` copies
21 MiB in 0.53 s. Most modules never read either tree.

Two properties make narrowing defensible, and both are checkable rather than
assumed:

  * it cannot weaken what a PASS claims about the SOURCE TREE, because
    `tree_fingerprint` already excludes `.git` and `.saipen` at the top level
    (``core_unit.FINGERPRINT_EXCLUDED``). A record never attested those bytes,
    so not copying them preserves the exact file set the record describes.
  * the decision itself is a per-module DECLARATION, never an inference. The
    campaign's own hard rule is that static imports do not prove dependency
    completeness, and an audit hook over two modules returning zero hits is not
    evidence about a third. So this module reads a manifest and nothing else.

DEFAULT IS FULL. A pattern with no manifest entry copies everything, exactly as
before. A declaration can only list trees to ADD to the source copy; entries
naming anything but a whole `.git` or one `.saipen/<child>` subtree are an
error, so no declaration can silently drop part of the tested subject.

The resolved decision is recorded in the evidence record and folded into the
verification configuration, so a slim record can never be replayed for a scope
that would have copied more (INV-20).
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from pathlib import Path

#: Tracked beside the tests it describes, not under `.saipen/`: a manifest is
#: part of the subject being verified, exactly like `verification_policy.json`.
SCOPE_REL = "tools/sandbox_scope.json"
SCHEMA = 1

FULL = "FULL"
DECLARED = "DECLARED"

_GIT = ".git"
_SAIPEN_PREFIX = ".saipen/"
#: One whole history tree, or one direct subtree of the canonical directory.
#: Nothing else: a narrower entry (`tools`) would drop part of the subject and
#: make the fingerprint describe bytes that were never run.
_ENTRY = re.compile(r"^(?:\.git|\.saipen/[A-Za-z0-9_.-]+)$")


class ScopeError(ValueError):
    """A manifest that cannot be trusted. Always a refusal, never a fallback."""


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _load(root: Path) -> tuple[dict, str | None]:
    """``(modules, manifest_sha256)``; ``({}, None)`` when there is no manifest.

    A MISSING file is the legacy state and means "nothing is declared", which
    resolves to FULL. An UNREADABLE or INVALID one is a refusal: a typo that
    silently degraded to a full copy would hide the operator's intent, and a
    typo that silently degraded to a narrow one would hide a missing tree.
    """
    path = Path(root) / SCOPE_REL
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {}, None
    except OSError as exc:
        raise ScopeError(f"{SCOPE_REL} is unreadable: {exc}") from exc
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ScopeError(f"{SCOPE_REL} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        raise ScopeError(f"{SCOPE_REL} must be an object with schema {SCHEMA}")
    modules = data.get("modules")
    if not isinstance(modules, dict):
        raise ScopeError(f"{SCOPE_REL} must carry a 'modules' object")
    for name, trees in modules.items():
        if not (isinstance(name, str) and name.startswith("test_") and name.endswith(".py")
                and "/" not in name and "\\" not in name):
            raise ScopeError(f"{SCOPE_REL}: {name!r} is not a test_*.py module name")
        if not isinstance(trees, list) or any(not isinstance(item, str) for item in trees):
            raise ScopeError(f"{SCOPE_REL}: {name} must name a list of trees")
        for entry in trees:
            if not _ENTRY.match(entry):
                raise ScopeError(
                    f"{SCOPE_REL}: {name} declares {entry!r}; only '.git' or "
                    "'.saipen/<child>' may be named, because anything else would "
                    "drop part of the tested subject"
                )
            if entry.startswith(_SAIPEN_PREFIX) and not (Path(root) / entry).is_dir():
                raise ScopeError(f"{SCOPE_REL}: {name} declares a missing subtree {entry!r}")
    return modules, _sha256(raw)


def select_modules(root: Path | str, patterns) -> tuple[list[str], list[str]]:
    """The focused runner's own filename-selection contract, shared by every
    consumer that needs to know which test modules a pattern set selects.

    ``(selected, unmatched)``: the sorted module filenames in ``tools/`` that
    at least one pattern matches, and the patterns that match no file today.
    Selection and sandbox copying must not implement two different pattern
    languages: a wildcard that the runner expands but the resolver compares as
    a literal silently degrades a declared run to a FULL copy.

    ``fnmatch.fnmatchcase`` is the contract ``focused_unit`` already used. It
    is case-sensitive on every platform, so a Windows run and a POSIX run
    select the same modules from the same names.
    """
    root = Path(root)
    try:
        filenames = sorted(p.name for p in (root / "tools").iterdir() if p.is_file())
    except OSError:
        filenames = []
    selected: set[str] = set()
    unmatched: list[str] = []
    for pattern in sorted(set(patterns)):
        hits = [name for name in filenames if fnmatch.fnmatchcase(name, pattern)]
        if hits:
            selected.update(hits)
        else:
            unmatched.append(pattern)
    return sorted(selected), unmatched


def resolve(root: Path | str, patterns) -> dict:
    """The sandbox scope decision for one pattern set.

    Patterns are expanded through :func:`select_modules`, the same contract the
    focused runner executes, so ``test_t2093_*.py`` reaches the four modules it
    really selects instead of being compared to manifest keys as a literal.

    ALL selected modules must be declared for a narrow copy. One undeclared or
    unmatched pattern makes the whole run FULL, because one sandbox holds one
    snapshot and the undeclared module would otherwise read a tree nobody
    declared it needs. An empty selection is not a refusal here: the focused
    route refuses it before the copy (`preflight.selection_problem`), and the
    resolver's answer stays a well-formed FULL decision for record validation.
    """
    root = Path(root)
    patterns = sorted(set(patterns))
    modules, digest = _load(root)
    selected, unmatched = select_modules(root, patterns)
    undeclared = sorted({name for name in selected if name not in modules})
    blocked = sorted(unmatched) + undeclared
    if blocked:
        return {"mode": FULL, "trees": [], "undeclared": blocked,
                "selected": selected, "manifest_sha256": digest}
    trees = sorted({entry for name in selected for entry in modules[name]})
    return {"mode": DECLARED, "trees": trees, "undeclared": [],
            "selected": selected,
            "declared_by": {name: list(modules[name]) for name in selected},
            "manifest_sha256": digest}


def identity(scope: dict) -> dict:
    """The part of a decision that changes the sandbox's bytes.

    Deliberately excludes ``manifest_sha256``: editing an UNRELATED module's
    entry does not change what this pattern set copies, and invalidating every
    record for such an edit would be churn, not safety. Editing THIS set's
    trees does change the bytes, and it changes this value with them.
    """
    return {"mode": scope["mode"], "trees": list(scope["trees"])}


def problem(scope: object) -> str | None:
    """Why a recorded decision is not a well-formed one, or None."""
    if not isinstance(scope, dict):
        return "sandbox scope is missing from the focused record"
    mode = scope.get("mode")
    trees = scope.get("trees")
    if mode not in (FULL, DECLARED):
        return "sandbox scope has no recognised mode"
    if not isinstance(trees, list) or any(not isinstance(item, str) for item in trees):
        return "sandbox scope trees must be a list of names"
    if mode == FULL and trees:
        return "a FULL sandbox scope cannot declare trees"
    if mode == DECLARED:
        # An EMPTY list is the point of this feature: the module declared that
        # it reads no heavy tree, so the sandbox is the source tree only.
        for entry in trees:
            if not _ENTRY.match(entry):
                return f"sandbox scope names an unfilterable tree {entry!r}"
    return None


def is_current(recorded: object, current: dict) -> str | None:
    """Why a recorded decision no longer matches the manifest, or None.

    A narrowed record describes a sandbox WITHOUT some trees. If the manifest
    has since grown that module's declaration, replaying the record would
    present a pass from a copy that no longer matches the declared input.
    """
    issue = problem(recorded)
    if issue is not None:
        return issue
    if identity(recorded) != identity(current):
        return ("sandbox scope changed since this record ran: recorded "
                f"{identity(recorded)}, manifest now resolves to {identity(current)}")
    return None


def copy_plan(scope: dict) -> tuple[frozenset | None, list[str] | None]:
    """``(extra_top_level_trees, allowed_saipen_children)`` for the copier.

    ``(None, None)`` means copy everything, which is the FULL decision. A
    frozenset is the exact set of trees the sandbox must contain, so an empty
    frozenset is meaningful: source tree only.
    """
    if scope["mode"] == FULL:
        return None, None
    trees = frozenset(scope["trees"])
    children = sorted(entry.split("/", 1)[1] for entry in trees
                      if entry.startswith(_SAIPEN_PREFIX))
    return trees, children
