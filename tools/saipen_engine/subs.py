"""SubSaipen lifecycle operations on the common machinery (NITRO M8, dogfood II).

Mechanizes the DETERMINISTIC parts of the SubSaipen lifecycle (extensions/subs/
PROTOCOL.md section 7): spawn, list, status, adopt, pause, resume, clean
preflight, collect preflight. What Core owns here is the lifecycle boundary --
creating an instance journaled, never overwriting an existing one, recording
the MANIFEST line atomically, and mutating a sub's phase only through
owned-field patches with a resumable trace.

NO semantic acceptance of a finding is mechanized. Core still judges work;
this module guarantees boundaries and mechanics.
"""

from __future__ import annotations

import datetime
import re
from pathlib import Path

from . import codec
from .journal import hash_bytes, run_mutation
from .lock import project_writer_lock
from .paths import project_identity
from .result import Result
from .safeid import prove_inside, validate_safe_id
from .state import patch_state

SUBS_REL = ".saipen/extensions/subs"
MANIFEST_REL = f"{SUBS_REL}/MANIFEST.md"

# Shared files a first spawn copies from saipen_home (PROTOCOL.md section 7).
_BOOTSTRAP_FILES = ("PROTOCOL.md", "README.md", "crew.md")
_BOOTSTRAP_DIRS = ("TEMPLATE", "_shared")


def _utc_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ")


def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime(
        "%d.%m.%y %H:%M")


def _refuse(code: str, detail: str = "", **extra) -> Result:
    return Result(ok=False, code=code, message=detail, data=extra)


def _sub_dir(project_root: Path, name: str) -> Path:
    """The instance dir for a subSaipen, path-safe and inside the owner root.

    The name is validated through the shared safe-ID primitive and the
    resolved path is proven inside `.saipen/extensions/subs/` before use --
    no `..`, separators, drive/absolute forms or control characters can
    escape the owner root (NITRO dogfood II).
    """
    safe = validate_safe_id(name, kind="subSaipen name")
    owner = (Path(project_root) / SUBS_REL).resolve()
    path = Path(project_root) / SUBS_REL / safe
    prove_inside(path, owner, kind="subSaipen instance")
    return path


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


def _bootstrap_needed(root: Path) -> bool:
    """True when the project has no `.saipen/extensions/subs/` at all."""
    return not (root / SUBS_REL).is_dir()


def _bootstrap_targets(saipen_home: str) -> list[dict]:
    """The shared extension files a first spawn must copy (PROTOCOL 7).

    Copy PROTOCOL.md, README.md, crew.md, TEMPLATE/, _shared/inbox.md and all
    built-in sai*.md charters from saipen_home's own extensions/subs/ so the
    downstream project is self-contained after attachment.
    """
    src = Path(saipen_home) / "extensions" / "subs"
    targets = []
    for name in _BOOTSTRAP_FILES:
        f = src / name
        if f.is_file():
            targets.append({"path": f"{SUBS_REL}/{name}",
                            "role": "manifest",
                            "content": f.read_bytes()})
    for sub in ("TEMPLATE", "_shared"):
        d = src / sub
        if d.is_dir():
            for f in sorted(d.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(src).as_posix()
                    targets.append({"path": f"{SUBS_REL}/{rel}",
                                    "role": "manifest",
                                    "content": f.read_bytes()})
    for charter in sorted(src.glob("sai*.md")):
        targets.append({"path": f"{SUBS_REL}/{charter.name}",
                        "role": "manifest",
                        "content": charter.read_bytes()})
    return targets


def sub_spawn(project_root: Path | str, name: str, saipen_home: str,
              agent: str | None = None) -> Result:
    """Bootstrap-and-spawn a subSaipen, journaled (PROTOCOL.md section 7).

    On a project with no `.saipen/extensions/subs/` the first spawn copies the
    shared extension files (PROTOCOL.md, README.md, crew.md, TEMPLATE/,
    _shared/, built-in sai*.md charters) from saipen_home -- one journaled
    admission, so a crash never leaves a MANIFEST entry without its governing
    extension. Then creates `.saipen/extensions/subs/<name>/` with
    STATE/BOARD/LOG/kitchen/OUTBOX from TEMPLATE, sets live fields (agent,
    saipen_home, updated, role_revision), and records the MANIFEST line.
    Refuses if the instance already exists; never overwrites history.
    """
    root = Path(project_root)
    try:
        target = _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
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
    bootstrap = _bootstrap_needed(root)
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

    targets = []
    if bootstrap:
        targets.extend(_bootstrap_targets(saipen_home))
    targets += [
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
                        "path": f".saipen/extensions/subs/{name}/",
                        "bootstrap": bootstrap})


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


