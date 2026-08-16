"""Canonical Core convergence verdict (T-1003 Wave 2, items 1/14).

CONVERGE.md owns the E-I sequence (E canonical test gate, F forced HUNT,
G CLEAN, H post-clean test gate, I final forced HUNT). This module owns ONLY
the mechanical proof that those requirements are CURRENT against one source
identity -- the crew planner/gate (SC-7), the terminal ship gate and the
convergence mini-circuit all consume this ONE verdict, and crew.py never
re-implements the sequence.

The verdict is a terminal ordered chain of COMMITTED `convergence_stage`
operation receipts. Every receipt binds the LIVE source identity
(source_head + source_tree_fingerprint) at its execution time; G (CLEAN)
additionally binds the resulting identity after its mutation. The chain is
current iff:

- E and F bind one identity S0;
- G's input is S0 and G's resulting identity is the S1 that H and I bind;
- the CURRENT live source identity equals S1 -- no main-source mutation after
  the final forced HUNT;
- every stage verdict is the closed outcome CONVERGE.md defines for it;
- the working tree is fully attributed: every main-source delta (when a Git
  baseline exists) is claimed by an owner record with matching bytes, and no
  recorded claim is stale.

Receipts may be re-recorded (the F -> E loop CONVERGE.md defines when HUNT
finds work); only the terminal chain walking backwards from the latest I
counts. Earlier aborted attempts stay historical evidence and never certify
the current fixed point.

DONE STATE IS NOT CONVERGENCE PROOF. phase DONE + task none + an empty
workable board proves nothing about E-I; a project can sit at DONE with stale
or missing tests/HUNT/CLEAN evidence. This verdict is what SC-7 requires
instead of an empty-board inference.
"""

from __future__ import annotations

import datetime
import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

# The closed stage set CONVERGE.md defines. The letters are the document's own
# section labels, so a receipt can name the stage without restating prose.
CONVERGENCE_STAGES = ("E", "F", "G", "H", "I")

# Closed per-stage outcomes. Anything else is not a verdict, it is prose.
STAGE_VERDICTS = {
    "E": ("PASS",),                                  # canonical test gate PASS
    "F": ("CLEAN",),                                 # forced HUNT, no findings
    "G": ("COMPLETED", "NOTHING_SAFE_REMAINED"),     # CLEAN outcome
    "H": ("PASS",),                                  # post-clean test gate PASS
    "I": ("CLEAN",),                                 # final forced HUNT clean
}

STAGE_NAMES = {
    "E": "canonical test/validate gate",
    "F": "forced HUNT",
    "G": "CLEAN",
    "H": "post-clean test/validate gate",
    "I": "final forced HUNT",
}


@dataclass(frozen=True)
class ConvergenceVerdict:
    ok: bool
    reasons: tuple[str, ...]
    stages: tuple[dict, ...] = ()
    source: dict | None = None
    attribution_problems: tuple[str, ...] = ()

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "reasons": list(self.reasons),
            "stages": [{
                "stage": item.get("stage", ""),
                "verdict": (item.get("receipt_metadata") or {}).get(
                    "verdict", ""),
                "op_id": item.get("op_id", ""),
                "created_at": item.get("created_at", ""),
            } for item in self.stages],
            "source": self.source,
            "attribution_problems": list(self.attribution_problems),
        }


def _strict_created_at(value: object) -> str:
    """Strict ISO-8601 UTC timestamp (Z or +00:00), or '' when invalid.

    A timestamp that cannot parse structurally is NO evidence: a receipt
    claiming a time is meaningless when the time itself does not parse.
    """
    if not isinstance(value, str):
        return ""
    value = value.strip()
    try:
        stamp = datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if stamp.tzinfo is None:
        return ""
    return value


def _iter_operation_records(root: Path):
    """Yield every parseable operation.json under .saipen/recovery/ops."""
    ops = root / ".saipen" / "recovery" / "ops"
    if not ops.is_dir():
        return
    for op_dir in sorted(ops.iterdir()):
        manifest = op_dir / "operation.json"
        if not manifest.is_file():
            continue
        try:
            record = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        yield record


def _event_number(record: dict) -> int:
    """The monotonic LOG event id a receipt committed under. Ops recorded in
    the same wall-clock second must still order deterministically; the LOG
    event counter is the engine's own monotonic sequence."""
    meta = record.get("receipt_metadata") or {}
    match = re.match(r"E-(\d+)", str(meta.get("event_id") or ""))
    return int(match.group(1)) if match else -1


