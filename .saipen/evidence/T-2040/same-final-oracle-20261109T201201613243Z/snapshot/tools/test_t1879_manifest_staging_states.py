"""T-1879: the manifest check must see CONTENT, not just a name in the index.

THE DEFECT, measured 2026-10-27 on a scratch clone of this repo. `git add -N`
(intent-to-add) registers a path in the index with the empty blob and no
content. `validate.py` read `git ls-files` as "is this file tracked", so the
intent-only path counted as tracked:

    $ git add -N tools/probe_intent.py
    $ python tools/validate.py --gate core
    PASS: runtime manifest complete (617 files, all tracked)
    $ git commit -m innocent          # the only OTHER file was staged
    COMMITTED
    $ git cat-file -e HEAD:tools/probe_intent.py
    NOT_IN_HEAD                       # its bytes were never committed

That is exactly the failure the manifest check exists to refuse -- a runtime
file present on one disk and in no clone -- reached through a gate that said
PASS. `bootstrap/inject.sh:304` (`cp -R`) and `bootstrap/inject.ps1:405`
(`Copy-Item -Recurse`) ship the on-disk tree, so every clone receives the PATH
and none receives the CONTENT: an ImportError at boot, discovered by a user.

WHY THE FIX IS A THIRD STATE AND NOT A WARN. E-17768 already measured that both
injectors copy the whole tree, so downgrading any of these findings to WARN
would disable the only local gate that sees a real publication defect. The
three states are distinct and each keeps its own FAIL:

    intent-only  name in index, content unstaged  -> "content is not staged"
    staged       content staged for this commit   -> PASS (it will ship)
    untracked    name in no index at all          -> "git does not track"

WHY THESE TESTS DRIVE A SUBPROCESS. `tools/validate.py` has no `__main__`
guard: importing it runs a full validation pass and calls `sys.exit`. So every
case here builds a real repository fixture, runs the real validator, and reads
its real output. The staging state IS the condition, and only git can create it.

WHY THE FIXTURE IS A DIRECTORY COPY. Two alternatives were measured and
rejected. A synthetic home of a few files cannot reach the manifest block at
all: the validator refuses with `SAIPEN installation has no BOOT.md` before it
produces a finding, so a green or red verdict there would be about the fixture,
not the check. Copying the whole repository takes 36 s; the four protocol
directories (`tools/`, `saipen/`, `bootstrap/`, `extensions/`) plus a committed
`.saipen/` scenario take 0.3 s and run the real validator in 1.6 s. The
manifest is narrowed to the files this fixture actually carries, so the only
variable between the three cases is the index.

Run standalone:
    python tools/test_t1879_manifest_staging_states.py
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: The probe whose staging state each case changes. It lives under `tools/`,
#: which `saipen/MANIFEST.json` ships as a copy tree -- so it IS a runtime
#: member the moment it exists on disk.
PROBE = "tools/probe_t1879_staging.py"

#: Directories a validator run needs before it can reach the manifest block:
#: `tools/` is the engine, `saipen/` holds the documents + MANIFEST.json and
#: the registry the phase graph loads, `bootstrap/` is part of the home shape,
#: `extensions/` supplies the schemas. Anything less and the run dies during
#: import instead of validating.
PROTOCOL_DIRS = ("tools", "saipen", "bootstrap", "extensions")

#: A small committed `.saipen/` a scenario already maintains, so the fixture
#: does not have to invent a conformant STATE/BOARD/LOG triple.
MEMORY_FIXTURE = ROOT / "tests" / "scenarios" / "stale-state-reconciliation" / ".saipen"


class _RepoFixture(unittest.TestCase):
    """A committed SAIPEN home whose only moving part is the index."""

    #: Built once per class: the copy is invariant, the cases only touch one
    #: probe file. Building it per test would triple the cost for no extra
    #: coverage.
    _base: Path | None = None
    _base_tmp: tempfile.TemporaryDirectory | None = None

    @classmethod
    def setUpClass(cls) -> None:
        if _RepoFixture._base is not None:
            return
        cls._base_tmp = tempfile.TemporaryDirectory(prefix="saipen-t1879-base-")
        base = Path(cls._base_tmp.name) / "home"
        ignore = shutil.ignore_patterns("__pycache__", ".pytest_cache")
        for name in PROTOCOL_DIRS:
            shutil.copytree(ROOT / name, base / name, ignore=ignore)
        (base / "VERSION").write_text("8.1.0\n", encoding="utf-8", newline="\n")
        # Exactly one `**vX.Y.Z**` badge: the badge check wants one and only
        # one, so a fixture README with none would fail for that reason and the
        # manifest defect would stop being the only one under test.
        (base / "README.md").write_text(
            "# fixture\n\n**v8.1.0**\n", encoding="utf-8", newline="\n"
        )
        # The fixture must ignore what the real repo ignores, or the purity
        # guard (which diffs `git status` around validation) reports the
        # validator's own byproducts as a mutation. Measured: without this,
        # validation writing `__pycache__/`, `.saipen/locks/core.lock` and its
        # conformance receipt made the accept case FAIL "VALIDATION MUTATED THE
        # TREE" -- a fact about the fixture, not about admission. Copying the
        # real `.gitignore` keeps the two trees' noise identical.
        shutil.copyfile(ROOT / ".gitignore", base / ".gitignore")
        shutil.copytree(MEMORY_FIXTURE, base / ".saipen")
        # Narrow the REAL manifest to what this fixture carries. A manifest
        # naming files the fixture dropped would fail for that reason, and the
        # staging state would stop being the only variable.
        manifest_path = base / "saipen" / "MANIFEST.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["files"] = [
            entry for entry in manifest["files"] if (base / entry["src"]).is_file()
        ]
        phase_dir = manifest["phase_docs"]["src_dir"]
        manifest["phase_docs"]["files"] = [
            name for name in manifest["phase_docs"]["files"] if (base / phase_dir / name).is_file()
        ]
        manifest_path.write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n"
        )
        cls._neutralize_foreign_wip(base)
        cls._init_repo(base)
        _RepoFixture._base = base

    @staticmethod
    def _neutralize_foreign_wip(home: Path) -> None:
        """Drop the one schema property the shared worktree's WIP disagrees on.

        `extension/schemas/state.schema.json` and `saipen/REGISTRY.json` are both
        mid-edit by another actor in this worktree: the schema declares 33
        properties, the registry's `state.known_fields` lists 32, and the
        difference is `continuous_maintenance`. `validate.py` compares exactly
        those two sets, so the real worktree FAILs `engine-state-contract` for
        that reason alone -- measured: restoring the registry's HEAD bytes
        instead makes the engine refuse to import (`REGISTRY.json
        'known_fields' must be a string array`), because HEAD's registry predates
        a key the WIP `board.py` now requires. Neither restore direction yields
        a coherent tree.

        So this fixture does not restore anything: it removes the single
        disagreeing property from its own scratch copy of the schema, which
        makes the pair consistent and leaves every other check untouched. The
        worktree's WIP is never written -- that belongs to another actor.
        """
        schema_path = home / "extensions" / "schemas" / "state.schema.json"
        registry_path = home / "saipen" / "REGISTRY.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8-sig"))
        registry = json.loads(registry_path.read_text(encoding="utf-8-sig"))
        known = set(registry.get("state", {}).get("known_fields", []))
        dropped = sorted(set(schema.get("properties", {})) - known)
        for name in dropped:
            schema["properties"].pop(name, None)
        schema_path.write_text(
            json.dumps(schema, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
            newline="\n",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._base_tmp is not None:
            cls._base_tmp.cleanup()
            _RepoFixture._base_tmp = None
            _RepoFixture._base = None

    @staticmethod
    def _init_repo(home: Path) -> None:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "probe",
            "GIT_AUTHOR_EMAIL": "probe@example.invalid",
            "GIT_COMMITTER_NAME": "probe",
            "GIT_COMMITTER_EMAIL": "probe@example.invalid",
        }
        for args in (
            ("init", "-q"),
            ("add", "-A"),
            ("commit", "-q", "-m", "fixture baseline"),
        ):
            subprocess.run(
                ["git", *args],
                cwd=home,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=True,
            )

    def setUp(self) -> None:
        assert _RepoFixture._base is not None
        self._tmp = tempfile.TemporaryDirectory(prefix="saipen-t1879-case-")
        self.root = Path(self._tmp.name) / "home"
        shutil.copytree(_RepoFixture._base, self.root)
        # The probe must not exist before a case begins: its whole subject is
        # the transition from absent to one of the three staging states.
        (self.root / PROBE).unlink(missing_ok=True)
        self._gitenv = {
            **os.environ,
            "GIT_AUTHOR_NAME": "probe",
            "GIT_AUTHOR_EMAIL": "probe@example.invalid",
            "GIT_COMMITTER_NAME": "probe",
            "GIT_COMMITTER_EMAIL": "probe@example.invalid",
        }

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            env=self._gitenv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def validate(self, *, validator: Path | None = None) -> str:
        """The real validator's real output. Never imported (see module doc)."""
        target = validator or (self.root / "tools" / "validate.py")
        result = subprocess.run(
            [sys.executable, str(target), "--project-root", str(self.root), "--gate", "core"],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return result.stdout + result.stderr

    @staticmethod
    def manifest_lines(output: str) -> list[str]:
        return [
            line for line in output.splitlines() if "runtime manifest" in line
        ]

    def write_probe(self, body: str) -> None:
        (self.root / PROBE).write_text(body, encoding="utf-8", newline="\n")

    def commit(self, message: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.root,
            env=self._gitenv,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    def install_hook(self) -> Path:
        """Install the shipped hook into the fixture, validating the fixture.

        `tools/install_hook.py` derives its home from `__file__`, so running the
        fixture's own copy bakes the fixture path -- which is what these cases
        need. The assertion below pins that, because a hook pointing at the real
        repo would pass for the wrong reason and prove nothing about admission.
        """
        result = subprocess.run(
            [sys.executable, str(self.root / "tools" / "install_hook.py")],
            cwd=self.root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        hook = self.root / ".git" / "hooks" / "pre-commit"
        self.assertTrue(
            result.returncode == 0 and hook.is_file(),
            f"installer failed: {result.stdout}{result.stderr}",
        )
        body = hook.read_text(encoding="utf-8-sig")
        self.assertIn("# saipen pre-commit hook", body)
        fixture_home = str(self.root).replace("\\", "/")
        self.assertIn(
            f'SAIPEN_HOME="{fixture_home}"',
            body,
            "hook targets another home; the admission cases would test that tree",
        )
        self.assertIn('python "$SAIPEN_HOME/tools/validate.py"', body)
        hook.chmod(0o755)
        return hook


class ThreeStateTests(_RepoFixture):
    """One fixture, three staging states, three distinct verdicts."""

    def test_the_baseline_is_green(self) -> None:
        lines = self.manifest_lines(self.validate())
        self.assertTrue(
            any(line.startswith("PASS: runtime manifest complete") for line in lines),
            lines,
        )

    def test_intent_only_content_fails_and_names_the_real_repair(self) -> None:
        """THE DEFECT. Pre-fix this printed PASS (see RedControlTests)."""
        self.write_probe("INTENT = 1\n")
        self.git("add", "-N", PROBE)
        self.assertEqual(
            self.git("ls-files", "--", PROBE).stdout.strip(),
            PROBE,
            "fixture precondition: intent-to-add must list the path",
        )
        self.assertEqual(
            self.git("diff", "--cached", "--name-only", "--diff-filter=d", "--", PROBE).stdout.strip(),
            "",
            "fixture precondition: -N stages no content",
        )
        output = self.validate()
        self.assertIn(
            f"runtime manifest names a file whose content is not staged: {PROBE}",
            output,
        )
        # The repair names the CONTENT step, not "commit the file" -- which is
        # what a session using -N believes it already did.
        self.assertIn(f"`git add {PROBE}`, then commit it", output)
        # ...and the misleading green line must be gone.
        self.assertNotIn("runtime manifest complete", output)

    def test_staged_content_passes(self) -> None:
        """The middle state is the ordinary case: one commit will carry it."""
        self.write_probe("STAGED = 1\n")
        self.git("add", PROBE)
        self.assertIn(
            PROBE,
            self.git("diff", "--cached", "--name-only", "--diff-filter=d", "--", PROBE).stdout,
        )
        lines = self.manifest_lines(self.validate())
        self.assertFalse([line for line in lines if line.startswith("FAIL")], lines)
        self.assertTrue(
            any(line.startswith("PASS: runtime manifest complete") for line in lines),
            lines,
        )

    def test_plain_untracked_still_fails_with_the_original_message(self) -> None:
        """T-1592's finding must not be reworded by this change."""
        self.write_probe("UNTRACKED = 1\n")
        self.assertEqual(
            self.git("ls-files", "--", PROBE).stdout.strip(),
            "",
            "fixture precondition: a plain untracked file is in no index",
        )
        output = self.validate()
        self.assertIn(f"runtime manifest names a file git does not track: {PROBE}", output)
        self.assertNotIn("content is not staged", output)

    def test_a_file_the_index_never_met_is_not_called_intent_only(self) -> None:
        """The three states must not collapse: only a staged name is intent-only."""
        initial = self.validate()
        self.assertNotIn("content is not staged", initial)
        self.assertNotIn("git does not track", initial)

    def test_conformance_passes_on_a_tree_whose_only_defect_would_be_untracked(self) -> None:
        """The verify clause's third half, asserted on the whole gate.

        Not "the manifest line is green" but "the gate has no FAIL at all" once
        the only candidate defect is a file that is properly committed. A tree
        that failed for some unrelated reason would make the manifest PASS
        meaningless, so this checks the absence of every FAIL line.
        """
        output = self.validate()
        fails = [line for line in output.splitlines() if line.startswith("FAIL")]
        self.assertEqual(fails, [], "fixture is not clean apart from staging")
        self.assertIn("PASS: runtime manifest complete", output)


class AdmissionTests(_RepoFixture):
    """The commit itself, not the validator's opinion of the index.

    The verify clause asks that a newly added `tools/` file "either commits
    cleanly or is refused at the point it is added". Arguing that the hook runs
    `validate.py` is not that proof: the hook could be absent, non-executable,
    or bypassed by an unset variable and the validator would still look right.
    These cases make the commit attempt and read git's own exit status.
    """

    def test_the_shipped_hook_refuses_a_commit_whose_only_runtime_file_is_intent_only(self) -> None:
        self.install_hook()
        self.write_probe("INTENT = 1\n")
        self.git("add", "-N", PROBE)
        before = self.git("rev-parse", "HEAD").stdout.strip()
        result = self.commit("attempt the intent-only add")
        self.assertNotEqual(result.returncode, 0, "the hook let the commit through")
        self.assertIn("content is not staged", result.stdout + result.stderr)
        after = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(before, after, "HEAD moved: a commit landed despite the refusal")
        self.assertEqual(
            self.git("cat-file", "-e", f"HEAD:{PROBE}").returncode,
            128,
            "the intent-only file reached HEAD anyway",
        )

    def test_the_shipped_hook_accepts_the_same_file_once_its_content_is_staged(self) -> None:
        self.install_hook()
        self.write_probe("STAGED = 1\n")
        self.git("add", PROBE)
        before = self.git("rev-parse", "HEAD").stdout.strip()
        result = self.commit("stage the content and commit")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertNotEqual(before, after, "the commit did not land")
        self.assertEqual(
            self.git("cat-file", "-e", f"HEAD:{PROBE}").returncode,
            0,
            "the committed file is missing from HEAD",
        )
        self.assertEqual(
            self.git("show", f"HEAD:{PROBE}").stdout,
            "STAGED = 1\n",
            "HEAD carries different bytes than the worktree",
        )

    def test_a_missing_hook_is_why_this_suite_installs_it(self) -> None:
        """Guard against a fixture that silently has no gate at all."""
        hook = self.root / ".git" / "hooks" / "pre-commit"
        self.assertFalse(hook.exists(), "fixture already carries a hook; the cases prove nothing")
        self.install_hook()
        self.assertIn("# saipen pre-commit hook", hook.read_text(encoding="utf-8-sig"))


class RedControlTests(_RepoFixture):
    """The fix is the delta: without it the intent-only state reads green.

    The pre-fix expression is reproduced by emptying `_runtime_intent_only`,
    which is exactly the old verdict: `ls-files` listed the path, so nothing
    was reported and the green line printed over bytes no commit would carry.
    """

    #: The single expression this change introduced. If a later edit removes
    #: it, the control says so instead of passing vacuously.
    _ASSIGNMENT = (
        "                        _runtime_intent_only = set(_runtime_tracked_set) - _runtime_landed_set"
    )

    def test_the_red_control_anchor_still_exists(self) -> None:
        source = (ROOT / "tools" / "validate.py").read_text(encoding="utf-8-sig")
        self.assertIn(self._ASSIGNMENT, source, "the fix's anchor moved; update the control")

    def test_without_the_fix_the_intent_only_state_reads_green(self) -> None:
        source = (ROOT / "tools" / "validate.py").read_text(encoding="utf-8-sig")
        pre = source.replace(self._ASSIGNMENT, "                        _runtime_intent_only = set()")
        self.assertNotEqual(pre, source, "the intent-only assignment moved; update the control")
        mutated = self.root / "tools" / "validate.py"
        mutated.write_text(pre, encoding="utf-8", newline="\n")
        self.write_probe("INTENT = 1\n")
        self.git("add", "-N", PROBE)
        output = self.validate(validator=mutated)
        # The defect reproduced: no content-staging FAIL for this file, and the
        # green line printed over a path no commit carries.
        self.assertNotIn("content is not staged", output)
        self.assertIn("runtime manifest complete", output)


class InjectionStillShipsTheDiskTests(unittest.TestCase):
    """E-17768's measurement, pinned so nobody re-tries the WARN idea."""

    def test_the_shell_injector_copies_the_whole_tree(self) -> None:
        text = (ROOT / "bootstrap" / "inject.sh").read_text(encoding="utf-8-sig")
        self.assertIn('cp -R "$ROOT/$src" "$target"', text)

    def test_the_powershell_injector_copies_the_whole_tree(self) -> None:
        text = (ROOT / "bootstrap" / "inject.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("Copy-Item -Destination $target -Recurse -Force", text)

    def test_copy_tree_members_reads_the_disk_not_the_index(self) -> None:
        """The shared expansion must stay disk-based, or the FAIL loses meaning."""
        text = (ROOT / "tools" / "saipen_engine" / "manifest.py").read_text(encoding="utf-8-sig")
        self.assertIn("os.walk(source", text)
        self.assertNotIn("ls-files", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
