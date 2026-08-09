"""SubSaipen lifecycle operations on the common machinery (NITRO M8).

Mechanizes the DETERMINISTIC parts of the SubSaipen lifecycle (extensions/subs/
PROTOCOL.md section 7): spawn, list, status, pause, resume. The sub's own
STATE/BOARD/LOG/kitchen writes stay the sub's own mechanical business; what
Core owns here is the lifecycle boundary -- creating an instance journaled,
never overwriting an existing one, recording the MANIFEST line atomically, and
mutating a sub's phase only through owned-field patches.

NO semantic acceptance of a finding is mechanized. Core still judges work;
this module guarantees boundaries and mechanics.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from . import codec
from .journal import hash_bytes, run_mutation
from .lock import project_writer_lock
from .paths import project_identity
from .result import Result
from .state import patch_state

SUBS_REL = ".saipen/extensions/subs"
MANIFEST_REL = f"{SUBS_REL}/MANIFEST.md"


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d.%m.%y %H:%M")


def _refuse(code: str, detail: str = "", **extra) -> Result:
    return Result(ok=False, code=code, message=detail, data=extra)


def _sub_dir(project_root: Path, name: str) -> Path:
    safe = name.strip().replace("/", "").replace("\\", "")
    if not safe or safe != name.strip():
        raise ValueError(f"unsafe subSaipen name {name!r}")
    return project_root / SUBS_REL / safe


def _read_maybe(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig")


def sub_list(project_root: Path | str) -> Result:
    """Read MANIFEST.md; report each instance's phase/task. Read-only."""
    root = Path(project_root)
    manifest = root / MANIFEST_REL
    if not manifest.is_file():
        return _refuse("TICKET_NOT_FOUND",
                       "no subSaipen MANIFEST.md; run `saipen sub spawn "
                       "<name>` to bootstrap")
    lines = []
    blocked = []
    for line in _read_maybe(manifest).splitlines():
        stripped = line.strip()
        if not stripped.startswith("- "):
            continue
        fields = [f.strip() for f in stripped[2:].split("|")]
        first = fields[0].strip()
        name = first.split(" -- ")[0].strip() if " -- " in first else first
        if not name or " " in name:
            continue
        state_path = root / SUBS_REL / name / "STATE.md"
        phase, task = None, None
        if state_path.is_file():
            from .state import parse_state
            st = parse_state(codec.read_doc(state_path))
            phase, task = st.get("phase"), st.get("task")
        entry = {"name": name, "phase": phase, "task": task}
        if phase == "BLOCKED":
            blocked.append(name)
        lines.append(entry)
    return Result(ok=True, code="SUB_LIST", data={"subs": lines,
                                                  "blocked": blocked})


def sub_status(project_root: Path | str, name: str) -> Result:
    """Read-only peek: OUTBOX ready/draft/blocked/reviewed counts."""
    root = Path(project_root)
    outbox = _sub_dir(root, name) / "kitchen" / "OUTBOX.md"
    if not outbox.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    text = _read_maybe(outbox)
    counts = {}
    for status in ("ready", "draft", "blocked", "reviewed", "stale"):
        counts[status] = text.count(f"**status:** {status}")
    critical = text.count("**critical:** true")
    return Result(ok=True, code="SUB_STATUS", data={"name": name,
                                                    "outbox": counts,
                                                    "critical": critical})