def sub_adopt(project_root: Path | str, name: str, saipen_home: str) -> Result:
    """Adopt a subSaipen: revalidate its role under the CURRENT charter
    (PROTOCOL section 6, T-542). Records a fresh role_revision into the sub's
    own STATE and appends a trace -- one journaled operation. This is the
    mechanical `adopt` T-585 named but never implemented: the sub keeps its
    board/log/outbox, only its charter freshness is re-anchored."""
    root = Path(project_root)
    try:
        state_path = _sub_dir(root, name) / "STATE.md"
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    if not state_path.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    role_revision = _spawn_role_revision(saipen_home, name)
    if not role_revision:
        return _refuse("VALIDATION_FAILED",
                       f"no charter {name!r} in saipen_home to adopt against",
                       name=name)
    doc = codec.read_document(state_path)
    rel = f"{SUBS_REL}/{name}/STATE.md"
    new_text = patch_state(doc.text_norm, {
        "role_revision": role_revision,
        "updated": _utc_iso(),
    })
    op_id = "sub-adopt-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, "sub_adopt", "saipen-cli", project_identity(root),
            hash_bytes(("sub_adopt:" + name).encode("utf-8")),
            [{"path": rel, "role": "state", "content": doc.encode(new_text),
              "before_hash": doc.raw_hash,
              "after_hash": hash_bytes(doc.encode(new_text))}],
            preconditions={rel: doc.raw_hash})
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SUB_ADOPTED", op_id=op_id,
                  changed_files=[rel],
                  data={"name": name, "role_revision": role_revision})


def sub_pause(project_root: Path | str, name: str) -> Result:
    """Pause a subSaipen: record prior phase/next_action, then BLOCKED.

    The prior execution state is stored conditionally on the sub's STATE as
    owned pause-lifecycle metadata (`paused_from_phase` / `paused_from_na`)
    so resume can restore it deterministically instead of parsing LOG prose
    (NITRO dogfood II). A trace line is appended to the sub's own LOG.
    """
    root = Path(project_root)
    try:
        state_path = _sub_dir(root, name) / "STATE.md"
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    if not state_path.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    doc = codec.read_document(state_path)
    from .state import parse_state
    st = parse_state(doc.text_norm)
    if st.get("phase") == "BLOCKED":
        return _refuse("VALIDATION_FAILED",
                       f"subSaipen {name!r} is already BLOCKED", name=name)
    rel = f"{SUBS_REL}/{name}/STATE.md"
    new_text = patch_state(doc.text_norm, {
        "phase": "BLOCKED",
        "blocker": "paused by main agent",
        "paused_from_phase": st.get("phase") or "PLAN",
        "paused_from_na": st.get("next_action") or "saipen plan",
        "updated": _utc_iso(),
    })
    targets = [{"path": rel, "role": "state", "content": doc.encode(new_text),
                "before_hash": doc.raw_hash,
                "after_hash": hash_bytes(doc.encode(new_text))}]
    targets.extend(_sub_trace_targets(root, name, "pause",
                                      f"paused by main agent "
                                      f"(from {st.get('phase')})"))
    op_id = "sub-pause-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, "sub_pause", "saipen-cli", project_identity(root),
            hash_bytes(("sub_pause:" + name).encode("utf-8")),
            targets,
            preconditions={rel: doc.raw_hash,
                           f"{SUBS_REL}/{name}/LOG.md":
                           _hash_or_empty(root / f"{SUBS_REL}/{name}/LOG.md")})
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SUB_PAUSED", op_id=op_id,
                  changed_files=[t["path"] for t in targets],
                  data={"name": name,
                        "paused_from_phase": st.get("phase")})