def _stage_receipts(root: Path) -> list[dict]:
    """Every COMMITTED convergence_stage receipt, oldest event first."""
    out = []
    for record in _iter_operation_records(root):
        if record.get("operation") != "convergence_stage":
            continue
        if record.get("status") != "COMMITTED":
            continue
        created = _strict_created_at(record.get("created_at"))
        if not created:
            continue
        meta = record.get("receipt_metadata") or {}
        if meta.get("operation") != "convergence_stage" \
                or meta.get("status") != "COMMITTED":
            continue
        if _event_number(record) < 0:
            continue
        out.append(record)
    out.sort(key=lambda item: (_event_number(item), item.get("op_id", "")))
    return out


def _pick_latest(receipts: list[dict], wanted_stage: str, before_event: int,
                 reasons: list[str]) -> dict | None:
    """The latest receipt of `wanted_stage` committed strictly before
    `before_event`, or None. Receipts recorded in the same wall-clock second
    still order by their monotonic LOG event, never by timestamp ties."""
    candidates = [item for item in receipts
                  if (item.get("receipt_metadata") or {}).get("stage")
                  == wanted_stage and _event_number(item) < before_event]
    if not candidates:
        reasons.append(f"missing convergence stage {wanted_stage} "
                       f"({STAGE_NAMES[wanted_stage]}) before event "
                       f"E-{before_event}")
        return None
    return max(candidates, key=_event_number)


def _identity_of(record: dict) -> tuple[str, str] | None:
    """The INPUT source identity a stage receipt binds.

    Hostile-regression: the input side is `source_head` +
    `source_tree_fingerprint`, and BOTH must be present. The resulting side
    (`resulting_source_head` / `resulting_source_tree_fingerprint`, carried
    by CLEAN) is NEVER a fallback here -- a receipt that lost its input
    side is a broken chain link, not evidence with a second chance. The
    caller reads CLEAN's resulting side explicitly and only for stage G.
    """
    meta = record.get("receipt_metadata") or {}
    head = meta.get("source_head")
    tree = meta.get("source_tree_fingerprint")
    if not head or not tree:
        return None
    return head, tree


