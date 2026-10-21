"""External implementation resolution authority (SRC-088 / T-1434 M2).

A defect can be reported locally, implemented in an UPSTREAM authority (the
protocol home, a shared engine, a released dependency), and verified locally
against the INSTALLED implementation. Before this module the only closure
provenance was local patch ownership, so such a ticket stayed BLOCKED_EXTERNAL
forever or had to lie with `own_patch`.

This module owns the ONE external closure mode (``external_implementation``,
the protocol's LOCAL_IMPLEMENTATION vs
EXTERNAL_IMPLEMENTATION_LOCAL_VERIFICATION distinction): the receipt format,
the closed authority/implementation grammar, and the re-derivation every
consumer shares -- the closure resolver and the validator both call
:func:`resolution_problems`, so they cannot drift.

Nothing here trusts prose. An authority must be a portable project lineage
identity, an implementation must be ``<T-###>@<commit>`` whose commit ancestry
is proven in the external project's OWN git history (a DONE row and a matching
lineage alone are never sufficient), and an executable check is authenticated
only by the sealed regression-execution contract: argv-bound, executable-proven
and hash-bound by :func:`regression_execution._runtime`. Command prefixes and
blacklists are not trust; BOARD prose never executes. The resolution is valid
only while the running ENGINE GENERATION it was verified against is still the
one installed: a dependency rollback (or any installed-code move) makes an
external closure non-green instead of silently green. Re-resolution is the
lawful repair, and it writes a NEW append-only receipt -- no historical bytes
are rewritten.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

EXTERNAL_SCHEMA_VERSION = 1
EXTERNAL_DIR = ".saipen/recovery/conformance/external"
EXTERNAL_ID_RE = re.compile(r"\AEX-(\d{6})\Z")

#: The closure_mode written on the resolved DONE row.
CLOSURE_MODE = "external_implementation"

#: Closed resolution-reason vocabulary. Free text is never provenance.
RESOLUTION_REASONS = (
    "PROTOCOL_HOME_FIX_VERIFIED",
    "DEPENDENCY_UPGRADE_VERIFIED",
    "UPSTREAM_FIX_VERIFIED",
)

_AUTHORITY_RE = re.compile(r"\Alineage-[0-9a-f]{32}\Z")
_IMPLEMENTATION_RE = re.compile(r"\A(T-\d+)@([0-9a-f]{7,40})\Z")

#: Board-level operator/hardware authority gates an external implementation
#: may never lift: these rows carry a decision only the operator can make.
OPERATOR_GATE_TOKENS = (
    "wait_user_decision",
    "wait_user_confirmation",
    "deferred_by_operator",
)


class ExternalRefusal(Exception):
    """A structured external-resolution refusal (code + bounded detail)."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def external_dir(root: Path | str) -> Path:
    return Path(root) / EXTERNAL_DIR


def existing_receipts(root: Path | str) -> list[Path]:
    directory = external_dir(root)
    if not directory.is_dir():
        return []
    return [
        path
        for path in sorted(directory.glob("EX-*.json"))
        if path.is_file() and EXTERNAL_ID_RE.match(path.stem)
    ]


def next_receipt_id(root: Path | str) -> str:
    numbers = [int(EXTERNAL_ID_RE.match(path.stem).group(1)) for path in existing_receipts(root)]
    return f"EX-{(max(numbers) + 1) if numbers else 1:06d}"


def authority_error(authority: str | None) -> str | None:
    """Why this external authority identity is not admissible, or None."""
    value = str(authority or "").strip()
    if not value:
        return (
            "external implementation authority is required (--authority): the "
            "portable lineage identity of the project that implemented the fix, "
            "e.g. lineage-<32 hex chars>"
        )
    if not _AUTHORITY_RE.match(value):
        return (
            f"authority {value!r} is not a portable lineage identity "
            "(lineage-<32 hex chars>); a URL, a path or a prose name is not "
            "an authority that can be checked"
        )
    return None


def implementation_error(implementation: str | None) -> str | None:
    """Why this upstream implementation identity is not admissible, or None."""
    value = str(implementation or "").strip()
    if not value:
        return (
            "external implementation identity is required (--implementation): "
            "the upstream Work and the exact commit that carries the fix, "
            "e.g. T-1411@cc86601f"
        )
    if not _IMPLEMENTATION_RE.match(value):
        return (
            f"implementation {value!r} is not a structured <T-###>@<commit> "
            "identity; free text or a URL cannot prove an upstream change"
        )
    return None


def reason_error(reason: str | None) -> str | None:
    value = str(reason or "").strip()
    if value not in RESOLUTION_REASONS:
        return f"resolution reason {reason!r} is outside {'|'.join(RESOLUTION_REASONS)}"
    return None


def contract_digest(work: str, verify_text: str) -> str:
    """Identity of the LOCAL defect contract this resolution answers.

    The local ticket's own verify clause is the contract; hashing it means a
    resolution recorded for T-73 can never be replayed against T-66's contract
    without the digests disagreeing.
    """
    material = f"{str(work).strip()}\0{str(verify_text).strip()}"
    return "sha256:" + hashlib.sha256(material.encode("utf-8")).hexdigest()