def sub_resume(project_root: Path | str, name: str) -> Result:
    """Resume a subSaipen: prove it was paused by us, restore exact prior
    phase + next_action, clear blocker and pause metadata, append trace.

    Refuses SUB_RESUME if the sub was not paused by the main agent or has no
    recorded prior state -- no fake success (NITRO dogfood II).
    """
    root = Path(project_root)
    try:
        state_path = _sub_dir(root, name) / "STATE.md"
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
    if not state_path.is_file():
        return _refuse("TICKET_NOT_FOUND", f"no subSaipen {name!r}", name=name)
    doc = codec.read_document(state_path)
    from .state import parse_state
    st = parse_state(doc.text_norm)
    if st.get("phase") != "BLOCKED" or \
            st.get("blocker") != "paused by main agent":
        return _refuse("VALIDATION_FAILED",
                       f"subSaipen {name!r} is not paused by the main agent",
                       name=name, phase=st.get("phase"))
    prior_phase = st.get("paused_from_phase")
    prior_na = st.get("paused_from_na")
    if not prior_phase:
        return _refuse("RECOVERY_REQUIRED",
                       f"subSaipen {name!r} has no recorded paused state; "
                       "restore phase/next_action from its LOG tail manually",
                       name=name)
    rel = f"{SUBS_REL}/{name}/STATE.md"
    new_text = patch_state(doc.text_norm, {
        "phase": prior_phase,
        "next_action": prior_na,
        "blocker": "",
        "paused_from_phase": "",
        "paused_from_na": "",
        "updated": _utc_iso(),
    })
    targets = [{"path": rel, "role": "state", "content": doc.encode(new_text),
                "before_hash": doc.raw_hash,
                "after_hash": hash_bytes(doc.encode(new_text))}]
    targets.extend(_sub_trace_targets(root, name, "resume",
                                      f"resumed to {prior_phase}"))
    op_id = "sub-resume-" + __import__("uuid").uuid4().hex[:8]
    with project_writer_lock(root):
        commit = run_mutation(
            root, op_id, "sub_resume", "saipen-cli", project_identity(root),
            hash_bytes(("sub_resume:" + name).encode("utf-8")),
            targets,
            preconditions={rel: doc.raw_hash,
                           f"{SUBS_REL}/{name}/LOG.md":
                           _hash_or_empty(root / f"{SUBS_REL}/{name}/LOG.md")})
    if not commit.get("ok"):
        return _refuse(commit.get("code", "VALIDATION_FAILED"),
                       commit.get("detail", ""), name=name)
    return Result(ok=True, code="SUB_RESUMED", op_id=op_id,
                  changed_files=[t["path"] for t in targets],
                  data={"name": name, "restored_phase": prior_phase,
                        "restored_next_action": prior_na})


def _sub_trace_targets(root: Path, name: str, action: str,
                       message: str) -> list[dict]:
    """One trace line appended to the sub's own LOG (PROTOCOL traceability)."""
    log_rel = f"{SUBS_REL}/{name}/LOG.md"
    log_path = root / log_rel
    text = _read_maybe(log_path)
    from .log import log_tail_event
    tail = log_tail_event(text)
    from .log import build_event
    event, line = build_event(tail, "DEC",
                              f"main agent {action}: {message}",
                              ticket=None, agent="saipen-cli", now=_now())
    new_log = (text.rstrip("\n") + "\n" + line + "\n") if text else \
        ("# Log\n\n" + line + "\n")
    return [{"path": log_rel, "role": "log", "content": new_log.encode("utf-8"),
             "before_hash": _hash_or_empty(log_path),
             "after_hash": hash_bytes(new_log.encode("utf-8"))}]


def sub_clean_preflight(project_root: Path | str, name: str) -> Result:
    """Evidence-gated removal preflight (PROTOCOL section 7, read-only).

    Delegates the deterministic evidence scan to tools/sub_clean.py's
    sub_clean_blockers. The engine NEVER deletes; this reports every blocker
    and, when clean, leaves removal to the human-confirmed path.
    """
    root = Path(project_root)
    try:
        instance = _sub_dir(root, name)
    except ValueError as exc:
        return _refuse("INVALID_ID", str(exc), name=name)
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


def _parse_outbox(text: str) -> tuple[list[str], str | None]:
    """Parse OUTBOX into package blocks. Returns (blocks, malformed_reason).

    An OUTBOX is genuinely empty only when it carries no `## `-headed package
    sections at all (the TEMPLATE header). A nonempty OUTBOX whose sections do
    not parse as packages (`## <ID>: description`) is MALFORMED -- never an
    empty queue (NITRO dogfood II).
    """
    blocks = _outbox_blocks(text)
    if not text.strip():
        return [], None
    if not blocks:
        return [], None  # header-only: an empty queue, not malformed
    package_shaped = [b for b in blocks
                      if re.match(r"^##\s+\S+:\s*\S", b.splitlines()[0])
                      and "**status:**" in b]
    if not package_shaped:
        return [], "nonempty OUTBOX sections do not parse as packages"
    return blocks, None


