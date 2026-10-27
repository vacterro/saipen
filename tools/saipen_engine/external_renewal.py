"""Explicit same-owner renewal of an immutable external implementation proof."""

from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path, PurePosixPath

from . import external
from .journal import (
    hash_bytes,
    hash_file_dependency,
    hash_tree_dependency,
    semantic_receipt_snapshot,
)
from .paths import prove_owned_dir_chain, prove_owned_regular, read_bound_regular_bytes


def _git(root, *arguments):
    result = subprocess.run(["git", "-C", str(root), *arguments],
                            env=external.git_environment(), capture_output=True, timeout=30)
    if result.returncode:
        raise ValueError("external Git evidence is unavailable")
    return result.stdout


def _paths(paths):
    if (
        not isinstance(paths, (list, tuple))
        or not paths
        or len(paths) > 256
        or any(not isinstance(item, str) or not item for item in paths)
    ):
        raise ValueError("explicit external implementation paths are required")
    for rel in paths:
        if (
            ":" in rel
            or "\\" in rel
            or PurePosixPath(rel).is_absolute()
            or any(part in ("", ".", "..") for part in rel.split("/"))
            or rel.split("/")[0].casefold() in (".git", ".saipen")
            or any(ord(char) < 32 for char in rel)
        ):
            raise ValueError("external implementation path is not confined source")
    if len({item.casefold() for item in paths}) != len(paths):
        raise ValueError("duplicate or aliased external implementation path")
    return sorted(paths)


def _read(root, rel):
    path = root / rel
    prove_owned_dir_chain(path.parent, ownership_root=root, kind="external implementation")
    info = prove_owned_regular(path, kind="external implementation")
    return read_bound_regular_bytes(path, info, max_bytes=32 * 1024 * 1024)


def runtime_inputs(paths):
    """Hash explicitly declared native/runtime inputs without executing them."""
    if not isinstance(paths, (list, tuple)) or len(paths) > 256:
        raise ValueError("runtime inputs must be a bounded path list")
    result = {}
    seen = set()
    for raw in paths:
        path = Path(raw)
        if not path.is_absolute() or str(path).casefold() in seen:
            raise ValueError("runtime input must be an unaliased absolute path")
        seen.add(str(path).casefold())
        info = prove_owned_regular(path, kind="external verification runtime input")
        content = read_bound_regular_bytes(path, info, max_bytes=32 * 1024 * 1024)
        result[str(path)] = hashlib.sha256(content).hexdigest()
    return result


def capture(root, authority, implementation, paths, *, external_root=None):
    """Bind declared actual artifacts to the immutable carrying commit."""
    from .closure import member_hash_matches

    paths = _paths(paths)
    inspected = external.inspect_external_dependency(
        root, authority, implementation, project_root=external_root
    )
    if not inspected.get("ok"):
        raise ValueError(str(inspected.get("code")) + ": " + str(inspected.get("detail")))
    upstream = Path(inspected["external_root"])
    commit = (
        _git(upstream, "rev-parse", inspected["external_commit"] + "^{commit}").decode().strip()
    )
    files = {}
    for rel in paths:
        expected = _git(upstream, "show", f"{commit}:{rel}")
        current = _read(upstream, rel)
        if not member_hash_matches(current, hash_bytes(expected)):
            raise ValueError("external implementation differs from its carrying commit: " + rel)
        files[rel] = hashlib.sha256(current).hexdigest()
    work = implementation.split("@", 1)[0]
    return {
        "authority": authority,
        "implementation": f"{work}@{commit}",
        "root": str(upstream),
        "files": files,
    }


def snapshot_problem(root, snapshot):
    """A moved external artifact or rolled-back commit is not current evidence."""
    try:
        if not isinstance(snapshot, dict) or not isinstance(snapshot.get("files"), dict):
            raise ValueError("external proof snapshot is malformed")
        observed = capture(
            root,
            snapshot["authority"],
            snapshot["implementation"],
            list(snapshot["files"]),
            external_root=snapshot.get("root"),
        )
        if observed["files"] != snapshot["files"]:
            raise ValueError("external implementation bytes changed since verification")
        if runtime_inputs(list(snapshot.get("runtime_inputs", {}))) != snapshot.get(
            "runtime_inputs", {}
        ):
            raise ValueError("external native/runtime inputs changed since verification")
        return None
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        return str(exc)