def _hash_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def engine_identity() -> dict:
    """The identity of the engine generation CURRENTLY executing.

    The digest covers every engine source this resolution depends on, so an
    installed generation move, a rollback to an older install, or a different
    engine copy answering the re-check all produce a different identity. The
    receipt binds it; the closure resolver and the validator recompute it, so
    an external closure is green only against the generation it verified.
    """
    package = Path(__file__).resolve().parent
    tools = package.parent
    files: list[Path] = sorted(
        [path for path in package.glob("*.py") if path.is_file()]
        + [path for path in (tools / "saipen.py", tools / "validate.py") if path.is_file()]
    )
    material = ""
    for path in files:
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            digest = "unreadable"
        material += f"{path.name}:{digest}\n"
    version = ""
    version_file = tools.parent / "VERSION"
    if version_file.is_file():
        try:
            version = version_file.read_text(encoding="utf-8-sig").strip()
        except OSError:
            version = ""
    return {
        "kind": "saipen-engine",
        "version": version,
        "engine_digest": _hash_bytes(material.encode("utf-8")),
        "files": len(files),
    }


def load_receipt(root: Path | str, receipt_id: str) -> dict:
    """Read ONE external receipt, fail-closed on any identity problem."""
    rid = str(receipt_id or "").strip()
    if not EXTERNAL_ID_RE.match(rid):
        raise ExternalRefusal(
            "EXTERNAL_RECEIPT_MISSING", f"{receipt_id!r} is not an EX-###### identity"
        )
    path = external_dir(root) / f"{rid}.json"
    if not path.is_file():
        raise ExternalRefusal(
            "EXTERNAL_RECEIPT_MISSING", f"{rid} does not exist at {EXTERNAL_DIR}/"
        )
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExternalRefusal("EXTERNAL_RECEIPT_CORRUPT", f"{rid} unreadable: {exc}") from exc
    if not isinstance(record, dict) or record.get("schema_version") != EXTERNAL_SCHEMA_VERSION:
        raise ExternalRefusal("EXTERNAL_RECEIPT_CORRUPT", f"{rid} has an unsupported schema")
    if record.get("receipt_id") != rid:
        raise ExternalRefusal("EXTERNAL_RECEIPT_CORRUPT", f"{rid} names a different receipt id")
    recorded = str(record.get("integrity_digest") or "")
    if not recorded:
        raise ExternalRefusal("EXTERNAL_RECEIPT_CORRUPT", f"{rid} carries no integrity digest")
    canonical = {key: value for key, value in record.items() if key != "integrity_digest"}
    raw = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if _hash_bytes(raw) != recorded:
        raise ExternalRefusal("EXTERNAL_RECEIPT_CORRUPT", f"{rid} integrity digest mismatch")
    return record


def build_receipt(
    *,
    root: Path | str,
    receipt_id: str,
    work: str,
    project_identity: str,
    project_lineage: str,
    agent: str,
    created_at: str,
    authority: str,
    implementation: str,
    resolution_reason: str,
    defect_contract_digest: str,
    defect_contract_text: str,
    prior_blocker_sha256: str,
    verification: list[dict],
    verification_contract_digest: str,
    verdict: str,
    op_id: str = "",
    predecessor: dict | None = None,
    external_snapshot: dict | None = None,
) -> dict:
    """The immutable receipt record, integrity-sealed before return."""
    record = {
        "schema_version": EXTERNAL_SCHEMA_VERSION,
        "receipt_id": receipt_id,
        "work": work,
        "project_identity": project_identity,
        "project_lineage": project_lineage,
        "created_at": created_at,
        "agent": agent,
        "external_authority": authority,
        "external_implementation": implementation,
        "resolution_reason": resolution_reason,
        "defect_contract_digest": defect_contract_digest,
        "defect_contract_text": defect_contract_text,
        "prior_blocker_sha256": prior_blocker_sha256,
        "verification": verification,
        "verification_contract_digest": verification_contract_digest,
        "verdict": verdict,
        "installed_identity": engine_identity(),
        "journal_op_id": op_id,
    }
    if predecessor is not None:
        record["predecessor"] = predecessor
    if external_snapshot is not None:
        record["external_snapshot"] = external_snapshot
    canonical = json.dumps(record, sort_keys=True, separators=(",", ":")).encode("utf-8")
    record["integrity_digest"] = _hash_bytes(canonical)
    return record


def resolution_problems(root: Path | str, work: str, ticket: dict) -> list[str]:
    """Why this DONE external closure is NOT current, or [] when it is.

    Both the closure resolver and the validator call THIS, so "resolves" and
    "validates" are one predicate. A missing receipt, a foreign project, a
    tampered record, a non-PASS verdict, a board/receipt disagreement and a
    moved (rolled back or upgraded) installed engine generation are all
    distinct, named problems.
    """
    from .board import (
        external_evidence as _evidence,
    )

    root = Path(root)
    problems: list[str] = []
    receipt_id = _evidence(ticket)
    if not receipt_id:
        return [f"{work} closes external_implementation with no | external_evidence: EX-######"]
    try:
        record = load_receipt(root, receipt_id)
    except ExternalRefusal as exc:
        return [f"{work}: {exc.detail}"]
    if record.get("work") != work:
        problems.append(f"{work} cites {receipt_id}, which resolves {record.get('work')!r}")
    problems.extend(receipt_binding_problems(root, work, ticket, record))
    current = engine_identity()
    installed = record.get("installed_identity") or {}
    if installed.get("engine_digest") != current.get("engine_digest"):
        problems.append(
            f"{receipt_id} was verified against installed engine generation "
            f"{(installed.get('engine_digest') or 'unknown')[:23]}... but the "
            f"running engine is {(current.get('engine_digest') or 'unknown')[:23]}... "
            "-- the dependency moved (rollback or upgrade): re-resolve truthfully "
            "instead of inheriting a stale green"
        )
    if "external_snapshot" in record:
        from .external_renewal import proof_problem, snapshot_problem

        problem = proof_problem(root, record) or snapshot_problem(root, record["external_snapshot"])
        if problem:
            problems.append(problem)
        for entry in record.get("verification", []):
            _plan, problem = receipt_plan(entry, root=root)
            if problem:
                problems.append(problem)
    return problems