def sub_collect(project_root: Path | str, name: str | None = None) -> Result:
    """Read-only collect preflight. With no name, aggregates every active
    subSaipen (PROTOCOL: `saipen sub collect` checks every active sub); with a
    name it is a targeted diagnostic. Enforces the complete-package freshness
    contract: a ready package MUST carry source_head + source_tree_fingerprint
    + role_revision, absence REFUSEs PACKAGE_INCOMPLETE, never equals fresh."""
    root = Path(project_root)
    manifest = root / MANIFEST_REL
    if not manifest.is_file():
        return _refuse("TICKET_NOT_FOUND", "no subSaipen MANIFEST.md")
    names = []
    if name is not None:
        names = [name]
    else:
        for line in _read_maybe(manifest).splitlines():
            stripped = line.strip()
            if not stripped.startswith("- "):
                continue
            first = [f.strip() for f in stripped[2:].split("|")][0]
            n = first.split(" -- ")[0].strip() if " -- " in first else first
            if n and " " not in n:
                names.append(n)
    from freshness import compute_source_identity
    try:
        current = compute_source_identity(root)
    except Exception as exc:  # noqa: BLE001
        return _refuse("VALIDATION_FAILED",
                       f"source identity UNKNOWN: {exc}")
    all_packages = []
    all_issues = []
    malformed = []
    for n in names:
        outbox = root / SUBS_REL / n / "kitchen" / "OUTBOX.md"
        if not outbox.is_file():
            all_issues.append(f"{n}: no OUTBOX")
            continue
        text = _read_maybe(outbox)
        blocks, malformed_reason = _parse_outbox(text)
        if malformed_reason:
            malformed.append(n)
            all_packages.append({"name": n, "malformed": malformed_reason})
            continue
        if not blocks:
            all_packages.append({"name": n, "packages": []})
            continue
        packages = []
        for block in blocks:
            entry = {"summary": _field(block, "summary"),
                     "status": _field(block, "status")}
            if _field(block, "status") != "ready":
                packages.append({**entry, "fresh": None})
                continue
            head = _field(block, "source_head")
            tree = _field(block, "source_tree_fingerprint")
            role = _field(block, "role_revision")
            missing = [k for k, v in (
                ("source_head", head), ("source_tree_fingerprint", tree),
                ("role_revision", role)) if not v]
            if missing:
                packages.append({**entry, "fresh": False,
                                 "reason": "missing " + ", ".join(missing)})
                all_issues.append(
                    f"{n}: ready package missing {', '.join(missing)}")
                continue
            fresh = True
            reasons = []
            if current.source_head and head != current.source_head:
                fresh, reasons = False, ["source_head stale"]
            if tree != current.source_tree_fingerprint:
                fresh, reasons = False, ["source_tree_fingerprint differs"]
            if role and not _role_current(saipen_home_of(root), n, role):
                fresh, reasons = False, ["role_revision superseded"]
            if not fresh:
                all_issues.append(f"{n}: {'; '.join(reasons)}")
            packages.append({**entry, "fresh": fresh})
        all_packages.append({"name": n, "packages": packages})
    if malformed:
        return _refuse("MALFORMED_PACKAGE",
                       "malformed OUTBOX: " + ", ".join(malformed),
                       packages=all_packages)
    if all_issues:
        return _refuse("PACKAGE_INCOMPLETE",
                       "collect refused; incomplete/stale package(s): " +
                       "; ".join(all_issues[:5]), packages=all_packages)
    return Result(ok=True, code="COLLECT_PREFLIGHT",
                  data={"names": names, "packages": all_packages})


def _field(text: str, key: str) -> str:
    match = re.search(
        rf"(?m)^[-*\s]*\*\*{re.escape(key)}:\*\*\s*(.*)$", text)
    if match:
        return match.group(1).strip()
    match = re.search(rf"(?m)^{re.escape(key)}:\s*(.*)$", text)
    return match.group(1).strip() if match else ""


def _outbox_blocks(text: str) -> list[str]:
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
