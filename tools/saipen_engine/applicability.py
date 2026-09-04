"""Does this capability have anything to apply to? (T-1279, `CREW-APPLICABILITY-01`)

The crew roster was static. `CrewRole.ensure_instance` is a bool on a frozen
dataclass, `crew.py` iterates it, and nothing anywhere in `subs.py`, `crew.py`
or `producer.py` could express that a project has no UI. So every crew cycle
ran a mandatory UI stage against a surface that does not exist, and the honest
report of that fact -- "there is nothing to scan" -- was written eleven times
in a row, each one becoming a Core review ticket with a claim, a verify clause
and a disposition.

The cost was never the empty package. A scanner that honestly finds nothing has
done its job, and six-signal coverage is real coverage. The cost is that
**absence of a surface and correctness of a surface reported identically**: a
reader of the crew record could not tell "UI was audited and is fine" from
"there is no UI", and every release carried a green UI certification either way.
That is a missing applicability model, not a misbehaving sensor.

This module is the DECISION only, kept pure so the promise is provable without
copying a tree and running the whole circuit. `collect_facts` is the single
impure function and it is deliberately at the bottom, separated by a banner:
everything above it is a function of its arguments.

Two rules carry the weight:

* **Undecidable is APPLICABLE.** A probe that cannot answer -- no Git, an
  unreadable tree, a probe name the registry does not know -- resolves to
  `APPLICABLE`. A capability that runs when it did not need to costs a pass; a
  capability silently skipped costs the coverage it was there to provide, and
  nothing reports the difference. The model fails toward doing the work.
* **A verdict always names the deciding fact.** `NOT_APPLICABLE` with no reason
  is indistinguishable from a stage nobody ran, which is the exact confusion
  this module exists to remove.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

APPLICABLE = "APPLICABLE"
NOT_APPLICABLE = "NOT_APPLICABLE"

#: Probe names a `CrewRole` may declare. Closed set: an unknown name is not a
#: silent skip, it resolves APPLICABLE and says so.
ALWAYS = "always"
VISUAL_SURFACE = "visual-surface"
PROBES = (ALWAYS, VISUAL_SURFACE)

#: A visual implementation file by extension. This is the same surface saiui's
#: own charter scans by hand every cycle and reports as its evidence; it is
#: written down here so the answer is machine-decidable instead of re-derived
#: in prose each time.
VISUAL_SUFFIXES = frozenset(
    {
        ".html",
        ".htm",
        ".css",
        ".scss",
        ".sass",
        ".less",
        ".tsx",
        ".jsx",
        ".vue",
        ".svelte",
        ".qml",
        ".ui",
        ".xaml",
        ".storyboard",
        ".xib",
    }
)

#: A desktop-UI toolkit import. Extension alone misses a Tk or Qt application,
#: which is a `.py` file like any other, so the probe reads imports too.
GUI_IMPORT_RE = re.compile(
    rb"^[ \t]*(?:from|import)[ \t]+(tkinter|PyQt[456]|PySide[26]|textual|wx|kivy|gi)\b",
    re.MULTILINE,
)

#: Files the import probe opens. Anything else is judged by extension only.
_IMPORT_SUFFIXES = frozenset({".py", ".pyw"})

#: Never walked: runtime state, VCS internals, dependency forests and caches.
#: `.saipen/` is excluded for the same reason `PROTOCOL.md` section 6 excludes
#: it from the source fingerprint -- a worker's own kitchen is not the project,
#: and a producer's staged copy of a page must not make the project look like
#: it grew a UI.
EXCLUDED_DIRS = frozenset(
    {
        ".git",
        ".saipen",
        ".venv",
        "venv",
        "node_modules",
        "__pycache__",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        "dist",
        "build",
        ".freebuff",
        ".claude",
    }
)

#: A single file is read no further than this when probing imports. An import
#: line lives at the top; reading a 200 MB generated blob to find that out is a
#: cost the answer does not justify.
IMPORT_PROBE_BYTES = 64 * 1024


@dataclass(frozen=True)
class ProjectFacts:
    """Deterministic, cheap, read-only facts a capability can be judged against.

    Every field is derived from the project tree. Nothing here reads STATE,
    BOARD, a charter or an agent's claim: an applicability answer that could be
    changed by writing prose would be the same narrative-authority leak the
    protocol already names.

    `readable` is False when the tree could not be enumerated at all. It is kept
    as a field rather than signalled by an exception because "I could not look"
    is an answer callers must be able to carry into a verdict, and the verdict
    for it is APPLICABLE.
    """

    visual_paths: tuple[str, ...] = ()
    gui_module_paths: tuple[str, ...] = ()
    readable: bool = True
    unreadable_reason: str = ""
    #: Files enumerated. Zero on a readable but genuinely empty tree, which is
    #: why it is carried separately from `readable`.
    scanned: int = 0
    _evidence: tuple[str, ...] = field(default=(), compare=False, repr=False)

    @property
    def visual_surface(self) -> bool:
        """Does a visual implementation exist anywhere in the project?"""
        return bool(self.visual_paths or self.gui_module_paths)

    def visual_evidence(self, limit: int = 3) -> tuple[str, ...]:
        """A bounded sample of the paths that decided `visual_surface`.

        Bounded on purpose: a verdict reason is read by a human in a plan
        listing, and a reason that pastes four thousand paths is not evidence,
        it is a denial of service on the reader.
        """
        return tuple((*self.visual_paths, *self.gui_module_paths))[:limit]


def verdict(probe: str, facts: ProjectFacts | None) -> tuple[str, str]:
    """`(verdict, reason)` for one probe against one set of facts.

    The reason is never empty, including for `APPLICABLE`, because a plan that
    prints a bare verdict makes the two failure directions -- ran when it need
    not have, skipped when it must not have -- look the same from outside.
    """
    if facts is None:
        return APPLICABLE, "project facts unavailable; applicability fails closed to APPLICABLE"
    if not facts.readable:
        reason = facts.unreadable_reason or "project tree could not be enumerated"
        return APPLICABLE, f"{reason}; applicability fails closed to APPLICABLE"
    if probe == ALWAYS:
        return APPLICABLE, "role declares no applicability condition"
    if probe == VISUAL_SURFACE:
        if facts.visual_surface:
            sample = ", ".join(facts.visual_evidence())
            return APPLICABLE, f"visual surface present: {sample}"
        return (
            NOT_APPLICABLE,
            f"no visual implementation file in {facts.scanned} scanned project "
            f"files (extensions {_suffix_list()}; no desktop UI toolkit import)",
        )
    return (
        APPLICABLE,
        f"unknown applicability probe {probe!r}; applicability fails closed to APPLICABLE",
    )


def _suffix_list() -> str:
    return " ".join(sorted(VISUAL_SUFFIXES))


def is_applicable(probe: str, facts: ProjectFacts | None) -> bool:
    """Convenience predicate. Callers that report to a human want `verdict`."""
    return verdict(probe, facts)[0] == APPLICABLE


# ---------------------------------------------------------------------------
# THE ONLY IMPURE FUNCTION BELOW THIS LINE.
#
# Everything above is a function of its arguments and is tested without a
# filesystem. `collect_facts` walks a tree, so it is quarantined here and
# returns the same frozen `ProjectFacts` the pure half consumes.
# ---------------------------------------------------------------------------


def collect_facts(project_root) -> ProjectFacts:
    """Enumerate the project's visual surface, once, cheaply, read-only.

    Prefers Git's own idea of the project (`git ls-files`), because a tracked
    file is what the repository claims to own and it inherits `.gitignore` for
    free. Falls back to a bounded walk when Git cannot answer, and reports
    `readable=False` only when neither route produced a listing -- at which
    point every verdict is APPLICABLE, so an unreadable tree can never silently
    retire a capability.
    """
    import os
    import subprocess
    from pathlib import Path

    root = Path(project_root)
    paths: list[str] = []
    try:
        completed = subprocess.run(
            ["git", "-C", os.fspath(root), "ls-files", "-z", "--cached", "--others",
             "--exclude-standard"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if completed.returncode == 0:
            paths = [p for p in completed.stdout.decode("utf-8", "replace").split("\0") if p]
    except (OSError, ValueError):
        paths = []

    if not paths:
        try:
            for base, dirs, files in os.walk(root):
                dirs[:] = sorted(d for d in dirs if d not in EXCLUDED_DIRS)
                for name in sorted(files):
                    rel = (Path(base) / name).relative_to(root).as_posix()
                    paths.append(rel)
        except OSError as exc:
            return ProjectFacts(readable=False, unreadable_reason=f"tree walk failed: {exc}")

    visual: list[str] = []
    gui: list[str] = []
    for rel in paths:
        parts = rel.split("/")
        if any(part in EXCLUDED_DIRS for part in parts[:-1]):
            continue
        suffix = ("." + parts[-1].rsplit(".", 1)[1].lower()) if "." in parts[-1] else ""
        if suffix in VISUAL_SUFFIXES:
            visual.append(rel)
            continue
        if suffix in _IMPORT_SUFFIXES and _imports_gui_toolkit(root / rel):
            gui.append(rel)

    return ProjectFacts(
        visual_paths=tuple(visual),
        gui_module_paths=tuple(gui),
        readable=True,
        scanned=len(paths),
    )


def _imports_gui_toolkit(path) -> bool:
    """Does this module import a desktop UI toolkit?

    An unreadable file answers False rather than raising: one file the probe
    cannot open is not a reason to fail the whole enumeration, and the
    surrounding contract already fails closed at the level that matters -- an
    entire tree that cannot be listed reports `readable=False`.
    """
    try:
        with open(path, "rb") as handle:
            head = handle.read(IMPORT_PROBE_BYTES)
    except OSError:
        return False
    return GUI_IMPORT_RE.search(head) is not None