def receipt_binding_problems(root, work, ticket, record):
    """Static receipt/Work identity, independently of legitimately moved inputs."""
    from .board import external_authority as _authority
    from .board import external_implementation as _implementation
    from .board import resolution_reason as _reason
    from .paths import history_bound_here, project_lineage_identity

    problems = []
    receipt_id = record["receipt_id"]
    if record.get("work") != work:
        problems.append(f"{receipt_id} belongs to another Work")

    # T-1516: the lineage owns the receipt; the path binds a lineage-less project only.
    if record.get("project_lineage") != project_lineage_identity(root):
        problems.append(f"{receipt_id} was written for a different project lineage")
    elif not history_bound_here(
        record.get("project_identity"), record.get("project_lineage"), root
    ):
        problems.append(f"{receipt_id} was written for a different project identity")
    if record.get("verdict") != "PASS":
        problems.append(
            f"{receipt_id} verdict is {record.get('verdict')!r}; only a PASS "
            "external verification is closure evidence"
        )
    board_authority = _authority(ticket)
    board_implementation = _implementation(ticket)
    if board_authority and board_authority != record.get("external_authority"):
        problems.append(
            f"{work} names authority {board_authority} but {receipt_id} records "
            f"{record.get('external_authority')}"
        )
    if board_implementation and board_implementation != record.get("external_implementation"):
        problems.append(
            f"{work} names implementation {board_implementation} but {receipt_id} "
            f"records {record.get('external_implementation')}"
        )
    board_reason = _reason(ticket)
    if board_reason and board_reason != record.get("resolution_reason"):
        problems.append(
            f"{work} names resolution_reason {board_reason} but {receipt_id} "
            f"records {record.get('resolution_reason')}"
        )
    return problems


def locate_external_project(
    root: Path | str,
    authority: str,
    *,
    hint_path: str | Path | None = None,
) -> Path | None:
    """Resolve an external authority lineage to a local readable project root.

    Does not crawl the filesystem. Checks explicit hint_path first, then
    immediate sibling projects of the current project and its parent category.
    Verifies that the candidate's canonical IDENTITY.md matches the lineage.
    Rejects symlink or reparse escapes.
    """
    import os
    import stat
    from .paths import project_lineage_identity

    authority = str(authority or "").strip()
    if not _AUTHORITY_RE.match(authority):
        return None

    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)

    if hint_path:
        cand = Path(hint_path)
        try:
            info = cand.lstat()
            if not (
                os.path.islink(cand) or bool(getattr(info, "st_file_attributes", 0) & reparse_flag)
            ):
                cand = cand.resolve()
                if cand.is_dir() and (cand / ".saipen" / "IDENTITY.md").is_file():
                    return cand
        except OSError:
            pass
        return None

    root_path = Path(root).resolve()
    candidates: list[Path] = []
    try:
        parent = root_path.parent
        for child in parent.iterdir():
            if child.is_dir() and child != root_path:
                candidates.append(child)
        grandparent = parent.parent
        for child in grandparent.iterdir():
            if child.is_dir() and child != parent:
                candidates.append(child)
    except OSError:
        pass

    for cand in candidates:
        try:
            if cand.is_symlink():
                continue
            info = cand.lstat()
            if bool(getattr(info, "st_file_attributes", 0) & reparse_flag):
                continue
            if (cand / ".saipen" / "IDENTITY.md").is_file():
                if project_lineage_identity(cand) == authority:
                    return cand
        except OSError:
            continue
    return None