def sub_spawn(project_root: Path | str, name: str, saipen_home: str,
              agent: str | None = None) -> Result:
    """Bootstrap-and-spawn a subSaipen, journaled (PROTOCOL.md section 7).

    Creates `.saipen/extensions/subs/<name>/` with STATE/BOARD/LOG/kitchen/
    OUTBOX from the shipped TEMPLATE, sets the live fields (agent, saipen_home,
    updated, role_revision from the spawned charter), and records the MANIFEST
    line -- all as ONE ordered journaled transaction. Refuses if the instance
    already exists; never overwrites history.
    """
    root = Path(project_root)
    target = _sub_dir(root, name)
    if target.exists():
        return _refuse("ALREADY_CLAIMED",
                       f"subSaipen {name!r} already exists; run "
                       f"`saipen sub clean {name}` first if replacement is "
                       "intended", name=name)

    template_root = Path(saipen_home) / "extensions" / "subs" / "TEMPLATE"
    if not (template_root / "STATE.md").is_file():
        return _refuse("VALIDATION_FAILED",
                       f"saipen_home {saipen_home!r} has no subSaipen TEMPLATE; "
                       "clone/refresh before spawning", name=name)

    manifest = root / MANIFEST_REL
    manifest_text = _read_maybe(manifest)
    if manifest_text and not manifest_text.startswith("# SubSaipen Manifest"):
        manifest_text = "# SubSaipen Manifest\n\n" + manifest_text
    new_manifest = manifest_text.rstrip("\n") + "\n" + \
        f"- {name} -- .saipen/extensions/subs/{name}/\n"
    now = _utc_iso()
    doc = codec.read_document(target / "STATE.md")
    state = codec.read_doc(template_root / "STATE.md")
    state = patch_state(state, {
        "agent": agent or name,
        "saipen_home": saipen_home,
        "updated": now,
    })
    role_revision = _spawn_role_revision(saipen_home, name)
    if role_revision:
        state = patch_state(state, {"role_revision": role_revision})

    targets = [
        {"path": f"{SUBS_REL}/{name}/STATE.md", "role": "state",
         "content": doc.encode(state)},
        {"path": f"{SUBS_REL}/{name}/BOARD.md", "role": "board",
         "content": _read_maybe(template_root / "BOARD.md").encode("utf-8")},
        {"path": f"{SUBS_REL}/{name}/LOG.md", "role": "log",
         "content": _read_maybe(template_root / "LOG.md").encode("utf-8")},
        {"path": f"{SUBS_REL}/{name}/kitchen/OUTBOX.md", "role": "report",
         "content": _read_maybe(template_root / "kitchen" / "OUTBOX.md")
         .encode("utf-8")},
        {"path": MANIFEST_REL, "role": "manifest",
         "content": new_manifest.encode("utf-8")},
    ]
    op_id = "sub-spawn-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, "sub_spawn", agent or name, project_identity(root),
            hash_bytes(("sub_spawn:" + name).encode("utf-8")),
            targets, preconditions={MANIFEST_REL: _hash_or_empty(manifest)})
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SPAWNED", op_id=op_id,
                  changed_files=[t["path"] for t in targets],
                  data={"name": name,
                        "path": f".saipen/extensions/subs/{name}/"})


def _spawn_role_revision(saipen_home: str, name: str) -> str:
    """The derived role revision for a spawned built-in charter (T-542)."""
    try:
        from freshness import compute_role_revision
        charter = Path(saipen_home) / "extensions" / "subs" / f"{name}.md"
        if charter.is_file():
            return compute_role_revision(charter)
    except Exception:  # noqa: BLE001 -- freshness failure means no revision
        pass
    return ""


def _hash_or_empty(path: Path) -> str:
    try:
        return hash_bytes(path.read_bytes())
    except OSError:
        return ""


def sub_pause(project_root: Path | str, name: str) -> Result:
    """Pause a subSaipen: owned-field phase patch -> BLOCKED (PROTOCOL 7)."""
    return _sub_state_patch(project_root, name, {"phase": "BLOCKED",
                                                 "blocker":
                                                 "paused by main agent"},
                            "pause", "SUB_PAUSED", "")


def sub_resume(project_root: Path | str, name: str) -> Result:
    """Resume a subSaipen: clear the paused blocker (PROTOCOL 7)."""
    return _sub_state_patch(project_root, name, {"blocker": ""},
                            "resume", "SUB_RESUMED", "")


def sub_clean_preflight(project_root: Path | str, name: str) -> Result:
    """Evidence-gated removal preflight (PROTOCOL section 7, read-only).

    Delegates the deterministic evidence scan to tools/sub_clean.py's
    sub_clean_blockers. The engine NEVER deletes; this reports every blocker
    and, when clean, leaves removal to the human-confirmed path.
    """
    root = Path(project_root)
    instance = _sub_dir(root, name)
    if not instance.is_dir():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    try:
        from sub_clean import sub_clean_blockers
        blockers = sub_clean_blockers(
            instance,
            root / ".saipen" / "recovery" / "subs" / name)
    except RuntimeError as exc:
        return _refuse("VALIDATION_FAILED", str(exc), name=name)
    if blockers:
        return _refuse("VALIDATION_FAILED", "clean refused; " +
                       "; ".join(blockers[:5]), name=name, blockers=list(
                           blockers))
    return Result(ok=True, code="CLEAN_PREFLIGHT", data={"name": name})


