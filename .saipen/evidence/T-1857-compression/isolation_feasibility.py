"""Disposable feasibility experiment, NOT a canonical release executor."""
from __future__ import annotations
import concurrent.futures
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMP_ROOT = Path(tempfile.gettempdir()).resolve()
RESULTS = []

def digest(data):
    return hashlib.sha256(data).hexdigest()

class Fixture:
    def __init__(self):
        self.temp = tempfile.TemporaryDirectory(prefix="saipen-w2-", dir=TEMP_ROOT)
        self.sandbox = Path(self.temp.name).resolve()
        assert self.sandbox.is_relative_to(TEMP_ROOT) and self.sandbox.name.startswith("saipen-w2-")
        self.root = self.sandbox / "repository"
        self.root.mkdir()
        self.hooks = self.sandbox / "empty-hooks"
        self.hooks.mkdir()
        self.git(self.root, "init", "--initial-branch=main")
        self.git(self.root, "config", "user.name", "SAIPEN disposable fixture")
        self.git(self.root, "config", "user.email", "fixture@example.invalid")
        for name in ("reviewed.txt", "foreign.txt", "second.txt"):
            (self.root / name).write_bytes(("original " + name + "\n").encode("utf-8"))
        self.git(self.root, "add", "--", "reviewed.txt", "foreign.txt", "second.txt")
        self.git(self.root, "commit", "-m", "fixture base")
        self.base = self.git(self.root, "rev-parse", "HEAD").strip()
        (self.root / "foreign.txt").write_bytes(b"operator's foreign staged bytes\n")
        self.git(self.root, "add", "--", "foreign.txt")
        (self.root / "reviewed.txt").write_bytes(b"reviewed change\n")
        (self.root / "second.txt").write_bytes(b"independent reviewed change\n")

    def close(self):
        # The only recursive deletion is the directory created above. Verify
        # the absolute target again immediately before TemporaryDirectory cleanup.
        assert self.sandbox.is_relative_to(TEMP_ROOT)
        assert self.sandbox.name.startswith("saipen-w2-") and self.sandbox != TEMP_ROOT
        self.temp.cleanup()

    def git(self, cwd, *args):
        assert Path(cwd).resolve().is_relative_to(self.sandbox)
        env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}
        # Fixture isolation only: never invoke an operator's global hooks or signer.
        run = subprocess.run(
            ["git", "-c", "core.hooksPath=" + str(self.hooks),
             "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", *args],
            cwd=cwd, env=env, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=40, check=False,
        )
        if run.returncode:
            raise RuntimeError(f"disposable git {args}: {run.stderr}")
        return run.stdout

    def snapshot(self):
        return {
            "head": self.git(self.root, "rev-parse", "HEAD").strip(),
            "refs": self.git(self.root, "show-ref", "--head"),
            "index": (self.root / ".git/index").read_bytes(),
            "entries": self.git(self.root, "ls-files", "--stage", "-z"),
            "worktree": {p.name: p.read_bytes() for p in self.root.iterdir() if p.is_file()},
        }

    def violations(self, before, commit, scope):
        now = self.snapshot()
        found = []
        for name in ("head", "refs", "index", "entries", "worktree"):
            if now[name] != before[name]:
                found.append(name + "-changed")
        parent = self.git(self.root, "rev-parse", commit + "^").strip()
        if parent != before["head"]:
            found.append("wrong-parent")
        changed = set(self.git(self.root, "diff-tree", "--no-commit-id", "--name-only",
                               "-r", parent, commit).splitlines())
        if changed != set(scope):
            found.append("unreviewed-or-missing-path")
        for name in scope:
            stored = self.git(self.root, "show", commit + ":" + name).encode("utf-8")
            if stored != before["worktree"][name]:
                found.append("reviewed-bytes-mismatch")
        if self.git(self.root, "show", commit + ":foreign.txt") != "original foreign.txt\n":
            found.append("foreign-staged-content-committed")
        return found

    def isolated(self, name, scope, expected, *, interrupted=False):
        for path in scope:
            source = (self.root / path).resolve()
            assert source.is_relative_to(self.root.resolve()) and source.is_file()
            if source.is_symlink() or digest(source.read_bytes()) != expected[path]:
                raise ValueError("reviewed source changed")
        target = self.sandbox / name
        self.git(self.root, "worktree", "add", "--detach", str(target), self.base)
        for path in scope:
            data = (self.root / path).read_bytes()
            if digest(data) != expected[path]:
                raise ValueError("reviewed source changed during construction")
            (target / path).write_bytes(data)
        self.git(target, "add", "--", *scope)
        self.git(target, "commit", "-m", "fixture exact reviewed scope")
        if interrupted:
            raise InterruptedError(str(target))
        return self.git(target, "rev-parse", "HEAD").strip()

