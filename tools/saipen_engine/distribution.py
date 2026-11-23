"""Source-receipt distribution boundary.

Canonical receipt bodies remain exact local authority.  A quarantined body
lives below ``.saipen/quarantine/``; that entire prefix is deliberately
outside every supported distribution surface.  The exported quarantine
record stays under intake and identifies the receipt and digest without
carrying the body.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath


DISTRIBUTABLE = "DISTRIBUTABLE"
QUARANTINED = "QUARANTINED"

QUARANTINE_PREFIX = ".saipen/quarantine/"
QUARANTINE_SOURCE_DIR = Path(".saipen/quarantine/source")
DISTRIBUTION_RECORD_DIR = Path(".saipen/intake/distribution")

#: T-2174 / Campaign XVIII §9. Raw environment dumps were git-tracked under
#: scratch roots and shipped in the handoff archive with plaintext credential
#: values. These are transient diagnostics, never evidence: the exportable
#: form is a key-DIGEST record under evidence/, which carries no secret value.
#: Matching is structural (a scratch ROOT plus an env-like file name, or a
#: direct env-dump name anywhere), so a new dump under an existing scratch
#: root is excluded without suppressing real evidence elsewhere.
SCRATCH_ENV_ROOTS = ("_TEMP_", ".saipen/tmp", "scratch", ".saipen/kitchen")

#: HANDOFF 2026-11-23: the top-level research kitchen held four untracked
#: diagnostics with plaintext credential values, including two ``*family.json``
#: exports. Inside the kitchen only these env-dump shapes are refused; the
#: three explicitly tracked project-memory files stay exportable.
KITCHEN_DUMP_SUFFIXES = (".env", "family.json")
KITCHEN_ALLOWED_NAMES = frozenset({
    "cohort_registry.json", "digest.md", "release_receipt.json",
})
ENV_DUMP_STEMS = ("env", "env1", "env2", "env3", "env_a", "env_b",
                  "env_ba_py", "env_ps_py", "env_ps", "env_ba",
                  "env_probe_1", "env_probe_2", "ident_a", "gate_debug",
                  "dump_out")


def _is_raw_env_dump(value: str) -> bool:
    parts = value.split("/")
    stem = PurePosixPath(parts[-1]).stem.lower()
    if len(parts) > 1 and "/".join(parts[:-1]) == ".saipen/kitchen":
        name = parts[-1].lower()
        if name in KITCHEN_ALLOWED_NAMES:
            return False
        return name.endswith(KITCHEN_DUMP_SUFFIXES)
    if not stem.startswith("env") and stem not in ENV_DUMP_STEMS:
        return False
    if len(parts) == 1:
        return stem in ENV_DUMP_STEMS or stem.startswith("env")
    root = "/".join(parts[:-1])
    return any(
        root == candidate or root.startswith(candidate + "/")
        for candidate in SCRATCH_ENV_ROOTS
    )


def quarantine_body_rel(receipt_id: str) -> str:
    """Return the protected canonical body location for one receipt."""
    return (QUARANTINE_SOURCE_DIR / f"{receipt_id}.md").as_posix()


def distribution_record_rel(receipt_id: str) -> str:
    """Return the export-safe distribution record location."""
    return (DISTRIBUTION_RECORD_DIR / f"{receipt_id}.json").as_posix()


def is_non_exportable_path(path: str | Path) -> bool:
    """True only for the protected local-authority namespace.

    Paths are repository-relative.  Backslashes are normalized because Git,
    ZIP, PowerShell, and pathlib callers do not all use the same separator.
    """
    value = PurePosixPath(str(path).replace("\\", "/")).as_posix()
    while value.startswith("./"):
        value = value[2:]
    value = value.lstrip("/")
    if value == QUARANTINE_PREFIX.rstrip("/") or value.startswith(QUARANTINE_PREFIX):
        return True
    return _is_raw_env_dump(value)