def proof_problem(root, record):
    """Modern proof needs a committed receipt and real unskipped execution."""
    from .journal import semantic_receipts_for_operation_safe

    try:
        rel = f"{external.EXTERNAL_DIR}/{record['receipt_id']}.json"
        raw = (Path(root) / rel).read_bytes()
        records, errors = semantic_receipts_for_operation_safe(root, "external_resolve")
        if errors:
            raise ValueError("external proof journal is corrupt")
        committed = next(
            (
                item
                for item in records
                if item.get("op_id") == record.get("journal_op_id")
                and item.get("status") == "COMMITTED"
            ),
            None,
        )
        if committed is None or not any(
            item.get("path") == rel and item.get("after_hash") == hash_bytes(raw)
            for item in committed.get("targets", [])
        ):
            raise ValueError("external proof has no intact committed journal target")
        previous = record.get("predecessor")
        if not isinstance(previous, dict) or previous.get("receipt_id") == record["receipt_id"]:
            raise ValueError("external proof predecessor is invalid")
        external.load_receipt(root, previous["receipt_id"])
        prior_raw = (
            Path(root) / external.EXTERNAL_DIR / (previous["receipt_id"] + ".json")
        ).read_bytes()
        if hashlib.sha256(prior_raw).hexdigest() != previous.get("sha256"):
            raise ValueError("external proof predecessor changed")
        entries = record.get("verification")
        if not isinstance(entries, list) or not entries:
            raise ValueError("external proof has no executed checks")
        for entry in entries:
            summary = entry.get("summary")
            if (
                entry.get("executed") is not True
                or entry.get("require_tests") is not True
                or entry.get("result") != "PASS"
                or not isinstance(summary, dict)
                or any(type(summary.get(key)) is not int for key in ("ran", "failed", "skipped"))
                or summary["ran"] <= 0
                or summary["failed"]
                or summary["skipped"]
            ):
                raise ValueError("external proof lacks complete unskipped test execution")
        return None
    except (OSError, ValueError, KeyError, TypeError, external.ExternalRefusal) as exc:
        return str(exc)


