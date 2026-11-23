"""Conservative candidate discovery, never proof that a subset is complete."""

from __future__ import annotations

import re
from pathlib import Path

SCRIPT_SUFFIXES = {".py", ".ps1", ".sh", ".cmd", ".bat", ".js", ".cjs", ".mjs"}
SOURCE_SUFFIXES = SCRIPT_SUFFIXES | {".cpp", ".cc", ".c", ".h", ".hpp", ".json", ".txt"}


def affected(root: Path) -> dict:
    from .suite_record import _git, load_declaration, newest_record

    declaration, error = load_declaration(root)
    if error or declaration is None:
        raise LookupError(error or "no suite is declared for this project")
    root = root.resolve()
    entrypoints = set()
    repositories = {root}
    for word in declaration["command"]:
        path = root / word.replace("\\", "/")
        if path.suffix.lower() not in SCRIPT_SUFFIXES or not path.resolve().is_relative_to(root):
            continue
        entrypoints.add(path.resolve().relative_to(root).as_posix())
        # BZDECOMP ignores vrv/, whose suite belongs to a separate nested
        # repository. Query its Git owner explicitly rather than silently
        # reporting only the enclosing documentation repository's changes.
        owner = _git(path.parent, "rev-parse", "--show-toplevel")
        if owner:
            candidate = Path(owner.decode("utf-8", "surrogateescape").strip()).resolve()
            if candidate.is_relative_to(root):
                repositories.add(candidate)

    def paths(raw):
        return {
            name.decode("utf-8", "surrogateescape").replace("\\", "/")
            for name in raw.split(b"\0") if name
            and not name.startswith((b".saipen/", b".git/"))
        }

    changed_paths, all_paths, untracked_paths = set(), set(), set()
    deltas = []
    for repository in sorted(repositories):
        changed = _git(repository, "diff", "HEAD", "--name-only", "-z", "--")
        untracked = _git(repository, "ls-files", "--others", "--exclude-standard", "-z")
        tracked = _git(repository, "ls-files", "-z")
        delta = _git(repository, "diff", "HEAD", "--no-ext-diff", "--unified=0", "--")
        if any(value is None for value in (changed, untracked, tracked, delta)):
            raise LookupError(f"affected needs a readable Git worktree with HEAD: {repository}")
        prefix = repository.relative_to(root)
        changed_paths.update((prefix / name).as_posix() for name in paths(changed))
        untracked_paths.update((prefix / name).as_posix() for name in paths(untracked))
        all_paths.update((prefix / name).as_posix() for name in paths(tracked))
        deltas.append(delta.decode("utf-8", "replace"))
    changed_paths.update(untracked_paths)
    all_paths.update(untracked_paths)
    # Both sides matter: a removed call can break a fixture just as an added
    # call can. Identifiers also catch row-count/table constants (kLINE_COUNT).
    diff_lines = "\n".join(
        line[1:] for line in "\n".join(deltas).splitlines()
        if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))
    )
    for name in sorted(untracked_paths):
        path = root / name
        if (path.suffix.lower() in SOURCE_SUFFIXES and path.is_file()
                and path.resolve().is_relative_to(root.resolve())):
            diff_lines += "\n" + path.read_text(encoding="utf-8", errors="replace")
    symbols = set(re.findall(r"\b[A-Za-z_]\w*(?:::[A-Za-z_]\w*)+\b", diff_lines))
    symbols.update(re.findall(r"\b(?:k[A-Z]\w*|[A-Z][A-Z_0-9]{2,})\b", diff_lines))
    needles = {Path(path).name for path in changed_paths} | symbols
    command_dirs = {Path(name).parent.as_posix() for name in entrypoints} - {"."}
    contents = {}
    skipped = []
    for name in sorted(all_paths):
        path = root / name
        if path.suffix.lower() not in SOURCE_SUFFIXES:
            continue
        parts = [part.lower() for part in Path(name).parts]
        is_test = any("test" in part or "fixture" in part for part in parts)
        in_suite = any(name.casefold().startswith(directory.casefold() + "/")
                       for directory in command_dirs)
        if not (is_test or in_suite):
            continue
        try:
            if (path.is_symlink() or not path.is_file()
                    or not path.resolve().is_relative_to(root.resolve())):
                skipped.append(name)
                continue
            contents[name] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            skipped.append(name)
    selected = {}
    for name, source in contents.items():
        reasons = sorted(needle for needle in needles if needle and needle in source)
        if name in changed_paths:
            reasons.append("changed test/fixture")
        if reasons:
            selected[name] = reasons
    # A test can reference the fixture rather than the changed production
    # file. Follow that dependency without pretending static text is complete.
    while True:
        additions = {}
        for name, source in contents.items():
            if name in selected:
                continue
            references = [path for path in selected if Path(path).name in source]
            if references:
                additions[name] = references
        if not additions:
            break
        selected.update(additions)
    newest = newest_record(root)
    record = newest["record"] if newest else {}
    duration = record.get("duration_s")
    runner_sources = [contents[name] for name in entrypoints if name in contents]

    def runnable_candidate(name):
        if name in entrypoints or Path(name).suffix.lower() not in SCRIPT_SUFFIXES:
            return False
        # Suite directories also contain generators/installers. Expose those
        # as dependency candidates, not as tests to execute during preflight.
        basename = Path(name).name
        return ("test" in basename.lower() or "check" in basename.lower()
                or any(basename in source for source in runner_sources))

    return {
        "ok": True, "code": "SUITE_AFFECTED", "executed": False,
        "changed_paths": sorted(changed_paths), "symbols": sorted(symbols),
        "repositories": [path.relative_to(root).as_posix() for path in sorted(repositories)],
        "candidates": [
            {"path": name, "reasons": reasons, "suite_entrypoint": name in entrypoints}
            for name, reasons in sorted(selected.items())
        ],
        "scripts": sorted(
            name for name in selected if runnable_candidate(name)
        ),
        "skipped": skipped, "last_duration_s": duration,
        "preflight_required": isinstance(duration, (int, float)) and duration > 300,
        "failed_script_first": record.get("first_failure_line"),
        "limitations": [
            "Candidates only; text references do not prove dependency completeness.",
            "Review table/count assertions, dynamic imports and generated fixtures manually.",
            "After FAIL, rerun the failed script and check sibling fixtures before one full run.",
        ],
    }
