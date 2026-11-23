"""T-1743 SAIPEN engine patch. Byte-level, line-ending preserving, anchored.

Each edit names its file and an anchor that must match exactly once; nothing
is written unless every anchor in that file matches.
"""
import pathlib
import sys

ROOT = pathlib.Path(r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\tools\saipen_engine")

EDITS: dict[str, list[tuple[str, str]]] = {}


def edit(name: str, old: str, new: str) -> None:
    EDITS.setdefault(name, []).append((old, new))


# --- F1: an adoption DEC is the operator's legacy classification -----------
edit(
    "log.py",
    '''LEGACY_DONE_ATTESTATION = "legacy completion attested"
''',
    '''LEGACY_DONE_ATTESTATION = "legacy completion attested"

#: The DEC text prefix `saipen recover --adopt-legacy` writes for a record that
#: had no allocation event. Like an attestation it is a NOW-dated operator
#: classification of a LEGACY record, never closure-generation evidence.
LEGACY_ADOPTION = "LEGACY_ADOPTED"
''',
)
edit(
    "reconcile.py",
    '''    attestation is the operator's legacy classification, never closure-
    generation evidence.
    """
    from .log import LEGACY_DONE_ATTESTATION

    return {
        ev.get("ticket")
        for ev in (events or ())
        if ev.get("ticket")
        and ev.get("op_id")
        and LEGACY_DONE_ATTESTATION not in (ev.get("text") or "")
    }
''',
    '''    attestation is the operator's legacy classification, never closure-
    generation evidence.

    The SAME holds for a `--adopt-legacy` DEC (T-1743, measured on
    SMART_VAC_CLEANER): adoption gives a legacy record the allocation event it
    never had, so counting it flipped the adopted rows to `current` and the
    very next `recover` demanded a reopen approval for rows the operator had
    just adopted AND attested in the same repair -- the cure re-armed the
    refusal it answered.
    """
    from .log import LEGACY_ADOPTION, LEGACY_DONE_ATTESTATION

    return {
        ev.get("ticket")
        for ev in (events or ())
        if ev.get("ticket")
        and ev.get("op_id")
        and LEGACY_DONE_ATTESTATION not in (ev.get("text") or "")
        and LEGACY_ADOPTION not in (ev.get("text") or "")
    }
''',
)
edit(
    "reconcile.py",
    '''            f"LEGACY_ADOPTED {_adopt_tid} -- no canonical allocation event is "''',
    '''            f"{LEGACY_ADOPTION} {_adopt_tid} -- no canonical allocation event is "''',
)

# --- F3: owned-path proofs stop at the project root ------------------------
edit(
    "audit_manifest.py",
    '''    prove_owned_dir_chain(path.parent, kind="audit manifest")''',
    '''    prove_owned_dir_chain(path.parent, kind="audit manifest", ownership_root=root)''',
)
edit(
    "audit_manifest.py",
    '''safe_atomic_write_bytes(path, render(manifest), kind="audit manifest")''',
    '''safe_atomic_write_bytes(path, render(manifest), kind="audit manifest", ownership_root=root)''',
)

edit(
    "reconcile.py",
    """        from .log import legacy_done_attestation_text
        from .plan import apply_plan, build_plan""",
    """        from .log import LEGACY_ADOPTION, legacy_done_attestation_text
        from .plan import apply_plan, build_plan""",
)
edit(
    "suite_record.py",
    """def _write_json(path: Path, data: dict) -> None:
""",
    """def _project_root_of(path: Path) -> Path | None:
    \"\"\"The project root above `path`'s `.saipen/`: the owned-path proof stops there.\"\"\"
    for parent in Path(path).parents:
        if parent.name == ".saipen":
            return parent.parent
    return None


def _write_json(path: Path, data: dict) -> None:
""",
)
edit(
    "suite_record.py",
    """    safe_atomic_write_bytes(path, text.encode("utf-8"), kind="suite evidence")
""",
    """    safe_atomic_write_bytes(
        path, text.encode("utf-8"), kind="suite evidence", ownership_root=_project_root_of(path)
    )
""",
)
edit(
    "suite_record.py",
    """    if not safe_unlink_owned(base / DECLARATION_REL, kind="suite declaration"):""",
    """    if not safe_unlink_owned(base / DECLARATION_REL, kind="suite declaration", ownership_root=base):""",
)


def apply() -> None:
    plans = {}
    for name, edits in EDITS.items():
        path = ROOT / name
        raw = path.read_bytes()
        crlf = b"\r\n" in raw
        text = raw.decode("utf-8")
        if crlf:
            text = text.replace("\r\n", "\n")
        for old, new in edits:
            count = text.count(old)
            if count != 1:
                sys.exit(f"{name}: anchor matched {count} times: {old[:90]!r}")
            text = text.replace(old, new, 1)
        if crlf:
            text = text.replace("\n", "\r\n")
        plans[path] = text.encode("utf-8")
    for path, data in plans.items():
        path.write_bytes(data)
        print("patched", path.name)


if __name__ == "__main__":
    apply()