def plan(
    root,
    work,
    agent,
    implementation,
    verification_contract,
    implementation_paths,
    *,
    external_root=None,
    native_inputs=(),
    dry_run=False,
):
    from . import operations as ops, regression_execution as reg_exec
    from .result import Result

    root = Path(root)
    read_once = ops._read(root)
    docs, state, board, _tail = read_once
    refusal = ops._active_claim_refusal(state, docs["board"].text_norm, agent)
    if refusal is not None:
        return refusal
    try:
        ticket = board["tickets"].get(work)
        if ticket is None or ticket["section"] != "## DONE":
            raise ValueError("external proof renewal requires existing DONE Work")
        fields = ticket.get("fields") or {}
        if fields.get("closure_mode") != external.CLOSURE_MODE:
            raise ValueError("external proof renewal never changes another closure mode")
        operator = external.operator_gate_problem(ticket)
        if operator:
            raise ValueError(operator)
        previous = external.load_receipt(root, fields.get("external_evidence"))
        if previous.get("agent") != agent:
            raise ValueError("external proof renewal requires the original canonical owner")
        problems = external.receipt_binding_problems(root, work, ticket, previous)
        if problems:
            raise ValueError("original external proof is not intact: " + "; ".join(problems))
        original = previous.get("external_implementation", "")
        if (
            external.implementation_error(implementation)
            or implementation.split("@", 1)[0] != original.split("@", 1)[0]
        ):
            raise ValueError("renewal must preserve the external Work identity")
        if previous.get("defect_contract_digest") != external.contract_digest(
            work, fields.get("verify", "")
        ):
            raise ValueError("renewal must preserve the original defect contract")
        authority = semantic_receipt_snapshot(root)
        if authority.errors:
            raise ValueError("corrupt original receipt journal: " + "; ".join(authority.errors[:3]))
        old_rel = f"{external.EXTERNAL_DIR}/{previous['receipt_id']}.json"
        old_raw = (root / old_rel).read_bytes()
        committed = next(
            (
                item
                for item in authority.records
                if item.get("op_id") == previous.get("journal_op_id")
                and item.get("operation") == "external_resolve"
                and item.get("status") == "COMMITTED"
            ),
            None,
        )
        if committed is None or not any(
            item.get("path") == old_rel and item.get("after_hash") == hash_bytes(old_raw)
            for item in committed.get("targets", [])
        ):
            raise ValueError("original external receipt has no intact committed journal target")
        binding = capture(
            root,
            previous["external_authority"],
            implementation,
            implementation_paths,
            external_root=external_root,
        )
        binding["runtime_inputs"] = runtime_inputs(native_inputs)
        upstream = Path(binding["root"])
        ancestor = subprocess.run(
            [
                "git",
                "-C",
                str(upstream),
                "merge-base",
                "--is-ancestor",
                original.split("@", 1)[1],
                binding["implementation"].split("@", 1)[1],
            ],
            env=external.git_environment(),
            capture_output=True,
            timeout=30,
        )
        if ancestor.returncode:
            raise ValueError("renewal cannot select a rollback or unrelated implementation commit")
        material = reg_exec._load(root, verification_contract, closed=True)
        executable, code, detail = external.contract_plan(
            root,
            {
                "verification_contract": material["contract_path"],
                "verification_contract_digest": hashlib.sha256(
                    material["contract_raw"]
                ).hexdigest(),
            },
        )
        if executable is None:
            raise ValueError(str(code) + ": " + str(detail))
        executable.update(require_tests=True, report_format=material["contract"]["format"])
        from .intake import work_closure_gate

        source_gate = work_closure_gate(root, work)
        if not source_gate.get("ok"):
            raise ValueError("unresolved Source coverage: " + str(source_gate))
        previous_checks = previous.get("verification") or []
        if (
            previous.get("external_snapshot") == binding
            and len(previous_checks) == 1
            and not external.resolution_problems(root, work, ticket)
            and external._same_argv(previous_checks[0].get("argv"), executable.get("argv"))
            and external._same_runtime(previous_checks[0].get("runtime"), executable.get("runtime"))
            and all(
                previous_checks[0].get(key) == executable.get(key)
                for key in (
                    "contract_sha256",
                    "context_sha256",
                    "verifier",
                    "require_tests",
                    "report_format",
                )
            )
        ):
            return Result(
                True,
                "ALREADY_APPLIED",
                data={
                    "ticket": work,
                    "receipt_id": previous["receipt_id"],
                    "verification_executed": False,
                },
            )
        if dry_run:
            return Result(
                True,
                "PLAN",
                data={
                    "dry_run": True,
                    "ticket": work,
                    "implementation": binding["implementation"],
                    "verification_executed": False,
                },
            )
        dependencies = {
            old_rel: hash_bytes(old_raw),
            ".saipen/recovery": authority.digest,
            ".saipen/intake": hash_tree_dependency(root / ".saipen/intake"),
            material["contract_path"]: hash_file_dependency(root / material["contract_path"]),
        }
        for rel in material["contract"]["context"]:
            path = root / rel
            dependencies[rel] = (
                hash_tree_dependency(path) if path.is_dir() else hash_file_dependency(path)
            )
        predecessor = {
            "receipt_id": previous["receipt_id"],
            "sha256": hashlib.sha256(old_raw).hexdigest(),
            "journal_op_id": previous["journal_op_id"],
        }
        renewal = {
            "predecessor": predecessor,
            "external_snapshot": binding,
            "preconditions": dependencies,
        }
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        subprocess.SubprocessError,
        external.ExternalRefusal,
    ) as exc:
        return ops._refuse("VALIDATION_FAILED", str(exc))
    return ops._plan_resolve_external_ticket(
        root,
        work,
        agent,
        authority=previous["external_authority"],
        implementation=binding["implementation"],
        resolution_reason="DEPENDENCY_UPGRADE_VERIFIED",
        runs=None,
        verification=None,
        contract=previous["defect_contract_digest"],
        timeout=material["contract"]["timeout"],
        now=ops._now(),
        utc=ops._utc_iso(),
        plans=[executable],
        renewal=renewal,
        read_once=read_once,
    )