def inspect_external_dependency(
    root: Path | str,
    authority: str,
    implementation: str,
    *,
    project_root: Path | str | None = None,
) -> dict:
    """Inspect an external implementation without mutation (read-only).

    Verifies external project lineage, checks if the external ticket is in
    DONE, and checks whether the referenced commit exists in external history.
    """
    from .board import parse_board
    from .paths import project_lineage_identity

    ext_root = locate_external_project(root, authority, hint_path=project_root)
    if ext_root is None:
        return {
            "ok": False,
            "code": "EXTERNAL_PROJECT_INACCESSIBLE",
            "detail": f"cannot locate readable canonical project for authority {authority}",
            "authority": authority,
            "implementation": implementation,
        }

    lineage = project_lineage_identity(ext_root)
    if lineage != authority:
        return {
            "ok": False,
            "code": "EXTERNAL_LINEAGE_MISMATCH",
            "detail": f"external project at {ext_root} reports lineage {lineage}, "
            f"expected {authority}",
            "authority": authority,
            "implementation": implementation,
            "external_root": str(ext_root),
        }

    m = _IMPLEMENTATION_RE.match(str(implementation or "").strip())
    if not m:
        return {
            "ok": False,
            "code": "EXTERNAL_IMPLEMENTATION_MALFORMED",
            "detail": f"{implementation!r} is not a valid <T-###>@<commit> identity",
            "authority": authority,
            "implementation": implementation,
        }
    ext_work, ext_commit = m.group(1), m.group(2)

    board_path = ext_root / ".saipen" / "BOARD.md"
    if not board_path.is_file():
        return {
            "ok": False,
            "code": "EXTERNAL_BOARD_MISSING",
            "detail": f"{ext_root} has no readable .saipen/BOARD.md",
            "authority": authority,
            "implementation": implementation,
            "external_root": str(ext_root),
        }
    try:
        ext_board = parse_board(board_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        return {
            "ok": False,
            "code": "EXTERNAL_BOARD_MALFORMED",
            "detail": f"cannot parse external BOARD.md: {exc}",
            "authority": authority,
            "implementation": implementation,
            "external_root": str(ext_root),
        }

    ticket = ext_board.get("tickets", {}).get(ext_work)
    if ticket is None:
        return {
            "ok": False,
            "code": "EXTERNAL_TICKET_ABSENT",
            "detail": f"external ticket {ext_work} not found on external board",
            "authority": authority,
            "implementation": implementation,
            "external_root": str(ext_root),
        }
    if ticket.get("section") != "## DONE":
        return {
            "ok": False,
            "code": "EXTERNAL_TICKET_NOT_DONE",
            "detail": f"external ticket {ext_work} is in "
            f"{ticket.get('section', 'unknown')}, not ## DONE",
            "authority": authority,
            "implementation": implementation,
            "external_root": str(ext_root),
            "external_section": ticket.get("section"),
        }

    ext_head = None
    git_dir = ext_root / ".git"
    if not git_dir.exists():
        # A DONE row and a matching lineage are NOT evidence that the named
        # commit exists or that it is this repository's HEAD ancestry. Without
        # its own git history the implementation identity cannot be proven at
        # all, so the dependency stays unverified instead of silently passing.
        return {
            "ok": False,
            "code": "EXTERNAL_GIT_EVIDENCE_MISSING",
            "detail": (
                f"{ext_root} carries no readable .git history; commit ancestry for "
                f"{implementation} cannot be proven (a DONE row and a matching "
                "lineage alone are not implementation evidence)"
            ),
            "authority": authority,
            "implementation": implementation,
            "external_root": str(ext_root),
        }
    try:
        proc = subprocess.run(
            ["git", "-C", str(ext_root), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        if proc.returncode != 0:
            return {
                "ok": False,
                "code": "EXTERNAL_GIT_ERROR",
                "detail": f"git rev-parse HEAD failed in {ext_root}: {proc.stderr.strip()}",
                "authority": authority,
                "implementation": implementation,
                "external_root": str(ext_root),
            }
        ext_head = proc.stdout.strip()
        proc_check = subprocess.run(
            ["git", "-C", str(ext_root), "cat-file", "-e", f"{ext_commit}^{{commit}}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        if proc_check.returncode != 0:
            return {
                "ok": False,
                "code": "EXTERNAL_COMMIT_MISSING",
                "detail": f"commit {ext_commit} not found in external repository history",
                "authority": authority,
                "implementation": implementation,
                "external_root": str(ext_root),
            }
        proc_anc = subprocess.run(
            ["git", "-C", str(ext_root), "merge-base", "--is-ancestor", ext_commit, ext_head],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        if proc_anc.returncode != 0:
            return {
                "ok": False,
                "code": "EXTERNAL_COMMIT_NOT_IN_HEAD",
                "detail": f"commit {ext_commit} is not an ancestor of external HEAD {ext_head}",
                "authority": authority,
                "implementation": implementation,
                "external_root": str(ext_root),
            }
    except FileNotFoundError:
        return {
            "ok": False,
            "code": "EXTERNAL_GIT_UNAVAILABLE",
            "detail": "git executable is unavailable for external commit verification",
            "authority": authority,
            "implementation": implementation,
            "external_root": str(ext_root),
        }
    except Exception as exc:
        return {
            "ok": False,
            "code": "EXTERNAL_GIT_ERROR",
            "detail": f"git verification failed: {exc}",
            "authority": authority,
            "implementation": implementation,
            "external_root": str(ext_root),
        }

    return {
        "ok": True,
        "code": "EXTERNAL_IMPLEMENTATION_VERIFIED",
        "authority": authority,
        "implementation": implementation,
        "external_work": ext_work,
        "external_commit": ext_commit,
        "external_root": str(ext_root),
        "external_head": ext_head,
    }


def contract_plan(root: Path | str, fields: dict) -> tuple[dict | None, str | None, str | None]:
    """Load the ONE sealed execution contract a ticket names, or refuse.

    Executable checks come from a regression-execution contract (schema 1
    under .saipen/evidence/), whose argv, runtime and environment are
    authenticated by regression_execution itself: argv only (no shell),
    the executable proven owned and sha256-bound, session authority scrubbed
    from the environment. BOARD prose -- verify or external_run -- is never
    an executable authority, no matter which prefix it starts with.
    Returns (plan, problem_code, problem_detail).
    """
    from . import regression_execution as reg_exec

    relative_raw = fields.get("verification_contract") or fields.get("contract_path")
    if not relative_raw:
        return (
            None,
            "EXTERNAL_VERIFICATION_REQUIRED",
            "external verification requires a sealed execution contract under "
            ".saipen/evidence/ (regression-execution schema 1) named by "
            "verification_contract; a BOARD verify/external_run prose string is "
            "never executed",
        )
    relative = str(relative_raw).strip()
    expected_digest = (
        fields.get("verification_contract_digest")
        or fields.get("contract_digest")
        or fields.get("contract_sha256")
    )
    if "@" in relative and not expected_digest:
        relative, expected_digest = relative.split("@", 1)
    elif "#" in relative and not expected_digest:
        relative, expected_digest = relative.split("#", 1)
    if expected_digest:
        contract_path = Path(root) / str(relative)
        try:
            actual_digest = hashlib.sha256(contract_path.read_bytes()).hexdigest()
        except OSError as exc:
            return (
                None,
                "EXTERNAL_VERIFICATION_CONTRACT_INVALID",
                f"verification contract {relative} is unreadable: {exc}",
            )
        clean_expected = str(expected_digest).strip()
        if clean_expected.startswith("sha256:"):
            clean_expected = clean_expected[7:]
        if actual_digest != clean_expected:
            return (
                None,
                "EXTERNAL_VERIFICATION_CONTRACT_INVALID",
                f"verification contract {relative} content tampered or substituted "
                f"(expected sha256:{clean_expected}, actual sha256:{actual_digest})",
            )
    try:
        material = reg_exec._load(root, str(relative), closed=True)
    except Exception as exc:
        return (
            None,
            "EXTERNAL_VERIFICATION_CONTRACT_INVALID",
            f"verification contract {relative} is not an authenticated executable contract: {exc}",
        )
    return (
        {
            "argv": list(material["argv"]),
            "runtime": dict(material["runtime"]),
            "environment": dict(material["environment"]),
            "timeout": int(material["contract"]["timeout"]),
            "verifier": material["verifier"],
            "contract_path": str(relative),
            "command": " ".join(material["argv"]),
            "contract_sha256": hashlib.sha256(material["contract_raw"]).hexdigest(),
            "context_sha256": reg_exec._sha(
                reg_exec._json(reg_exec._manifest(material["context"]))
            ),
        },
        None,
        None,
    )


def execution_entry(root: Path | str, plan: dict) -> dict:
    """Execute ONE authenticated argv plan and return its receipt entry.

    The argv, the proven runtime and the scrubbed environment come from the
    sealed contract (or a receipt written from one). Nothing is re-parsed
    through a shell, so BOARD-shaped metacharacters can never become commands.
    """
    from .process_tree import run

    started = datetime.now(timezone.utc)
    entry: dict = {
        "command": str(plan.get("command") or ""),
        "argv": list(plan["argv"]),
        "runtime": dict(plan["runtime"]),
        "verifier": plan.get("verifier"),
        "contract_path": plan.get("contract_path"),
        "executed": True,
    }
    for name in ("contract_sha256", "context_sha256", "require_tests", "report_format"):
        if name in plan:
            entry[name] = plan[name]
    try:
        completed = run(
            list(plan["argv"]),
            cwd=str(root),
            env=dict(plan.get("environment") or {}),
            capture_output=True,
            text=True,
            timeout=int(plan.get("timeout") or 300),
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        entry.update(
            result="FAIL",
            exit_code=None,
            launch_error=type(exc).__name__,
            duration_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
        )
        return entry
    output = (completed.stdout or "") + (completed.stderr or "")
    entry.update(
        result="PASS" if completed.returncode == 0 else "FAIL",
        exit_code=completed.returncode,
        output_bytes=len(output.encode("utf-8", "replace")),
        output_digest=hashlib.sha256(output.encode("utf-8", "replace")).hexdigest()[:16],
        duration_ms=int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
    )
    if plan.get("require_tests"):
        from .regression_execution import parse_summary

        try:
            summary = parse_summary(output, plan.get("report_format"))
            entry["summary"] = summary
            if summary["failed"] or summary["skipped"]:
                entry["result"] = "FAIL"
        except (ValueError, TypeError) as exc:
            entry.update(result="FAIL", summary_problem=str(exc))
    return entry


def _same_executable_path(left, right) -> bool:
    """Accept host path spelling aliases only when they name the same file."""
    if not isinstance(left, str) or not isinstance(right, str) or not left or not right:
        return False
    if not os.path.isabs(left) or not os.path.isabs(right):
        return False
    if os.path.normcase(os.path.normpath(left)) != os.path.normcase(os.path.normpath(right)):
        return False
    try:
        return os.path.samefile(left, right)
    except (OSError, ValueError):
        return False


def _same_argv(left, right) -> bool:
    return (
        isinstance(left, list)
        and isinstance(right, list)
        and bool(left)
        and bool(right)
        and left[1:] == right[1:]
        and _same_executable_path(left[0], right[0])
    )


def _same_runtime(left, right) -> bool:
    return (
        isinstance(left, dict)
        and isinstance(right, dict)
        and {key: value for key, value in left.items() if key != "path"}
        == {key: value for key, value in right.items() if key != "path"}
        and _same_executable_path(left.get("path"), right.get("path"))
    )


def receipt_plan(entry: dict, *, root=None) -> tuple[dict | None, str | None]:
    """Re-admit ONE stored receipt check as an executable plan, or refuse.

    A receipt check re-executes only when it carries an authenticated argv and
    a proven runtime whose CURRENT bytes still hash to the recorded digest. A
    stored command string (legacy or operator at the time it ran) is never
    re-shelled: without the executable identity it has no authority at all.
    """
    argv = entry.get("argv")
    runtime = entry.get("runtime")
    if not isinstance(argv, list) or not argv or not isinstance(runtime, dict):
        return (
            None,
            f"check {str(entry.get('command') or '')[:60]!r} carries no authenticated "
            "argv/runtime identity; a stored command string is never re-executed "
            "through a shell",
        )
    if "contract_sha256" in entry:
        if root is None:
            return None, "current owned project is required to re-admit this external check"
        current, code, detail = contract_plan(
            Path(root),
            {
                "verification_contract": entry.get("contract_path"),
                "verification_contract_digest": entry["contract_sha256"],
            },
        )
        if current is None:
            return None, str(code) + ": " + str(detail)
        if (
            current["context_sha256"] != entry.get("context_sha256")
            or not _same_argv(current["argv"], argv)
            or not _same_runtime(current["runtime"], runtime)
        ):
            return None, "external verifier context/runtime/argv changed since the receipt"
        if entry.get("require_tests"):
            from .regression_execution import _load

            material = _load(Path(root), entry["contract_path"], closed=True)
            if entry.get("report_format") != material["contract"]["format"]:
                return None, "external verifier summary contract changed"
            current.update(require_tests=True, report_format=entry["report_format"])
        return current, None
    from .paths import prove_owned_regular

    executable = Path(str(runtime.get("path") or ""))
    try:
        info = prove_owned_regular(executable, kind="verifier runtime")
        digest = hashlib.sha256()
        from .paths import update_digest_regular_bytes

        update_digest_regular_bytes(executable, info, digest)
    except (OSError, ValueError):
        return None, f"verifier runtime {executable} is not a proven owned executable"
    if digest.hexdigest() != str(runtime.get("sha256") or ""):
        return (
            None,
            f"verifier executable {executable} changed bytes since the receipt was "
            "written; the recorded check is no longer the authenticated one",
        )
    from .regression_execution import execution_environment

    return (
        {
            "argv": [str(item) for item in argv],
            "runtime": dict(runtime),
            "environment": execution_environment(),
            "timeout": 300,
            "verifier": entry.get("verifier"),
            "contract_path": entry.get("contract_path"),
            "command": str(entry.get("command") or " ".join(str(item) for item in argv)),
        },
        None,
    )


def operator_gate_problem(ticket: dict) -> str | None:
    """Why an external implementation may not decide this row, or None.

    A WAIT_USER_DECISION / WAIT_USER_CONFIRMATION / DEFERRED_BY_OPERATOR row
    carries an operator decision. Structured external fields never confer the
    authority to lift it -- only the operator's own recorded reply may.
    """
    fields = ticket.get("fields") or {}
    blocker = str(fields.get("blocker") or "").lower()
    for token in OPERATOR_GATE_TOKENS:
        if token in blocker:
            return (
                "row carries an operator gate; an external implementation never "
                "lifts WAIT_USER_DECISION/WAIT_USER_CONFIRMATION/DEFERRED_BY_OPERATOR "
                "-- only the operator's recorded reply does"
            )
    return None


def revalidate_external_dependencies(
    project_root: Path | str,
    agent: str,
    *,
    dry_run: bool = False,
    cache: dict | None = None,
    target_ticket: str | None = None,
) -> dict:
    """Bounded external dependency revalidation pass (Queue E).

    Inspects stale external receipts and declared external dependencies on
    BOARD.md. Revalidates verifiable candidates through canonical operations,
    recomputes work eligibility, and skips unchanged evidence generations.
    Every executable check arrives as an authenticated argv plan (sealed
    receipt identity or sealed execution contract); BOARD prose never runs.
    """
    from .board import (
        external_authority as _authority,
        external_implementation as _implementation,
        parse_board,
    )
    from .operations import resolve_external_ticket

    root = Path(project_root).resolve()
    board_path = root / ".saipen" / "BOARD.md"
    if not board_path.is_file():
        return {"ok": False, "code": "BOARD_MISSING", "detail": "BOARD.md is missing"}

    try:
        board_text = board_path.read_text(encoding="utf-8")
        parsed_board = parse_board(board_text)
    except Exception as exc:
        return {"ok": False, "code": "BOARD_UNREADABLE", "detail": str(exc)}

    tickets = parsed_board.get("tickets", {})
    resolved_tickets: list[str] = []
    predicted_eligible: list[str] = []
    resumed_parents: list[str] = []
    projected_parents: list[str] = []
    blocked_findings: list[dict] = []
    inaccessible: list[str] = []
    inspected_count = 0
    revalidated_count = 0
    candidate_keys: list[str] = []

    cur_engine = engine_identity()
    engine_digest = cur_engine.get("engine_digest", "")[:16]

    # 1. Existing external receipts: check for installed engine moves
    receipt_files = existing_receipts(root)
    for rpath in receipt_files:
        try:
            record = load_receipt(root, rpath.stem)
        except ExternalRefusal:
            continue
        work = record.get("work")
        if target_ticket and work != target_ticket:
            continue
        ticket = tickets.get(work)
        if not ticket or ticket.get("section") != "## DONE":
            continue
        problems = resolution_problems(root, work, ticket)
        if not problems:
            continue
        engine_moved = any("engine generation" in p and "dependency moved" in p for p in problems)
        other_problems = [
            p for p in problems if not ("engine generation" in p and "dependency moved" in p)
        ]
        if engine_moved and not other_problems:
            inspected_count += 1
            cand_key = (
                f"{work}:engine_move:{record.get('external_authority')}:"
                f"{record.get('external_implementation')}:{engine_digest}"
            )
            candidate_keys.append(cand_key)
            if cache is not None and cand_key in cache:
                continue
            # The recorded checks re-execute ONLY when they carry the
            # authenticated argv/runtime identity; a stored command string is
            # never re-shelled. This is an honest decline, not a silent pass.
            plans: list[dict] = []
            problem: str | None = None
            for entry in record.get("verification", []):
                if not entry.get("argv"):
                    problem = (
                        f"{work}'s recorded check {str(entry.get('command') or '')[:60]!r} "
                        "carries no authenticated argv/runtime identity; re-resolution "
                        "requires a sealed execution contract"
                    )
                    break
                plan, refusal = receipt_plan(entry, root=root)
                if refusal:
                    problem = refusal
                    break
                plans.append(plan)
            if dry_run:
                if problem is None:
                    predicted_eligible.append(work)
                else:
                    blocked_findings.append(
                        {
                            "ticket": work,
                            "code": "EXTERNAL_VERIFICATION_UNAUTHENTICATED",
                            "detail": problem,
                        }
                    )
                if cache is not None:
                    cache[cand_key] = True
            elif problem is not None:
                blocked_findings.append(
                    {
                        "ticket": work,
                        "code": "EXTERNAL_VERIFICATION_UNAUTHENTICATED",
                        "detail": problem,
                    }
                )
            else:
                res = resolve_external_ticket(
                    root,
                    work,
                    agent,
                    authority=record["external_authority"],
                    implementation=record["external_implementation"],
                    resolution_reason=record.get("resolution_reason", "UPSTREAM_FIX_VERIFIED"),
                    plans=plans,
                )
                if res.ok:
                    revalidated_count += 1
                    resolved_tickets.append(work)
                    if getattr(res, "data", {}) and res.data.get("resumed_parent"):
                        resumed_parents.append(res.data["resumed_parent"])
                    if cache is not None:
                        cache[cand_key] = True
                else:
                    blocked_findings.append(
                        {
                            "ticket": work,
                            "code": res.code,
                            "detail": res.message,
                        }
                    )

    # 2. Blocked tickets with declared external dependencies
    for tid, ticket in tickets.items():
        if target_ticket and tid != target_ticket:
            continue
        if ticket.get("section") != "## BLOCKED":
            continue
        fields = ticket.get("fields", {})
        auth = _authority(ticket) or fields.get("external_authority")
        impl = _implementation(ticket) or fields.get("external_implementation")
        if not auth or not impl:
            continue
        inspected_count += 1

        # An operator gate is the operator's decision; structured external
        # fields never confer the authority to lift it.
        gate = operator_gate_problem(ticket)
        if gate is not None:
            blocked_findings.append(
                {
                    "ticket": tid,
                    "code": "OPERATOR_DECISION_REQUIRED",
                    "detail": f"{tid}: {gate}",
                    "authority": auth,
                    "implementation": impl,
                }
            )
            continue

        ext_proj = fields.get("external_project")
        insp = inspect_external_dependency(root, auth, impl, project_root=ext_proj)
        ext_head = insp.get("external_head") or "no_git"
        verify_text = str(fields.get("verify") or "")
        c_digest = contract_digest(tid, verify_text)[:16]
        cand_key = f"{tid}:{auth}:{impl}:{ext_head}:{engine_digest}:{c_digest}"
        candidate_keys.append(cand_key)
        if cache is not None and cand_key in cache:
            continue

        if not insp.get("ok"):
            if insp.get("code") == "EXTERNAL_PROJECT_INACCESSIBLE":
                inaccessible.append(auth)
            blocked_findings.append(
                {
                    "ticket": tid,
                    "code": insp.get("code"),
                    "detail": insp.get("detail"),
                    "authority": auth,
                    "implementation": impl,
                }
            )
            continue

        # Executable checks come ONLY from structured evidence: a sealed
        # receipt's authenticated argv, or the sealed execution contract the
        # ticket names. BOARD verify/external_run prose is never an authority.
        plans: list[dict] = []
        plan_problem: tuple[str, str] | None = None
        if fields.get("external_evidence"):
            try:
                prev_receipt = load_receipt(root, fields["external_evidence"])
                for entry in prev_receipt.get("verification", []):
                    if not entry.get("argv"):
                        plan_problem = (
                            "EXTERNAL_VERIFICATION_UNAUTHENTICATED",
                            f"{fields['external_evidence']} records a check with no "
                            "authenticated argv identity; a stored command string is "
                            "never re-executed through a shell",
                        )
                        break
                    plan, refusal = receipt_plan(entry)
                    if refusal:
                        plan_problem = ("EXTERNAL_VERIFICATION_UNAUTHENTICATED", refusal)
                        break
                    plans.append(plan)
            except Exception:
                plans = []

        if not plans and plan_problem is None:
            plan, code, detail = contract_plan(root, fields)
            if plan is None:
                plan_problem = (code, f"{tid}: {detail}")
            else:
                plans = [plan]

        if plan_problem is not None:
            blocked_findings.append(
                {
                    "ticket": tid,
                    "code": plan_problem[0],
                    "detail": plan_problem[1],
                    "authority": auth,
                    "implementation": impl,
                }
            )
            continue

        reason = fields.get("resolution_reason") or "UPSTREAM_FIX_VERIFIED"

        if dry_run:
            predicted_eligible.append(tid)
            for parent_id, parent_ticket in tickets.items():
                if parent_ticket.get("section") == "## BLOCKED":
                    needs = [
                        n.strip()
                        for n in str(parent_ticket.get("fields", {}).get("needs") or "").split(",")
                        if n.strip()
                    ]
                    blocked_on = str(
                        parent_ticket.get("fields", {}).get("blocked_on") or ""
                    ).strip()
                    if tid in needs or tid == blocked_on:
                        projected_parents.append(parent_id)
            if cache is not None:
                cache[cand_key] = True
        else:
            res = resolve_external_ticket(
                root,
                tid,
                agent,
                authority=auth,
                implementation=impl,
                resolution_reason=reason,
                plans=plans,
            )
            if res.ok:
                revalidated_count += 1
                resolved_tickets.append(tid)
                if getattr(res, "data", {}) and res.data.get("resumed_parent"):
                    resumed_parents.append(res.data["resumed_parent"])
                if cache is not None:
                    cache[cand_key] = True
            else:
                blocked_findings.append(
                    {
                        "ticket": tid,
                        "code": res.code,
                        "detail": res.message,
                    }
                )

    return {
        "ok": True,
        "dry_run": dry_run,
        "discovered": len(candidate_keys),
        "inspected": inspected_count,
        "revalidated": revalidated_count if not dry_run else 0,
        "resolved": resolved_tickets if not dry_run else [],
        "predicted_eligible": predicted_eligible,
        "projected": predicted_eligible,
        "resumed_parents": resumed_parents if not dry_run else [],
        "projected_parents": projected_parents,
        "still_blocked": blocked_findings,
        "inaccessible": sorted(set(inaccessible)),
    }


def classify_blocked_inventory(tickets: dict, project_root: Path | str | None = None) -> dict:
    """Classify remaining blocked work into 7 derived reporting classifications (Queue G).

    TECHNICALLY_VERIFIABLE
    EXTERNAL_WORK_PENDING
    OPERATOR_DECISION_REQUIRED
    HARDWARE_ACCEPTANCE_REQUIRED
    FUTURE_GATED
    FORENSIC_EVIDENCE_MISSING
    UNRESOLVED
    """
    classifications: dict[str, list[dict]] = {
        "TECHNICALLY_VERIFIABLE": [],
        "EXTERNAL_WORK_PENDING": [],
        "OPERATOR_DECISION_REQUIRED": [],
        "HARDWARE_ACCEPTANCE_REQUIRED": [],
        "FUTURE_GATED": [],
        "FORENSIC_EVIDENCE_MISSING": [],
        "UNRESOLVED": [],
    }

    hw_tokens = (
        "winerror 1314",
        "symlink privilege",
        "ag3-token",
        "luna host",
        "luna runtime",
        "freebuff desktop cwd",
        "kiro blocking-adapter",
        "kiro runtime",
        "codex negative probe",
        "codex has a documented stop",
        "production host authority",
    )
    op_tokens = (
        "wait_user_decision",
        "wait_user_confirmation",
        "deferred_by_operator",
        "wait_role",
        "markhunt_triage_required",
        "mutation authorization is absent",
        "requires operator",
        "operator decides",
        "operator chooses",
        "operator witness",
        "operator authorization",
        "operator reply",
    )
    forensic_tokens = (
        "missing external fastprompter_drag",
        "missing forensic",
        "forensic uncertainty",
        "two artifacts are no longer in the installation root",
    )
    future_tokens = (
        "held",
        "future/strategic hold",
        "roadmap_incomplete",
        "concurrent mode",
        "sequential stability",
        "v9 runtime",
    )

    for tid, ticket in tickets.items():
        if ticket.get("section") != "## BLOCKED":
            continue
        fields = ticket.get("fields", {})
        blocker = str(fields.get("blocker") or "").lower()
        desc = str(ticket.get("description") or "")
        combined = f"{blocker} {desc.lower()}"
        tid_item = {
            "ticket": tid,
            "source_receipts": fields.get("source_receipts", ""),
            "blocker_summary": str(fields.get("blocker") or "")[:120],
        }

        # Check if structured external fields exist and can be verified
        auth = fields.get("external_authority")
        impl = fields.get("external_implementation")
        if auth and impl and project_root:
            insp = inspect_external_dependency(
                project_root, auth, impl, project_root=fields.get("external_project")
            )
            if insp.get("ok"):
                classifications["TECHNICALLY_VERIFIABLE"].append(tid_item)
                continue

        if any(tok in combined for tok in forensic_tokens) or tid in ("T-1764", "T-1765"):
            classifications["FORENSIC_EVIDENCE_MISSING"].append(tid_item)
        elif any(tok in combined for tok in hw_tokens):
            classifications["HARDWARE_ACCEPTANCE_REQUIRED"].append(tid_item)
        elif any(tok in combined for tok in op_tokens):
            classifications["OPERATOR_DECISION_REQUIRED"].append(tid_item)
        elif any(tok in combined for tok in future_tokens) or tid in (
            "T-1702",
            "T-1257",
            "T-1099",
            "T-1719",
            "T-1720",
            "T-473",
            "T-442",
            "T-575",
        ):
            classifications["FUTURE_GATED"].append(tid_item)
        elif "blocked_external" in blocker or "active_dependency" in blocker:
            classifications["EXTERNAL_WORK_PENDING"].append(tid_item)
        else:
            classifications["UNRESOLVED"].append(tid_item)

    counts = {cat: len(items) for cat, items in classifications.items()}
    return {
        "counts": counts,
        "classifications": classifications,
    }