def _attribution_claims(root: Path) -> dict[str, str | None]:
    """Owner claims over main-source paths, from the release-scope records
    and committed crew-defer receipts (item 14: reuse existing
    attribution/release-scope machinery, never git status inference).

    A claim is {rel: expected content hash} or {rel: None} for a reviewed
    deletion. The LATEST owning record wins per path.
    """
    claims: dict[str, str | None] = {}
    scope_dir = root / ".saipen" / "kitchen" / "release_scope"
    if scope_dir.is_dir():
        for scope in sorted(scope_dir.glob("T-*.json")):
            try:
                record = json.loads(scope.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for rel, expected in (record.get("paths") or {}).items():
                claims[rel] = expected
    for record in _iter_operation_records(root):
        meta = record.get("receipt_metadata") or {}
        if record.get("operation") != "crew_defer" \
                or record.get("status") != "COMMITTED":
            continue
        for rel, expected in (meta.get("paths") or {}).items():
            claims[rel] = expected
    return claims


def source_worktree_deltas(root: Path) -> list[str] | None:
    """ONE Git subprocess: deterministic main-source delta paths vs HEAD.

    Tri-state result: None when no usable Git baseline exists (UNKNOWN),
    [] when the source worktree equals HEAD, otherwise the sorted
    changed-path list covering staged + unstaged + untracked changes.
    The exact `.saipen` runtime boundary is excluded via a single
    pathspec, so `.saipenicious.py` / `.saipen-src/*` remain ordinary
    source. Rename/copy entries contribute their SOURCE path, matching
    the historical `git diff --name-status` identity semantics.
    """
    try:
        status = subprocess.run(
            ["git", "-C", os.fspath(root), "status", "--porcelain=v1",
             "-z", "--untracked-files=all", "--", ".",
             ":(exclude).saipen"],
            capture_output=True, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    if status.returncode != 0:
        return None
    paths: list[str] = []
    fields = status.stdout.decode("utf-8", "replace").split("\0")
    index = 0
    while index < len(fields) and fields[index]:
        record = fields[index]
        if len(record) < 3 or record[2] != " ":
            # Malformed porcelain record -- refuse instead of guessing.
            return None
        xy, path = record[:2], record[3:]
        index += 1
        if xy[0] == "R":
            if index >= len(fields) or not fields[index]:
                return None
            paths.append(path)
            paths.append(fields[index])
            index += 1
        elif xy[0] == "C":
            if index >= len(fields) or not fields[index]:
                return None
            paths.append(path)
            index += 1
        elif path:
            paths.append(path)
    return sorted(set(paths))


def _main_source_deltas(root: Path) -> list[str] | None:
    """Tracked/untracked main-source delta paths vs HEAD, excluding the
    exact `.saipen/` runtime boundary. None when no Git baseline exists.

    Thin projection over the single shared source-worktree probe so the
    historical name keeps working for attribution checks.
    """
    return source_worktree_deltas(root)


def attribution_problems(root: Path) -> list[str]:
    """Attribution problems for the current tree (item 14).

    Every main-source delta (Git baseline present) must be claimed by an
    owner record whose expected bytes still match; a foreign/unknown delta
    is a visible problem, never silently claimed. Without a Git baseline no
    delta enumeration exists, so a project that recorded NO claims cannot
    prove "fully attributed" -- vacuous green is exactly what this check
    exists to refuse.
    """
    problems: list[str] = []
    claims = _attribution_claims(root)
    deltas = _main_source_deltas(root)
    if deltas is not None:
        for rel in deltas:
            expected = claims.get(rel)
            if expected is None:
                if rel in claims:
                    problems.append(
                        f"main-source delta {rel} is a reviewed deletion but "
                        "exists again -- stale attribution, refuse")
                else:
                    problems.append(
                        f"unattributed main-source delta: {rel} -- every "
                        "change must belong to a reviewed scope")
                continue
            fp = root / rel
            if not fp.is_file():
                problems.append(
                    f"attributed path {rel} is missing -- reviewed scope "
                    "stale, refuse")
                continue
            live = _quick_hash(fp.read_bytes())
            if live != expected:
                problems.append(
                    f"attributed path {rel} changed after its reviewed "
                    f"scope (expected {expected}, live {live}) -- stale, "
                    "re-review before claiming a fixed point")
        return problems
    if not claims:
        problems.append(
            "no attribution claims recorded and no Git baseline exists -- "
            "a no-git tree cannot prove 'fully attributed' from an empty "
            "board alone")
        return problems
    for rel, expected in claims.items():
        fp = root / rel
        if expected is None:
            if fp.exists() or fp.is_symlink():
                problems.append(
                    f"reviewed deletion {rel} exists again -- stale "
                    "attribution, refuse")
            continue
        if not fp.is_file():
            problems.append(f"attributed path {rel} is missing -- stale")
            continue
        if _quick_hash(fp.read_bytes()) != expected:
            problems.append(
                f"attributed path {rel} changed after its reviewed scope -- "
                "stale, refuse")
    return problems


def _quick_hash(raw: bytes) -> str:
    # Scope/defer records store the journal's hash_bytes token (16 hex chars);
    # attribution must compare the SAME token or every claim looks stale.
    import hashlib
    return hashlib.sha256(raw).hexdigest()[:16]


def convergence_verdict(project_root: Path | str,
                        source_id=None) -> ConvergenceVerdict:
    """The ONE mechanical Core convergence verdict (items 1/14).

    Returns ok=False with reasons whenever any of E-I evidence is missing,
    out of order, bound to a different source identity, followed by a later
    main-source mutation, or when the tree is not fully attributed. The
    caller binds the CURRENT source identity: pass `source_id` (as computed
    inside the same coherent snapshot) to avoid a second read.
    """
    root = Path(project_root)
    reasons: list[str] = []
    if source_id is None:
        try:
            from freshness import compute_source_identity
            source_id = compute_source_identity(root)
        except Exception as exc:
            return ConvergenceVerdict(False, (
                "source identity UNKNOWN: " + str(exc),), source={
                    "error": str(exc)})
    live = (source_id.source_head, source_id.source_tree_fingerprint)

    receipts = _stage_receipts(root)
    if not receipts:
        return ConvergenceVerdict(
            False, ("no canonical convergence stage evidence -- E-I "
                    "(test/HUNT/CLEAN/post-clean test/final HUNT) must be "
                    "recorded against the current source identity; DONE + "
                    "empty board is not convergence proof",),
            source={"source_head": live[0],
                    "source_tree_fingerprint": live[1]})

    # The terminal chain: walk backwards from the latest I.
    i_receipts = [item for item in receipts
                  if (item.get("receipt_metadata") or {}).get("stage") == "I"]
    if not i_receipts:
        reasons.append("missing final forced HUNT (I) -- the closure sweep "
                       "must run after CLEAN and post-clean tests")
        return ConvergenceVerdict(False, tuple(reasons), source={
            "source_head": live[0], "source_tree_fingerprint": live[1]})
    latest_i = i_receipts[-1]
    i_event = _event_number(latest_i)
    i_identity = _identity_of(latest_i)
    if i_identity is None:
        reasons.append("final forced HUNT receipt lacks a bound source "
                       "identity")
        return ConvergenceVerdict(False, tuple(reasons), source={
            "source_head": live[0], "source_tree_fingerprint": live[1]})
    if i_identity != live:
        reasons.append(
            "final forced HUNT binds source "
            f"{i_identity[0][:12]}/{i_identity[1][:16]} but the CURRENT "
            f"source is {live[0][:12]}/{live[1][:16]} -- a main-source "
            "mutation after the final HUNT invalidates the fixed point")
        return ConvergenceVerdict(False, tuple(reasons), source={
            "source_head": live[0], "source_tree_fingerprint": live[1]})

    h = _pick_latest(receipts, "H", i_event, reasons)
    g = _pick_latest(receipts, "G", _event_number(h) if h else i_event,
                     reasons)
    f = _pick_latest(receipts, "F", _event_number(g) if g else i_event,
                     reasons)
    e = _pick_latest(receipts, "E", _event_number(f) if f else i_event,
                     reasons)
    if None in (e, f, g, h):
        return ConvergenceVerdict(False, tuple(reasons), source={
            "source_head": live[0], "source_tree_fingerprint": live[1]})

    chain = [e, f, g, h, latest_i]
    ef = _identity_of(e)
    gh = _identity_of(g)
    hi = _identity_of(h)
    if ef is None or gh is None or hi is None:
        reasons.append("convergence stage receipt lacks a bound source "
                       "identity")
        return ConvergenceVerdict(False, tuple(reasons), source={
            "source_head": live[0], "source_tree_fingerprint": live[1]})
    s0 = ef
    s1 = hi
    if f is not None and _identity_of(f) != s0:
        reasons.append(
            "forced HUNT binds a different source identity than the "
            "canonical test gate -- a main-source mutation between E and F "
            "breaks the chain")
    if gh[0] != s0[0] or gh[1] != s0[1]:
        reasons.append(
            "CLEAN input identity differs from the E/F identity -- CLEAN "
            "must run on the source the test gate and forced HUNT proved")
    g_result = ((g.get("receipt_metadata") or {}).get(
        "resulting_source_head", ""),
        (g.get("receipt_metadata") or {}).get(
            "resulting_source_tree_fingerprint", ""))
    if not g_result[0] or not g_result[1]:
        reasons.append("CLEAN receipt lacks its resulting source identity")
    elif g_result != s1:
        reasons.append(
            "CLEAN resulting identity differs from the H/I identity -- "
            "post-clean evidence must bind the post-CLEAN tree")
    if _identity_of(h) != s1:
        reasons.append(
            "post-clean test gate binds a different source identity than "
            "the final forced HUNT -- a mutation between H and I breaks the "
            "chain")

    for record in chain:
        meta = record.get("receipt_metadata") or {}
        stage = meta.get("stage")
        verdict = meta.get("verdict")
        allowed = STAGE_VERDICTS.get(stage, ())
        if verdict not in allowed:
            reasons.append(
                f"stage {stage} verdict {verdict!r} is not a closed "
                f"{STAGE_NAMES.get(stage, stage)} outcome ({', '.join(allowed)})")

    attribution = tuple(attribution_problems(root))
    if attribution:
        reasons.extend(attribution)

    return ConvergenceVerdict(
        not reasons, tuple(reasons), tuple(chain),
        source={"source_head": live[0],
                "source_tree_fingerprint": live[1]},
        attribution_problems=attribution)