def run():
    fixture = Fixture()
    try:
        before = fixture.snapshot()
        fixture.git(fixture.root, "add", "--", "reviewed.txt")
        fixture.git(fixture.root, "commit", "-m", "deliberately unsafe control")
        commit = fixture.git(fixture.root, "rev-parse", "HEAD").strip()
        red = fixture.violations(before, commit, ["reviewed.txt"])
        assert "foreign-staged-content-committed" in red
        assert "index-changed" in red and "head-changed" in red
        RESULTS.append({"case": "naive shared-index control", "oracle": "REJECT", "violations": red})
    finally:
        fixture.close()

    fixture = Fixture()
    try:
        before = fixture.snapshot()
        expected = {p: digest(before["worktree"][p]) for p in ("reviewed.txt", "second.txt")}
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(fixture.isolated, "candidate-one", ["reviewed.txt"], expected),
                pool.submit(fixture.isolated, "candidate-two", ["second.txt"], expected),
            ]
            commits = [future.result() for future in futures]
        for commit, scope in zip(commits, (["reviewed.txt"], ["second.txt"])):
            problems = fixture.violations(before, commit, scope)
            assert problems == [], problems
        RESULTS.append({"case": "two concurrent detached-worktree candidates",
                        "oracle": "PASS", "commits": commits,
                        "parent": before["head"], "live_index_sha256": digest(before["index"]),
                        "original_refs_unchanged": True, "original_worktree_unchanged": True,
                        "foreign_staging_unchanged": True, "exact_scope_only": True})
    finally:
        fixture.close()

    fixture = Fixture()
    try:
        before = fixture.snapshot()
        expected = {"reviewed.txt": digest(before["worktree"]["reviewed.txt"])}
        try:
            fixture.isolated("interrupted", ["reviewed.txt"], expected, interrupted=True)
        except InterruptedError as fault:
            target = Path(str(fault))
        else:
            raise AssertionError("interruption was not injected")
        recovered = fixture.git(target, "rev-parse", "HEAD").strip()
        assert fixture.violations(before, recovered, ["reviewed.txt"]) == []
        # A candidate can be inspected again without claiming or publishing it.
        assert fixture.git(target, "rev-parse", "HEAD").strip() == recovered
        RESULTS.append({"case": "interruption after candidate commit before acceptance",
                        "oracle": "PASS", "candidate_recoverable": True,
                        "production_journal_acceptance": False,
                        "live_index_sha256": digest(before["index"])})
    finally:
        fixture.close()

    fixture = Fixture()
    try:
        expected = {"reviewed.txt": digest((fixture.root / "reviewed.txt").read_bytes())}
        (fixture.root / "reviewed.txt").write_text("unreviewed concurrent edit\n", encoding="utf-8")
        before = fixture.snapshot()
        try:
            fixture.isolated("stale", ["reviewed.txt"], expected)
        except ValueError as fault:
            assert str(fault) == "reviewed source changed"
        else:
            raise AssertionError("stale source was accepted")
        assert fixture.snapshot() == before
        RESULTS.append({"case": "changed reviewed-source identity", "oracle": "REFUSE",
                        "source_and_index_preserved": True})
    finally:
        fixture.close()

    result = {
        "scope": "Git primitive feasibility in generated disposable repositories ONLY",
        "canonical_release_implemented": False,
        "live_repository_writes": False,
        "controls": RESULTS,
        "unproved": [
            "canonical current-generation full-family evidence for an isolated final tree",
            "native source/authority and closure receipt binding through the existing journal",
            "production hooks, signing, deployment policy and release recovery integration",
            "safe application to the live incomplete-history and 206-staged-path generation",
        ],
    }
    (HERE / "W2-FEASIBILITY.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    run()

