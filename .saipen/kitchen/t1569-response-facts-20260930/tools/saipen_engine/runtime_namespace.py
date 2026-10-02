"""Machine-local runtime namespace policy (T-1435 M6 / SRC-090 section 16-19).

SAIPEN writes machine-local mechanics beside durable protocol history: OS
writer locks, liveness caches, per-operation journal scratch and rebuildable
snapshot generations. In the measured FastPrompter incident ~255 per-operation
recovery directories, two writer locks and a liveness cache were ELIGIBLE to
enter a public release cohort until that project added its own local
exclusions. A release-inventory guarantee that every consumer has to
rediscover is not a guarantee.

This module is the ONE owner of the classification:

  NON-RELEASE (machine-local mechanics; never source, never release input)
      .saipen/locks/**, .saipen/cache/**, .saipen/recovery/ops/**,
      .saipen/snapshots/**

  DURABLE (protocol/evidence history the contract requires to survive)
      .saipen/evidence/**, .saipen/archive/**, .saipen/intake/**,
      .saipen/recovery/log-detail/**, .saipen/recovery/board-compaction/**,
      .saipen/recovery/conformance/**, .saipen/recovery/settled/**,
      .saipen/recovery/log-normalize/**, .saipen/recovery/log-foreign-tail/**,
      .saipen/extensions/**, and the canonical checkpoint files themselves.

The policy is deliberately NOT `.saipen/**`: a blanket exclusion would drop
the durable half. `.gitignore` is also not a repair -- it does not untrack a
file Git already follows, so a tracked runtime path gets a finite,
OPERATOR_AUTHORIZED_COMMAND (`git rm -r --cached ...`) instead of an
instruction that keeps failing forever.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

#: (repo-relative prefix, class id) in declaration order. First match wins.
NON_RELEASE_PATTERNS: tuple[tuple[str, str], ...] = (
    (".saipen/locks/", "os-writer-lock"),
    (".saipen/cache/", "liveness-cache"),
    (".saipen/recovery/ops/", "operation-journal-scratch"),
    (".saipen/snapshots/", "rebuildable-snapshot"),
)

#: Durable history the policy must never classify as runtime debris.
DURABLE_PROTECTED: tuple[str, ...] = (
    ".saipen/evidence/",
    ".saipen/archive/",
    ".saipen/intake/",
    ".saipen/recovery/log-detail/",
    ".saipen/recovery/board-compaction/",
    ".saipen/recovery/conformance/",
    ".saipen/recovery/settled/",
    ".saipen/recovery/log-normalize/",
    ".saipen/recovery/log-foreign-tail/",
    ".saipen/extensions/",
)

#: The one marker the canonical ignore block carries; its presence means the
#: policy is established (idempotent application, never a duplicate block).
IGNORE_MARKER = "# SAIPEN runtime namespace (machine-local; never release source)"

#: The closed remediation classification for a tracked runtime artifact.
OPERATOR_AUTHORIZED_COMMAND = "OPERATOR_AUTHORIZED_COMMAND"


def _rel(path: str) -> str:
    rel = str(path or "").replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel


def runtime_class(path: str) -> str | None:
    """The non-release class of `path`, or None when it is not runtime debris."""
    rel = _rel(path)
    for prefix, class_id in NON_RELEASE_PATTERNS:
        if rel == prefix.rstrip("/") or rel.startswith(prefix):
            return class_id
    return None


def is_durable_protected(path: str) -> bool:
    rel = _rel(path)
    return any(rel.startswith(prefix) for prefix in DURABLE_PROTECTED)


def ignore_block() -> str:
    """The canonical `.gitignore` block, marker first, classes after."""
    lines = [
        IGNORE_MARKER + " -- T-1435.",
        "# Durable protocol/evidence history (.saipen/evidence, archive, intake,",
        "# recovery/log-detail, recovery/board-compaction, recovery/conformance,",
        "# recovery/log-normalize, recovery/log-foreign-tail, extensions) stays",
        "# versioned; only the mechanics below are excluded.",
    ]
    lines.extend(prefix for prefix, _class in NON_RELEASE_PATTERNS)
    return "\n".join(lines) + "\n"


def ignore_policy_state(project_root: Path | str) -> str:
    """CURRENT when the canonical block is present, ABSENT otherwise."""
    path = Path(project_root) / ".gitignore"
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError:
        return "ABSENT"
    return "CURRENT" if IGNORE_MARKER in text else "ABSENT"


def ensure_gitignore_policy(project_root: Path | str) -> dict:
    """Establish the canonical runtime-ignore policy on adoption (idempotent).

    A new project (or an adopted one with no policy) gets the block appended
    once; an existing block is never duplicated and never rewritten. This is a
    project-file policy, not canonical protocol state, so it is applied
    directly and its failure is reported rather than raised.
    """
    root = Path(project_root)
    state = ignore_policy_state(root)
    if state == "CURRENT":
        return {"ok": True, "code": "IGNORE_POLICY_CURRENT"}
    path = root / ".gitignore"
    try:
        if path.is_file():
            text = path.read_text(encoding="utf-8-sig")
            if text and not text.endswith("\n"):
                text += "\n"
            text += "\n" + ignore_block()
        else:
            text = ignore_block()
        path.write_text(text, encoding="utf-8", newline="\n")
    except OSError as exc:
        return {
            "ok": False,
            "code": "IGNORE_POLICY_UNAVAILABLE",
            "detail": f"cannot establish the runtime ignore policy: {exc}",
        }
    return {"ok": True, "code": "IGNORE_POLICY_ADDED"}


#: T-1508. Byte-bound evidence: every file under these paths is proven by a
#: sha256 of its exact bytes, so Git's line-ending conversion (core.autocrlf,
#: the Git for Windows default) turns honest evidence into a digest mismatch.
#: Measured 2026-09-24 in a managed project with no `.gitattributes`: four
#: `git stash -u` round-trips rewrote seven untracked archived sources with
#: CRLF while their digests were of the LF bytes, and attribution refused
#: them. `-text` is the only setting that keeps the bytes; `eol=lf` would
#: still rewrite a source that genuinely arrived with CRLF.
ATTRIBUTES_MARKER = "# SAIPEN byte-bound evidence (digest-verified; never convert line endings)"

#: (pattern, probe) in declaration order. The probe is a representative path
#: `git check-attr` answers for, so a rule the project already has -- another
#: spelling, a broader pattern, a global attributes file -- is recognized
#: instead of duplicated.
BYTE_BOUND_PATTERNS: tuple[tuple[str, str], ...] = (
    (".saipen/intake/**", ".saipen/intake/active/SRC-000.md"),
    (".saipen/archive/source/**", ".saipen/archive/source/SRC-000.md"),
    (".saipen/archive/retired/**", ".saipen/archive/retired/SRC-000.md"),
    (".saipen/recovery/log-detail/**", ".saipen/recovery/log-detail/E-0-probe.LOG.md"),
    (
        ".saipen/recovery/board-compaction/**",
        ".saipen/recovery/board-compaction/T-0/T-0-probe.json",
    ),
    # A ledger REWRITE keeps the LOG it replaced here; the repair's DEC names
    # the copy, and `quarantine-log-tail` records its sha256.
    (".saipen/recovery/log-normalize/**", ".saipen/recovery/log-normalize/op/LOG.md"),
    (".saipen/recovery/log-foreign-tail/**", ".saipen/recovery/log-foreign-tail/op/LOG.md"),
)


def attributes_block(patterns=None) -> str:
    """The canonical `.gitattributes` block, marker first, rules after."""
    selected = [p for p, _probe in BYTE_BOUND_PATTERNS] if patterns is None else list(patterns)
    lines = [ATTRIBUTES_MARKER + " -- T-1508."]
    lines.extend(f"{pattern} -text" for pattern in selected)
    return "\n".join(lines) + "\n"


def _declared_unset(text: str) -> set[str]:
    """Patterns whose LAST rule in `text` unsets `text` (`-text` or `binary`)."""
    state: dict[str, bool] = {}
    for line in text.splitlines():
        fields = line.split()
        if len(fields) < 2 or fields[0].startswith("#"):
            continue
        for attribute in fields[1:]:
            if attribute in ("-text", "binary"):
                state[fields[0]] = True
            elif attribute == "text" or attribute.startswith(("text=", "!text")):
                state[fields[0]] = False
    return {pattern for pattern, unset in state.items() if unset}


def _git_unset(root: Path, probes: list[str]) -> set[str] | None:
    """Probes Git resolves to `text: unset`; None when Git cannot answer."""
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "check-attr", "text", "--", *probes],
            capture_output=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    unset = set()
    for line in proc.stdout.decode("utf-8", errors="replace").splitlines():
        path, _sep, value = line.rpartition(": text: ")
        if value.strip() == "unset":
            unset.add(path)
    return unset


def attributes_policy(project_root: Path | str) -> dict:
    """``{"state": CURRENT|PARTIAL|ABSENT, "missing": [pattern, ...]}``.

    The project's own `.gitattributes` answers first (no subprocess when it
    already carries every rule); whatever it does not declare is asked of
    Git, which knows every attributes source. Without Git the file alone
    decides, so a gitless project is judged by what it would carry into one.
    """
    root = Path(project_root)
    try:
        text = (root / ".gitattributes").read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        text = ""
    declared = _declared_unset(text)
    missing = [(p, probe) for p, probe in BYTE_BOUND_PATTERNS if p not in declared]
    if missing:
        answered = _git_unset(root, [probe for _p, probe in missing])
        if answered is not None:
            missing = [(p, probe) for p, probe in missing if probe not in answered]
    patterns = [p for p, _probe in missing]
    if not patterns:
        state = "CURRENT"
    elif len(patterns) == len(BYTE_BOUND_PATTERNS):
        state = "ABSENT"
    else:
        state = "PARTIAL"
    return {"state": state, "missing": patterns}


def attributes_policy_state(project_root: Path | str) -> str:
    """CURRENT when every byte-bound path is `-text`, else PARTIAL/ABSENT."""
    return attributes_policy(project_root)["state"]


def ensure_gitattributes_policy(project_root: Path | str) -> dict:
    """Mark byte-bound evidence `-text` wherever it is not already (idempotent).

    Only the missing rules are written, APPENDED to the existing file: its
    bytes, BOM and line-ending style are never rewritten, and a rule the
    project already carries in any spelling is never duplicated. Failure is
    reported rather than raised, as for `ensure_gitignore_policy`.
    """
    root = Path(project_root)
    policy = attributes_policy(root)
    if policy["state"] == "CURRENT":
        return {"ok": True, "code": "ATTRIBUTES_POLICY_CURRENT"}
    path = root / ".gitattributes"
    try:
        existing = path.read_bytes() if path.is_file() else b""
        newline = b"\r\n" if b"\r\n" in existing else b"\n"
        prefix = b""
        if existing:
            prefix = (b"" if existing.endswith(b"\n") else newline) + newline
        block = attributes_block(policy["missing"]).encode("utf-8").replace(b"\n", newline)
        with path.open("ab") as handle:
            handle.write(prefix + block)
    except OSError as exc:
        return {
            "ok": False,
            "code": "ATTRIBUTES_POLICY_UNAVAILABLE",
            "detail": f"cannot establish the byte-bound attributes policy: {exc}",
        }
    return {"ok": True, "code": "ATTRIBUTES_POLICY_ADDED", "added": policy["missing"]}


def tracked_runtime_paths(project_root: Path | str) -> dict:
    """Runtime artifacts Git ALREADY follows in this project.

    Returns ``{"ok": True, "paths": [...]}`` or ``{"ok": False, "code":
    "GIT_UNAVAILABLE"}`` when Git cannot answer (a gitless export must never
    turn this check into a crash). `.gitignore` cannot hide these: Git
    tracking beats ignore status, which is exactly why the remediation is a
    `git rm --cached`, not another ignore line.
    """
    root = Path(project_root)
    directories = sorted({prefix for prefix, _class in NON_RELEASE_PATTERNS})
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", *directories],
            capture_output=True,
            timeout=120,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return {"ok": False, "code": "GIT_UNAVAILABLE", "detail": str(exc)}
    if proc.returncode != 0:
        return {
            "ok": False,
            "code": "GIT_UNAVAILABLE",
            "detail": proc.stderr.decode("utf-8", errors="replace").strip()[:240],
        }
    paths = [
        part.replace("\\", "/")
        for part in proc.stdout.decode("utf-8", errors="replace").split("\0")
        if part and runtime_class(part)
    ]
    return {"ok": True, "paths": sorted(set(paths))}


def remediation_command(paths) -> str:
    """The exact authorized maintenance command for tracked runtime paths.

    SAIPEN does not mutate the Git index; the operator runs this. It removes
    the paths from tracking WITHOUT deleting the live runtime state on disk
    (`--cached`), so the protocol can recreate them normally.
    """
    quoted = " ".join(shlex.quote(str(path)) for path in paths)
    return f"git rm -r --cached -- {quoted}".strip()


def release_problems(project_root: Path | str) -> dict:
    """The one verdict a release/validator consumer reads.

    ``{"ok": True, "code": "RUNTIME_NAMESPACE_CLEAN"}`` or a structured
    problem carrying the tracked identities, their classes and the exact
    OPERATOR_AUTHORIZED_COMMAND remediation.
    """
    tracked = tracked_runtime_paths(project_root)
    if not tracked.get("ok"):
        return {"ok": True, "code": "RUNTIME_NAMESPACE_UNPROVEN", "detail": tracked.get("detail")}
    paths = tracked.get("paths") or []
    if not paths:
        return {"ok": True, "code": "RUNTIME_NAMESPACE_CLEAN"}
    classes = {path: runtime_class(path) for path in paths}
    return {
        "ok": False,
        "code": "RUNTIME_NAMESPACE_TRACKED",
        "paths": paths,
        "classes": classes,
        "remediation_kind": OPERATOR_AUTHORIZED_COMMAND,
        "remediation_command": remediation_command(paths),
        "detail": (
            "machine-local SAIPEN runtime artifacts are tracked by Git and would "
            "enter the release cohort; `.gitignore` cannot untrack them"
        ),
    }