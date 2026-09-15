#!/usr/bin/env python3
"""Re-inject the protocol into every installed agent home when it has moved,
and report the project's current state in one screen.

Two problems, one runner.

The injector copies the protocol into `~/.claude/skills/saipen` and its
siblings rather than linking it, because the readers that matter ignore
junctions (`KNOWLEDGE/traps.md`). Copies go stale silently: nothing in an
installed copy says which revision it came from, so an agent can boot a
protocol several releases behind the clone it was injected from and behave
exactly like one that is current. The standing instruction was "re-run
inject after every git pull", which is a rule with no witness -- the class
this repository keeps closing everywhere else.

So: stamp the installed copy with a digest of what was installed, compare it
against the source on every run, and re-inject only on a real difference.
The digest covers file CONTENT, so a pull that changes nothing changes
nothing, and a local edit to a shipped doc is picked up without a commit.

Second half: an agent driving this project needs to know where it stands
before it acts. That is `saipen status`'s job in a live session, and this is
the same picture for a session that has not started yet.

Never blocks. Exit 0 unless `--check` is asked for and the copies are stale.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from saipen_engine.manifest import (
    CACHE_DIRS,
    GENERATED_SUFFIXES,
    copy_tree_members,
    manifest_source,
)

HOME = Path(__file__).resolve().parent.parent
STAMP = ".saipen_injected"

_REGISTRY_PATH = HOME / "extensions" / "adapters" / "registry.json"
ACTIVATION_TEMPLATE = "saipen/ACTIVATION_BLOCK.md"


def load_adapter_registry() -> dict:
    """The one declarative host adapter authority (SRC-028:R008).

    Distribution targets, freshness surfaces and enforcement capability are
    registry data, never a handwritten list in this module.
    """
    try:
        registry = json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read adapter registry {_REGISTRY_PATH}: {exc}") from exc
    if not isinstance(registry.get("adapters"), list) or not registry["adapters"]:
        raise RuntimeError(f"adapter registry has no adapters: {_REGISTRY_PATH}")
    return registry


def _expand_home(surface: str) -> Path:
    return Path(surface).expanduser()


def registry_home_adapters() -> dict[str, dict]:
    """Map each installed home path (string) to its declaring adapter entry."""
    mapping: dict[str, dict] = {}
    for adapter in load_adapter_registry()["adapters"]:
        for surface in adapter.get("skill_surfaces") or []:
            mapping[str(_expand_home(surface).resolve())] = adapter
    return mapping


def registry_targets() -> list[Path]:
    """Installed skill homes, derived from the registry skill surfaces."""
    seen: dict[str, Path] = {}
    for adapter in load_adapter_registry()["adapters"]:
        for surface in adapter.get("skill_surfaces") or []:
            path = _expand_home(surface)
            seen.setdefault(str(path.resolve()), path)
    return list(seen.values())


# Where the injector installs. Absence is normal -- an agent home that is not
# installed on this machine is skipped, never created. Derived from the
# adapter registry; the old four-entry handwritten list is gone.
TARGETS = registry_targets()

# Ordered home -> adapter lookup for freshness reporting.
_HOME_ADAPTERS = registry_home_adapters()

# How many divergent files `--check` names before it stops. Enough to see the
# shape of a drift, few enough that a never-installed home does not print two
# hundred lines and bury the one that matters.
DRIFT_REPORT_LIMIT = 12


def _manifest_source(raw: object) -> Path:
    return manifest_source(HOME, raw)


def _is_within(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _manifest_surface() -> list[tuple[Path, bool]]:
    """Return exactly what injectors copy, derived from the runtime manifest."""
    manifest_path = HOME / "saipen" / "MANIFEST.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot read runtime manifest {manifest_path}: {exc}") from exc

    try:
        trees = manifest["copy_trees"]
        entries = manifest["files"]
        if not isinstance(trees, list) or not trees or not isinstance(entries, list):
            raise TypeError("copy_trees/files must be nonempty arrays")
        surface: list[tuple[Path, bool]] = []
        tree_roots: list[Path] = []
        for entry in trees:
            source, _members = copy_tree_members(HOME, entry["src"])
            surface.append((source, True))
            tree_roots.append(source)
        for entry in entries:
            if entry.get("required") is not True:
                continue
            source = _manifest_source(entry["src"])
            if any(_is_within(source, tree) for tree in tree_roots):
                continue
            if not source.is_file() or source.is_symlink():
                raise RuntimeError(f"runtime manifest file missing or symlinked: {entry['src']}")
            surface.append((source, False))
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"runtime manifest shape invalid: {exc}") from exc
    return surface


def _content_bytes(path: Path) -> bytes:
    """The file's CONTENT, with line endings normalised to LF (T-1253).

    The digest is a content digest -- that is what it has always claimed to be
    -- and a line ending is transport, not content. It has to be, because the
    two sides of the comparison come through different transports: the clone
    holds LF while the snapshot git produces for the scheduled injector holds
    CRLF, so `saipen/BOOT.md` is 4972 bytes here and 5063 bytes there with not
    one character of difference. Hashing raw bytes made a home refreshed
    seconds ago report STALE forever, which is the same as having no witness.

    A file that is not valid UTF-8 is hashed byte-for-byte: it is not text, so
    there are no line endings to normalise and guessing would be worse.
    """
    raw = path.read_bytes()
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _digest() -> str:
    """Content digest of the shipped surface, path-order stable."""
    h = hashlib.sha256()

    def frame(kind: bytes, path: Path, payload: bytes = b"") -> None:
        relative = path.relative_to(HOME.resolve()).as_posix().encode("utf-8")
        for part in (kind, relative, payload):
            h.update(len(part).to_bytes(8, "big"))
            h.update(part)

    def generated(path: Path) -> bool:
        # Same rule as the copier, from the same constant: a file the
        # injector would never ship must not move the digest that decides
        # whether what it shipped is current.
        relative = path.relative_to(HOME.resolve())
        return bool(CACHE_DIRS.intersection(relative.parts)) or (
            path.suffix in GENERATED_SUFFIXES
        )

    for path, is_tree in _manifest_surface():
        if is_tree:
            members = sorted(
                path.rglob("*"),
                key=lambda item: item.relative_to(HOME.resolve()).as_posix().encode(),
            )
        else:
            members = [path]
        for member in members:
            if generated(member):
                continue
            if member.is_symlink():
                raise RuntimeError(
                    f"runtime manifest surface contains unsupported symlink: {member}"
                )
            if member.is_dir():
                frame(b"D", member)
            elif member.is_file():
                frame(b"F", member, _content_bytes(member))
            else:
                raise RuntimeError(f"runtime manifest surface contains unsupported entry: {member}")
    return h.hexdigest()[:16]


def installed_relpath(source_relative: str) -> str:
    """Where a shipped source path lands inside an installed agent home.

    The injectors strip exactly one leading `saipen/` component and keep
    everything else: `saipen/BOOT.md` installs as `BOOT.md`, `saipen/phases/`
    as `phases/`, while `tools/`, `bootstrap/` and `extensions/` keep theirs.
    """
    if source_relative.startswith("saipen/"):
        return source_relative[len("saipen/") :]
    return source_relative


def surface_drift(target: Path, limit: int | None = None) -> list[tuple[str, str, str]]:
    """Which shipped files differ in `target`, as (path, source, installed).

    A digest says a home is stale. It cannot say what an agent stranded by that
    home is actually reading, and "stale" with no file name is the same
    diagnosis the incident in T-1249 already produced: the agent read a copy
    that disagreed with the repository, grepped for a rule that had moved, and
    answered from the older generation without anything naming the divergence.

    Comparison runs through `_content_bytes`, the same normaliser the digest
    uses, or every text file on the surface would read as divergent across the
    CRLF boundary T-1253 closed -- `saipen/BOOT.md` is 4972 bytes in the clone
    and 5063 in the snapshot with no character of difference. Byte counts are
    reported RAW, because that is what a human comparing two files sees.
    """
    findings: list[tuple[str, str, str]] = []
    root = HOME.resolve()
    for path, is_tree in _manifest_surface():
        members = sorted(path.rglob("*")) if is_tree else [path]
        for member in members:
            if not member.is_file() or member.is_symlink():
                continue
            relative = member.relative_to(root).as_posix()
            if CACHE_DIRS.intersection(member.relative_to(root).parts) or (
                member.suffix in GENERATED_SUFFIXES
            ):
                continue
            landed = target / installed_relpath(relative)
            if not landed.is_file():
                findings.append((relative, f"{member.stat().st_size}B", "missing"))
            elif _content_bytes(landed) != _content_bytes(member):
                findings.append(
                    (relative, f"{member.stat().st_size}B", f"{landed.stat().st_size}B")
                )
            if limit is not None and len(findings) >= limit:
                return findings
    return findings


def read_stamp(target: Path) -> dict | None:
    """The freshness record beside an installed protocol copy, or None.

    Two shapes are accepted on purpose. The original stamp was a bare digest
    line, and copies written by an older injector are still on disk; refusing
    to read them would turn every pre-existing install into "no record at all",
    which is the very blindness the stamp exists to remove.
    """
    stamp = target / STAMP
    if not stamp.is_file():
        return None
    raw = stamp.read_text(encoding="utf-8").strip()
    if not raw:
        return None
    if raw.startswith("{"):
        try:
            record = json.loads(raw)
        except ValueError:
            return None
        return record if isinstance(record, dict) and record.get("digest") else None
    return {"digest": raw}


def _installed(target: Path) -> str | None:
    record = read_stamp(target)
    return record.get("digest") if record else None


def _source_head() -> str | None:
    rc, out = _run(["git", "rev-parse", "HEAD"])
    return out.strip() if rc == 0 and out.strip() else None


def _run(cmd: list[str], cwd: Path = HOME, env: dict | None = None) -> tuple[int, str]:
    kwargs = dict(capture_output=True, text=True, errors="replace", timeout=300)
    if env is not None:
        kwargs["env"] = env
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    try:
        r = subprocess.run(cmd, cwd=cwd, **kwargs)
    except (OSError, subprocess.SubprocessError) as exc:
        return 1, f"{type(exc).__name__}: {exc}"
    return r.returncode, (r.stdout + r.stderr).strip()


def inject() -> tuple[bool, str]:
    """Run the platform injector. Returns (ok, output tail)."""
    if os.name == "nt":
        cmd = [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-File",
            str(HOME / "bootstrap" / "inject.ps1"),
        ]
    else:
        cmd = ["bash", str(HOME / "bootstrap" / "inject.sh")]
    # The installer renders the installed launcher with the SELECTED Python;
    # hand it the interpreter running this runner.
    rc, out = _run(cmd, env={**os.environ, "SAIPEN_PYTHON": sys.executable})
    return rc == 0, "\n".join(out.splitlines()[-12:])


def stamp_targets(digest: str, source_head: str | None = None) -> list[str]:
    """Write the digest into every target that actually exists.

    Only existing targets are stamped: creating one here would install a
    protocol into an agent home the user never set up.
    """
    # T-1249: a digest alone cannot tell a BOOTING agent anything -- comparing
    # it needs the clone, which a consumer machine may not have. The install
    # time and source head can be read on their own, so an agent that loads a
    # copy last refreshed days ago can say so instead of silently running an
    # old protocol. That was the actual incident: an agent read a pre-W4 CORE.md
    # looking for a shortcut table that had moved, and had no way to know.
    record = {
        "digest": digest,
        "installed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    # T-1255: the scheduled injector runs out of a `git archive` extraction,
    # which is not a repository, so asking git there silently drops the head on
    # the one path that matters. The runner already PROVED the head before it
    # published the snapshot, so it passes that instead of having the stamper
    # re-derive it from a tree that cannot answer. An unavailable head is
    # omitted, never guessed.
    head = source_head or _source_head()
    if head:
        record["source_head"] = head
    payload = json.dumps(record, indent=2, sort_keys=True) + "\n"
    done = []
    for t in TARGETS:
        if t.is_dir():
            (t / STAMP).write_text(payload, encoding="utf-8")
            # Every target's leaf is `saipen`, so the leaf names nothing.
            # The agent home is what distinguishes them.
            done.append(next((p for p in t.parts if p.startswith(".")), str(t)))
    return done


# ---------------------------------------------------------------------------
# Distribution freshness projection (T-1271)
# ---------------------------------------------------------------------------
#
# Every installed home already carries a stamp naming the source head it was
# built from, and the scheduled runner already writes why a run published
# nothing. Both were unreadable from the project: `saipen status` said nothing
# about injection, so "does an installed agent home run current SAIPEN" could
# only be answered by opening a log under LOCALAPPDATA. The guard that stalls
# distribution on a dirty source is correct -- it refuses to publish unproven
# bytes -- but one uncommitted edit stalls it indefinitely and only that log
# said so.
#
# Everything below READS. It opens the stamps, a bounded tail of the runner's
# log, and git; it creates nothing, stamps nothing, and never triggers a run.

#: Bytes of the runner's log to read from the end. The log grows forever and
#: only the newest run can explain today's staleness.
LOG_TAIL_BYTES = 65536

_RUN_START = "=== saipen scheduled inject run="
_RUN_END = "=== end rc="
#: The runner prefixes every line with `YYYY-MM-DD HH:MM:SS `. Splitting on
#: the first space alone leaves the clock glued to the payload, which is how
#: `SKIP: DIRTY_SOURCE` read as `09:46:00 SKIP: ...` and matched nothing.
_LOG_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s+")


def scheduler_log() -> Path | None:
    """The scheduled injector's log, or None where there is no scheduler.

    The runner is Windows-only today (`bootstrap/schedule-run.ps1` writes to
    `%LOCALAPPDATA%/saipen/inject.log`). Absence is a normal answer on every
    other host and must never read as a failure.
    """
    base = os.environ.get("LOCALAPPDATA")
    if not base:
        return None
    path = Path(base) / "saipen" / "inject.log"
    return path if path.is_file() else None


def last_inject_run(log: Path | None = None) -> dict | None:
    """The newest complete-or-partial run block in the runner's log.

    Returns None when there is no log at all. A run that is still in flight
    has no `rc`, which is reported as unknown rather than as a success.
    """
    log = log if log is not None else scheduler_log()
    if log is None or not log.is_file():
        return None
    try:
        size = log.stat().st_size
        with log.open("rb") as handle:
            if size > LOG_TAIL_BYTES:
                handle.seek(size - LOG_TAIL_BYTES)
            raw = handle.read()
    except OSError:
        return None
    lines = raw.decode("utf-8", errors="replace").splitlines()
    start = None
    for index in range(len(lines) - 1, -1, -1):
        if _RUN_START in lines[index]:
            start = index
            break
    if start is None:
        return None
    block = lines[start:]
    run: dict = {"rc": None, "skip": None, "head": None, "dirty": [], "at": ""}
    stamp, _, _ = block[0].partition(_RUN_START)
    run["at"] = stamp.strip()
    for line in block:
        body = _LOG_STAMP.sub("", line.strip()).strip()
        if body.startswith("SKIP:"):
            run["skip"] = body[len("SKIP:") :].strip()
        elif body.startswith("dirty:"):
            detail = body[len("dirty:") :].strip()
            if detail:
                run["dirty"].append(detail)
        elif "head=" in body:
            run["head"] = body.split("head=", 1)[1].split()[0]
        elif body.startswith(_RUN_END):
            tail = body[len(_RUN_END) :].strip().rstrip("=").strip()
            try:
                run["rc"] = int(tail)
            except ValueError:
                run["rc"] = None
    return run


# ---------------------------------------------------------------------------
# Surface freshness from the adapter registry (SRC-030 Part 12)
# ---------------------------------------------------------------------------
#
# A stamp alone proves the SKILL copy. A declared surface that IS installed
# must also be current; an installed-but-unobservable surface is UNKNOWN and
# never reads as fresh.


def activation_template_path() -> Path:
    """The canonical activation template for THIS home, layout-aware.

    The registry names the template by its SOURCE-relative path
    (`saipen/ACTIVATION_BLOCK.md`). In the repository clone that path exists
    verbatim; in an installed agent home the injector has already stripped the
    leading `saipen/` component (see `installed_relpath`), so the same relative
    string resolved naively points at `<home>/saipen/ACTIVATION_BLOCK.md` --
    which never exists -- and every distribution/instruction report on an
    installed home failed with FileNotFoundError (T-1323). Resolve through the
    one owner: verbatim when present, else the installed landing path.
    """
    registry = load_adapter_registry()
    relative = registry.get("activation_template") or ACTIVATION_TEMPLATE
    source = HOME / relative
    if source.is_file():
        return source
    landed = HOME / installed_relpath(relative)
    return landed if landed.is_file() else source


def activation_parity(target: Path) -> dict:
    """Deterministic source -> installed mapping proof for the template.

    Proves the chain the release certification depends on: the manifest names
    the template, it resolves to bytes in THIS home, the injector maps it to
    `installed_relpath`, and the installed bytes in `target` equal the source
    bytes. Any missing leg is reported with its exact path -- never a silent
    pass.
    """
    source = activation_template_path()
    if not source.is_file():
        return {"ok": False, "code": "SOURCE_MISSING", "source": str(source)}
    relative = (load_adapter_registry().get("activation_template") or ACTIVATION_TEMPLATE)
    landed = Path(target) / installed_relpath(relative)
    if not landed.is_file():
        return {
            "ok": False,
            "code": "INSTALLED_MISSING",
            "source": str(source),
            "installed": str(landed),
        }
    if _content_bytes(source) != _content_bytes(landed):
        return {
            "ok": False,
            "code": "INSTALLED_DRIFT",
            "source": str(source),
            "installed": str(landed),
        }
    return {
        "ok": True,
        "code": "ACTIVATION_PARITY",
        "source": str(source),
        "installed": str(landed),
    }


def rendered_activation_block(skill_install_dir: Path) -> str:
    """The canonical block as the injector would install it for this home."""
    template = activation_template_path().read_text(encoding="utf-8")
    return template.replace("{{SAIPEN_HOME}}", str(skill_install_dir))


def _extract_block(text: str) -> str | None:
    match = re.search(r"<!-- SAIPEN:BEGIN -->.*?<!-- SAIPEN:END -->", text, re.DOTALL)
    if not match:
        return None
    return match.group(0).replace("\r\n", "\n").strip()


def _activation_home(template_block: str, installed_block: str) -> str | None:
    """The SAIPEN home an installed block names, or None if it is not this
    template.

    `{{SAIPEN_HOME}}` is a VARIABLE. Matching the rendered block byte-for-byte
    treats one particular substitution as part of the contract, which is how a
    healthy install reported stale forever (T-1337): a block pointing at the
    source clone differs from a block pointing at the installed skill copy in
    the home and nowhere else, and no amount of re-injection can make the two
    spellings equal. Split on the placeholder, require every literal segment to
    match in order, and require every gap to carry the SAME home.
    """
    segments = template_block.split("{{SAIPEN_HOME}}")
    if len(segments) == 1:
        return "" if installed_block == template_block else None
    home: str | None = None
    rest = installed_block
    for index, segment in enumerate(segments):
        if index == 0:
            if not rest.startswith(segment):
                return None
            rest = rest[len(segment) :]
            continue
        if index == len(segments) - 1:
            if not rest.endswith(segment):
                return None
            candidate = rest[: len(rest) - len(segment)]
        else:
            position = rest.find(segment)
            if position < 0:
                return None
            candidate = rest[:position]
            rest = rest[position + len(segment) :]
        if home is None:
            home = candidate
        elif home != candidate:
            return None
    return home


def _names_a_real_home(home: str) -> bool:
    """Does the block's home actually resolve to protocol documents?

    This is the half of the contract that matters and that the byte comparison
    never checked: a block is useful when the path it sends every agent to
    holds `BOOT.md`. A pointer at a home that does not exist is stale no matter
    how current its prose is.
    """
    if not home.strip():
        return False
    try:
        base = Path(home.strip())
        return (base / "BOOT.md").is_file() or (base / "saipen" / "BOOT.md").is_file()
    except OSError:
        return False


def instruction_status(adapter: dict, skill_install_dir: Path) -> str:
    """current | stale | absent for the always-on instruction block.

    Current means BOTH halves: the block's prose is this generation's template,
    and the home it names resolves to real protocol documents. Which home that
    is belongs to whoever installed it -- the installed skill copy the injector
    writes, or a source clone an operator deliberately points at so the agent
    always reads live documents. Reporting the second as stale forever taught
    the operator to ignore the freshness surface, which is how a genuine
    staleness gets ignored too.
    """
    rendered = rendered_activation_block(skill_install_dir)
    expected = _extract_block(rendered)
    template_block = _extract_block(activation_template_path().read_text(encoding="utf-8"))
    for surface in adapter.get("instruction_surfaces") or []:
        path = _expand_home(surface)
        if not path.is_file():
            continue
        try:
            installed = _extract_block(_content_bytes(path).decode("utf-8", errors="replace"))
        except OSError:
            return "unknown"
        if installed is None:
            return "stale"
        if expected is not None and installed == expected.replace("\r\n", "\n").strip():
            return "current"
        if template_block is not None:
            named = _activation_home(
                template_block.replace("\r\n", "\n").strip(), installed
            )
            if named is not None and _names_a_real_home(named):
                return "current"
        return "stale"
    return "absent"


def hook_status(adapter: dict) -> str:
    """current | stale | absent | unknown for the installed blocking hook.

    A registry-declared LEGACY surface that still holds a copy of the artifact
    reads STALE: the supported OpenCode runtime discovers both the singular
    `plugin/` and the plural `plugins/` global plugin directories, so a stale
    copy there would load the same guard hook twice. Capability truth is not
    enough -- a duplicate load is not fresh.
    """
    surface = adapter.get("hook_install_surface")
    artifact = adapter.get("hook_artifact")
    for legacy in adapter.get("legacy_hook_surfaces") or []:
        if isinstance(legacy, str) and legacy and _expand_home(legacy).is_file():
            return "stale"
    if not surface or not artifact:
        return "absent"
    installed_path = _expand_home(surface)
    if not installed_path.is_file():
        return "absent"
    if adapter.get("hook_installer"):
        from install_host_guard import install

        try:
            status = install(adapter["id"], _expand_home("~"), HOME, check=True)
        except (OSError, ValueError, KeyError):
            return "unknown"
        return "current" if status["current"] else "stale"
    try:
        installed = _content_bytes(installed_path)
        shipped = _content_bytes(HOME / artifact)
    except OSError:
        # Installed but unobservable is UNKNOWN, never fresh (SRC-030 Part 12).
        return "unknown"
    return "current" if installed == shipped else "stale"


def home_surface_status(target: Path) -> dict:
    """Per-declared-surface freshness for one installed home."""
    adapter = _HOME_ADAPTERS.get(str(target.resolve()))
    if adapter is None:
        return {"adapter": None, "surfaces": {}, "ok": True}
    surfaces: dict[str, str] = {}
    # The skill copy's freshness is the stamp comparison already reported;
    # declared non-skill surfaces are checked here.
    if "instruction" in (adapter.get("freshness_surfaces") or []):
        surfaces["instruction"] = instruction_status(adapter, target)
    if "hook" in (adapter.get("freshness_surfaces") or []):
        surfaces["hook"] = hook_status(adapter)
    problems = [name for name, state in surfaces.items() if state in ("stale", "unknown")]
    return {
        "adapter": adapter.get("id"),
        "surfaces": surfaces,
        "ok": not problems,
        "problems": problems,
    }


def distribution_report(source_head: str | None = None) -> dict:
    """Read-only answer to: do the installed agent homes run current SAIPEN?

    `installed` counts only homes that exist -- an agent this machine never set
    up is not stale, it is absent. A home whose stamp predates the injector's
    head-recording carries no `source_head`; that is reported as UNKNOWN, never
    silently counted fresh, because a copy that cannot say what it is built
    from is exactly the case the stamp exists to expose.
    """
    head = source_head or _source_head()
    homes: list[dict] = []
    for target in TARGETS:
        if not target.is_dir():
            continue
        name = next((p for p in target.parts if p.startswith(".")), str(target))
        record = read_stamp(target) or {}
        carried = record.get("source_head")
        surface = home_surface_status(target)
        homes.append(
            {
                "home": name,
                "adapter": surface["adapter"],
                "source_head": carried,
                "installed_at": record.get("installed_at"),
                "stale": (bool(head) and carried != head) or not surface["ok"],
                "unknown": not carried,
                "surfaces": surface["surfaces"],
                "surface_problems": surface.get("problems", []),
            }
        )
    heads = [h for h in (item["source_head"] for item in homes) if h]
    newest = None
    if homes:
        dated = [item for item in homes if item["installed_at"] and item["source_head"]]
        if dated:
            newest = max(dated, key=lambda item: item["installed_at"])["source_head"]
        elif heads:
            newest = heads[0]
    run = last_inject_run()
    blocked = None
    if run is not None and (run.get("skip") or (run.get("rc") not in (0, None))):
        blocked = run.get("skip") or f"rc={run.get('rc')}"
    stale = [item["home"] for item in homes if item["stale"]]
    surface_unknown = len(
        [item for item in homes if any(s == "unknown" for s in item["surfaces"].values())]
    )
    return {
        "source_head": head,
        "installed": len(homes),
        "stale": len(stale),
        "stale_homes": stale,
        "unknown": len([item for item in homes if item["unknown"]]),
        "surface_unknown": surface_unknown,
        "newest_installed_head": newest,
        "homes": homes,
        "blocked": blocked,
        "blocking_paths": (run or {}).get("dirty") or [],
        "last_run_at": (run or {}).get("at") or None,
        "scheduler_log": str(scheduler_log()) if scheduler_log() else None,
        # AC-04: a fully current set is a POSITIVE answer, not an empty
        # section. "Nothing printed" and "everything is current" have to be
        # distinguishable or the report is only trustworthy when it complains.
        # SRC-030 Part 12: an installed-but-unobservable surface is UNKNOWN,
        # so a home can read stale with a perfectly current stamp.
        "fresh": bool(homes) and not stale and not blocked and surface_unknown == 0,
    }


def distribution_line(report: dict) -> str:
    """One operator sentence from `distribution_report`. Never a verdict."""
    if not report["installed"]:
        return "distribution: no installed agent home on this machine"
    if report["fresh"]:
        return (
            f"distribution: {report['installed']} home(s) current at "
            f"{str(report['source_head'] or '?')[:12]}"
        )
    parts = [
        f"distribution: {report['stale']} of {report['installed']} home(s) stale",
        f"newest installed head {str(report['newest_installed_head'] or 'unknown')[:12]}",
        f"source head {str(report['source_head'] or 'unknown')[:12]}",
    ]
    if report["unknown"]:
        parts.append(f"{report['unknown']} home(s) carry no head")
    if report["blocked"]:
        detail = f"injection blocked: {report['blocked']}"
        if report["blocking_paths"]:
            shown = ", ".join(report["blocking_paths"][:3])
            more = len(report["blocking_paths"]) - 3
            detail += f" ({shown}{f', +{more} more' if more > 0 else ''})"
        parts.append(detail)
    return " -- ".join(parts)


def state_report() -> list[str]:
    """The picture an agent needs before it acts. Facts only, no verdict."""
    lines = []
    version = (
        (HOME / "VERSION").read_text(encoding="utf-8").strip()
        if (HOME / "VERSION").is_file()
        else "?"
    )

    rc, head = _run(["git", "rev-parse", "--short", "HEAD"])
    head = head if rc == 0 else "no git"
    rc, counts = _run(["git", "rev-list", "--left-right", "--count", "origin/main...HEAD"])
    drift = ""
    if rc == 0 and counts:
        behind, ahead = [*counts.split(), "0", "0"][:2]
        if behind != "0" or ahead != "0":
            drift = f", {behind} behind / {ahead} ahead of origin/main"
    rc, dirty = _run(["git", "status", "--porcelain"])
    if rc == 0:
        n = len([ln for ln in dirty.splitlines() if ln.strip()])
        drift += f", {n} uncommitted file(s)" if n else ", tree clean"
    lines.append(f"protocol: v{version} @ {head}{drift}")

    state = HOME / ".saipen" / "STATE.md"
    if state.is_file():
        fields = {}
        for ln in state.read_text(encoding="utf-8-sig").splitlines():
            if ":" in ln and not ln.startswith("-"):
                k, _, v = ln.partition(":")
                fields[k.strip()] = v.strip().strip('"')
        lines.append(
            f"state: phase {fields.get('phase', '?')}, "
            f"task {fields.get('task', '?')}, "
            f"next_action {fields.get('next_action', '?')[:90]}"
        )

    board = HOME / ".saipen" / "BOARD.md"
    if board.is_file():
        section, counts = None, {}
        for ln in board.read_text(encoding="utf-8-sig").splitlines():
            if ln.startswith("## "):
                section = ln[3:].strip()
            elif ln.startswith("- [") and section:
                counts[section] = counts.get(section, 0) + 1
        lines.append("board: " + ", ".join(f"{k} {v}" for k, v in counts.items()) or "board: empty")

    rc, out = _run([sys.executable, str(HOME / "tools" / "validate.py")])
    tail = [ln for ln in out.splitlines() if ln.startswith(("Validation", "FAIL"))]
    lines.append("validator: " + (tail[-1] if tail else f"exit {rc}"))
    return lines


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--check", action="store_true", help="report staleness and exit 1 if stale; inject nothing"
    )
    ap.add_argument(
        "--force", action="store_true", help="re-inject even when the digest already matches"
    )
    ap.add_argument(
        "--quiet-when-fresh",
        action="store_true",
        help="print nothing when nothing was stale (for timers)",
    )
    ap.add_argument(
        "--stamp-only",
        action="store_true",
        help="write the freshness stamp into every installed target; copy nothing",
    )
    ap.add_argument(
        "--source-head",
        default=None,
        help="record this revision in the stamp (for a source tree with no git)",
    )
    args = ap.parse_args(argv)

    try:
        digest = _digest()
    except RuntimeError as exc:
        print(f"INJECT FAILED (runtime manifest): {exc}")
        return 1 if args.check else 0
    present = [t for t in TARGETS if t.is_dir()]
    stale = [t for t in present if _installed(t) != digest]

    if not present:
        print("no agent home installed on this machine -- nothing to inject")
        return 0

    if args.stamp_only:
        # T-1252: `bootstrap/inject.ps1` is the injector the scheduled task
        # runs, and it copies the protocol without writing the stamp this
        # module compares against -- so every refreshed home read as
        # "installed unstamped" forever and a genuinely drifted copy was
        # indistinguishable from a current one. The digest has exactly ONE
        # owner (`_digest`), so the PowerShell path calls back here rather
        # than growing a second implementation that would drift from it.
        stamped = stamp_targets(digest, args.source_head)
        for t in stamped:
            print(f"stamped: {t} at {digest}")
        if not stamped:
            print("no agent home installed on this machine -- nothing to stamp")
        return 0

    if args.check:
        for t in stale:
            print(f"STALE: {t} (installed {_installed(t) or 'unstamped'}, source {digest})")
            # A digest names no file. Name them: an agent stranded by a stale
            # copy needs to know WHAT it is reading, and one path with two byte
            # counts is the whole diagnosis. Bounded, because a home that was
            # never installed would otherwise print the entire surface.
            drift = surface_drift(t, limit=DRIFT_REPORT_LIMIT + 1)
            for relative, source_size, landed in drift[:DRIFT_REPORT_LIMIT]:
                print(f"    {relative}: source {source_size}, installed {landed}")
            if len(drift) > DRIFT_REPORT_LIMIT:
                print(f"    ... and more; {DRIFT_REPORT_LIMIT} shown")
            if not drift:
                print("    no file differs -- the stamp is stale, the content is not")
        if not stale:
            print(f"fresh: {len(present)} agent home(s) at {digest}")
        return 1 if stale else 0

    if args.quiet_when_fresh:
        if stale or args.force:
            why = (
                "forced"
                if args.force and not stale
                else f"{len(stale)} of {len(present)} home(s) stale"
            )
            ok, tail = inject()
            if ok:
                stamp_targets(digest)
            else:
                print(f"INJECT FAILED ({why}):\n{tail}")
        return 0

    if stale or args.force:
        why = (
            "forced"
            if args.force and not stale
            else f"{len(stale)} of {len(present)} home(s) stale"
        )
        ok, tail = inject()
        if not ok:
            print(f"INJECT FAILED ({why}):\n{tail}")
            return 0  # never block a timer on a failed inject
        stamped = stamp_targets(digest)
        print(f"injected ({why}) -> {digest}; stamped: {', '.join(stamped)}")
    elif not args.quiet_when_fresh:
        print(f"fresh: {len(present)} agent home(s) at {digest}")

    if stale or args.force or not args.quiet_when_fresh:
        for ln in state_report():
            print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