def sub_collect(project_root: Path | str, name: str) -> Result:
    """Read-only collect preflight: freshness gate per ready OUTBOX package
    (PROTOCOL section 6). No semantic acceptance is mechanized -- this checks
    the mechanical freshness bindings (source_head + tree fingerprint + role
    revision) and reports, it never judges a finding."""
    root = Path(project_root)
    outbox = _sub_dir(root, name) / "kitchen" / "OUTBOX.md"
    if not outbox.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    text = _read_maybe(outbox)
    from freshness import (compute_generic_role_revision,
                           compute_source_identity, compute_role_revision)
    try:
        current = compute_source_identity(root)
    except Exception as exc:  # noqa: BLE001
        return _refuse("VALIDATION_FAILED",
                       f"source identity UNKNOWN: {exc}", name=name)
    issues = []
    packages = []
    for block in _outbox_blocks(text):
        entry = {"summary": _field(block, "summary"),
                 "status": _field(block, "status")}
        if _field(block, "status") != "ready":
            packages.append({**entry, "fresh": None})
            continue
        head = _field(block, "source_head")
        tree = _field(block, "source_tree_fingerprint")
        role = _field(block, "role_revision")
        fresh = True
        reasons = []
        if head and current.source_head and head != current.source_head:
            fresh, reasons = False, ["source_head stale"]
        if tree and tree != current.source_tree_fingerprint:
            fresh, reasons = False, ["source_tree_fingerprint differs"]
        if role and not _role_current(saipen_home_of(root), name, role):
            fresh, reasons = False, ["role_revision superseded"]
        if not fresh:
            issues.append(f"{entry['summary'][:40]}: {', '.join(reasons)}")
        packages.append({**entry, "fresh": fresh})
    if issues:
        return _refuse("STALE_STATE",
                       "collect refused; stale package(s): " + "; ".join(
                           issues[:5]), name=name, packages=packages)
    return Result(ok=True, code="COLLECT_PREFLIGHT", data={"name": name,
                                                           "packages":
                                                           packages})


def _field(text: str, key: str) -> str:
    import re
    match = re.search(rf"(?m)^\*\*{re.escape(key)}:\*\*\s*(.*)$", text)
    if match:
        return match.group(1).strip()
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.*)$", text)
    return match.group(1).strip() if match else ""


def _outbox_blocks(text: str) -> list[str]:
    import re
    blocks = []
    current = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current:
                blocks.append("\n".join(current))
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append("\n".join(current))
    return blocks


def _role_current(saipen_home: str, name: str, recorded: str) -> bool:
    try:
        from freshness import compute_role_revision
        charter = Path(saipen_home) / "extensions" / "subs" / f"{name}.md"
        if charter.is_file():
            return compute_role_revision(charter) == recorded
    except Exception:  # noqa: BLE001
        pass
    return True


def saipen_home_of(project_root: Path) -> str:
    from .state import parse_state
    st = parse_state(codec.read_doc(project_root / ".saipen" / "STATE.md"))
    return st.get("saipen_home") or ""


def _sub_state_patch(project_root: Path | str, name: str, owned: dict,
                     operation: str, code: str,
                     log_message: str) -> Result:
    """Journaled owned-field patch on one sub's STATE.md (pause/resume)."""
    root = Path(project_root)
    rel = f"{SUBS_REL}/{name}/STATE.md"
    path = root / rel
    if not path.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    doc = codec.read_document(path)
    old_text = doc.text_norm
    from .state import parse_state
    st = parse_state(old_text)
    if operation == "pause":
        owned = {"phase": "BLOCKED", "blocker": "paused by main agent"}
    elif operation == "resume":
        # resume restores from the sub's own LOG tail; keep phase/next_action
        # as the sub recorded them -- we only clear the paused blocker.
        owned = {"blocker": ""}
    new_text = patch_state(old_text, owned)
    op_id = f"sub-{operation}-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, f"sub_{operation}", "saipen-cli",
            project_identity(root),
            hash_bytes((f"sub_{operation}:{name}").encode("utf-8")),
            [{"path": rel, "role": "state", "content": doc.encode(new_text),
              "before_hash": doc.raw_hash,
              "after_hash": hash_bytes(doc.encode(new_text))}],
            preconditions={rel: doc.raw_hash})
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code=code, op_id=op_id,
                  changed_files=[rel], data={"name": name})
