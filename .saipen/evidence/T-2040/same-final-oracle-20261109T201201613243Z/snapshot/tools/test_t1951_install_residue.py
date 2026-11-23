"""T-1951: two defects that together deadlocked authenticated ingress.

FIRST -- a retired module must not be resurrected into every new install.
`bootstrap/install_ownership.py:record()` merges the destination's state into a
freshly staged generation before the swap. Its documented contract is "an
upgrade preserves extra files", but a file that sits INSIDE a manifest-declared
runtime tree is not a user note: the runtime identity
(`saipen_engine.runtime_surface.require_runtime_generation_identity`) hashes
every member of that tree, so one extra file there makes the installed
generation permanently unequal to its source. The scheduled injector compares
the copy's identity against the source's, so that file kept the comparison
false forever and every publication rolled back. Measured live: 26 ROLLED_BACK
runs between 2026-10-05 12:01 and 2026-10-28.

SECOND -- a rollback must take the bindings back with it.
`bootstrap/schedule-run.ps1` restores `scheduled-source` and stopped there, so
the guard artifact and the PATH launchers written during the failed run stayed
in place and executed the NEW generation's code against the OLD generation's
tree. Measured live, the installed ZAICODE hook answered

    {"ok": false, "code": "ENGINE_UNREACHABLE",
     "detail": "runtime import failed: ImportError"}

for every operator prompt. The rollback also deleted `published` before
checking whether a previous generation existed, leaving NO generation at the
one path every launcher and hook config names.

Both halves are measured against the pre-fix bytes carried under
`.saipen/evidence/T-1951-install-residue/pre/`; a control proves the assertions
red there. The tests are behaviour, not source text: the first half runs
`record()` on a real two-directory pair, the second drives the real publisher.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BOOTSTRAP = ROOT / "bootstrap"

sys.path.insert(0, str(ROOT / "tools"))


def setUpModule() -> None:
    # The binding tests drive the real scheduled publisher, which writes host
    # hook configs. Isolation is reference-counted and restores on module
    # cleanup, so the operator's own surfaces are never touched.
    from test_hermetic_env import isolate_host_session

    isolate_host_session()


def _ownership():
    spec = importlib.util.spec_from_file_location(
        "t1951_install_ownership", BOOTSTRAP / "install_ownership.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _manifest(*trees: str, managed: tuple[str, ...] = ()) -> str:
    return json.dumps(
        {
            "managed_dirs": list(managed),
            "copy_trees": [{"src": t, "dst": t} for t in trees],
            "files": [],
        }
    )


class RetiredRuntimeFileIsNotResurrectedTests(unittest.TestCase):
    def test_a_file_inside_a_declared_tree_does_not_survive_the_swap(self):
        ownership = _ownership()
        with tempfile.TemporaryDirectory(prefix="saipen-t1951-") as tmp:
            destination = Path(tmp) / "skills" / "saipen"
            (destination / "tools").mkdir(parents=True)
            # The previous generation shipped it; this one does not.
            (destination / "tools" / "retired.py").write_bytes(b"# retired\n")
            (destination / "tools" / "kept.py").write_bytes(b"# old kept\n")

            stage = Path(tmp) / "stage"
            (stage / "tools").mkdir(parents=True)
            (stage / "tools" / "kept.py").write_bytes(b"# new kept\n")
            (stage / "MANIFEST.json").write_text(_manifest("tools"), encoding="utf-8")

            ownership.record(stage, destination)

            self.assertFalse(
                (stage / "tools" / "retired.py").exists(),
                "an undeclared file inside a declared runtime tree was copied back "
                "into the new generation, which can never match its source identity",
            )
            self.assertEqual((stage / "tools" / "kept.py").read_bytes(), b"# new kept\n")

    def test_the_retired_bytes_are_kept_in_the_sibling_backup(self):
        ownership = _ownership()
        with tempfile.TemporaryDirectory(prefix="saipen-t1951-") as tmp:
            skills = Path(tmp) / "skills"
            destination = skills / "saipen"
            (destination / "tools").mkdir(parents=True)
            payload = b"# retired, and worth keeping\n"
            (destination / "tools" / "retired.py").write_bytes(payload)

            stage = Path(tmp) / "stage"
            (stage / "tools").mkdir(parents=True)
            (stage / "MANIFEST.json").write_text(_manifest("tools"), encoding="utf-8")

            ownership.record(stage, destination)

            [backup] = [p for p in skills.iterdir() if p.name.startswith(".saipen-user-backup-")]
            self.assertEqual((backup / "tools" / "retired.py").read_bytes(), payload)

    def test_a_file_outside_every_declared_tree_is_still_preserved_in_place(self):
        # The rule must not become "delete things": a user's own file next to
        # the runtime is not part of the identity and stays where it is.
        ownership = _ownership()
        with tempfile.TemporaryDirectory(prefix="saipen-t1951-") as tmp:
            destination = Path(tmp) / "skills" / "saipen"
            (destination / "tools").mkdir(parents=True)
            (destination / "MY_NOTES.md").write_bytes(b"mine\n")

            stage = Path(tmp) / "stage"
            (stage / "tools").mkdir(parents=True)
            (stage / "MANIFEST.json").write_text(_manifest("tools"), encoding="utf-8")

            ownership.record(stage, destination)

            self.assertEqual((stage / "MY_NOTES.md").read_bytes(), b"mine\n")

    def test_a_preserved_user_file_is_not_claimed_by_the_ledger(self):
        # The ledger is what the NEXT run consults: an entry whose digest still
        # matches is treated as already installed and skipped, and the fresh
        # stage never contains that file. Writing a preserved file into the
        # ledger would therefore delete it on the following run -- trading a
        # resurrection for a disappearance. REVIEW caught exactly this in the
        # first version of the fix.
        ownership = _ownership()
        with tempfile.TemporaryDirectory(prefix="saipen-t1951-") as tmp:
            destination = Path(tmp) / "skills" / "saipen"
            (destination / "tools").mkdir(parents=True)
            (destination / "MY_NOTES.md").write_bytes(b"mine\n")

            stage = Path(tmp) / "stage"
            (stage / "tools").mkdir(parents=True)
            (stage / "MANIFEST.json").write_text(_manifest("tools"), encoding="utf-8")

            ownership.record(stage, destination)

            ledger = json.loads((stage / ownership.LEDGER).read_text(encoding="utf-8"))
            self.assertEqual((stage / "MY_NOTES.md").read_bytes(), b"mine\n")
            self.assertNotIn(
                "MY_NOTES.md",
                ledger["files"],
                "a preserved user file recorded as owned would be skipped by the next "
                "run and lost from the stage it was never copied into",
            )


class ARollbackKeepsTheBindingsOnTheGenerationItLeftBehindTests(unittest.TestCase):
    """The half of T-1951 that outlives the resurrection fix.

    A rollback puts the PREVIOUS source back at the one path every launcher and
    every installed hook config names. It used to stop there: the guard artifact
    and the PATH launchers written during the failed run stayed in place, so the
    hook executed the NEW generation's code against the OLD generation's tree.
    Measured live, that answers

        {"ok": false, "code": "ENGINE_UNREACHABLE",
         "detail": "runtime import failed: ImportError"}

    for every operator prompt -- the authenticated ingress deadlock. The tests
    below drive the real `bootstrap/schedule-run.ps1` through the same fixture
    T-1613 uses, because the defect lives in that script's rollback path and a
    mocked rollback would prove nothing about it.
    """

    def setUp(self) -> None:
        from test_t1613_publication_convergence import IS_WINDOWS, POWERSHELL, _Publisher

        if not (IS_WINDOWS and POWERSHELL):
            self.skipTest("the scheduled publisher is Windows-only")
        self._base = Path(tempfile.mkdtemp(prefix="saipen-t1951-bind-"))
        self.box = _Publisher(self._base)
        self._broken = None

    def tearDown(self) -> None:
        shutil.rmtree(self._base, ignore_errors=True)

    def _hook(self) -> Path:
        return self.box.home / ".gemini" / "hooks" / "saipen-guard.py"

    def _force_blocking_failure(self) -> None:
        """Break the blocking Gemini skill surface the way T-1613 case G does.

        The destination's own parent is a FILE, so staging cannot start and no
        retry can ever help: this is a terminal failure, not contention, and it
        makes the injector exit non-zero for a BLOCKING consumer.
        """
        skills = self.box.gemini_skill().parent
        shutil.rmtree(skills, ignore_errors=True)
        skills.write_text("not a directory\n", encoding="utf-8")
        self._broken = skills

    def _repair_surface(self) -> None:
        if self._broken is not None and self._broken.exists() and not self._broken.is_dir():
            self._broken.unlink()

    def _ship_a_new_guard_generation(self) -> None:
        """Move BOTH the runtime marker and the guard artifact forward.

        `_Publisher.bump_generation` only edits `saipen/BOOT.md`, so the guard
        artifact the injector copies is byte-identical from one fixture
        generation to the next -- and a test that compares guard bytes would
        then pass on the pre-fix runner for the wrong reason. The defect is a
        NEW guard beside an OLD engine, so the fixture has to ship a new guard:
        the appended comment changes the bytes without changing behaviour.
        """
        self.box.bump_generation()
        guard = self.box.source / "tools" / "host_guard.py"
        with guard.open("a", encoding="utf-8") as handle:
            handle.write(f"\n# fixture guard generation {self.box._generation}\n")
        self.box._git("add", "-A")
        self.box._git(
            "-c", "user.name=fixture", "-c", "user.email=f@x",
            "commit", "-q", "-m", f"fixture guard generation {self.box._generation}",
        )

    def _register_a_path_launcher(self) -> Path:
        """Put a launcher file where the engine would own one.

        Measured, and the reason this helper exists rather than a test: a
        same-path publish never changes the launcher's BYTES. The rendered
        launcher runs `<published>/tools/saipen.py`, and `scheduled-source` is a
        deliberately stable path, so the launcher is generation-invariant by
        construction. An assertion that a rollback restores launcher bytes would
        therefore pass on the pre-fix runner too -- a green that proves nothing.
        The launcher is still snapshotted, because the injector DOES rewrite it
        when the interpreter or the engine path changes.
        """
        directory = self.box.home / "bin"
        directory.mkdir(parents=True, exist_ok=True)
        launcher = directory / "saipen.cmd"
        launcher.write_bytes(b"@echo off\r\nrem fixture launcher, previous generation\r\n")
        return launcher

    def test_a_launcher_left_naming_the_published_path_still_reaches_an_engine(self):
        """The one launcher property a rollback CAN break.

        Bytes do not skew (see above), but the file a launcher names can be
        emptied: that is exactly what the pre-fix rollback did on a machine with
        no previous generation. So the honest assertion is that whatever the
        launcher runs still resolves after the rollback, not that its bytes are
        unchanged.
        """
        box = self.box
        box.install()
        self._register_a_path_launcher()
        self._ship_a_new_guard_generation()
        self._force_blocking_failure()
        try:
            run = box.publish()
            log = box.log_text()
        finally:
            self._repair_surface()

        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        with self.subTest("the engine a launcher would run survived the rollback"):
            self.assertTrue(
                (box.published() / "tools" / "saipen.py").is_file(),
                "a launcher naming scheduled-source now names a path with no engine",
            )
        with self.subTest("the run reports the surfaces it snapshotted and restored"):
            self.assertIn("bindings: snapshotted", log)
            self.assertIn("bindings: restored=", log)

    def test_a_rolled_back_run_leaves_no_new_guard_beside_the_old_source(self):
        box = self.box
        box.install()
        self.assertTrue(self._hook().is_file(), "fixture did not install a guard hook")
        before = self._hook().read_bytes()
        # A new generation is what makes the injector rewrite the artifact; the
        # bytes it writes must not survive a rollback that discards that
        # generation.
        self._ship_a_new_guard_generation()
        # The fixture must really be shipping different guard bytes, or this
        # run could not catch the skew it exists to catch. Compare the SHIPPED
        # artifact, not the installed one: the installed copy is what the
        # rollback is supposed to put back, so it is the wrong witness.
        shipped = (box.source / "tools" / "host_guard.py").read_bytes()
        self.assertNotEqual(
            shipped,
            before,
            "the fixture never shipped a new guard generation",
        )
        self._force_blocking_failure()
        try:
            run = box.publish()
            record = box.convergence()
            log = box.log_text()
        finally:
            self._repair_surface()

        with self.subTest("the run really rolled back"):
            self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertEqual(record.get("publication"), "ROLLED_BACK", record)
        with self.subTest("the binding agrees with the source it was restored to"):
            self.assertEqual(
                self._hook().read_bytes(),
                before,
                "the guard written for the rejected generation stayed installed, so "
                "the hook now runs new code against the old tree and cannot import",
            )
        with self.subTest("the run says which bindings it restored"):
            self.assertIn("bindings: restored=", log)
            self.assertIn("binding=bound", log)

    def test_the_binding_is_restored_even_when_no_previous_generation_exists(self):
        """A machine's first publish has nothing to go back to.

        `Restore-PublishedSource` used to delete the published path first and
        only then discover `previous` was absent, leaving NO generation at the
        path every launcher names. A rejected-but-complete generation still
        loads and names its own drift; an empty path answers ImportError.
        """
        box = self.box
        self.assertEqual(box.published_generation(), 0, "fixture must start unpublished")
        self._force_blocking_failure()
        try:
            run = box.publish()
            log = box.log_text()
        finally:
            self._repair_surface()

        self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
        with self.subTest("the published path still resolves to a generation"):
            # The rejected tree is a COMPLETE generation of the source HEAD, so
            # the honest question is not "was it rolled back" (there was nothing
            # to roll back to) but "does the path every launcher names still
            # hold a loadable engine".
            self.assertTrue(
                (box.published() / "tools" / "saipen.py").is_file(),
                "a rollback with no previous generation emptied the path every "
                "launcher and hook config names",
            )
            self.assertEqual(
                (box.published() / "saipen" / "BOOT.md").read_bytes(),
                (box.source / "saipen" / "BOOT.md").read_bytes(),
                "the retained tree must be the generation this run was publishing",
            )
        with self.subTest("the log never claims a binding it does not have"):
            self.assertIn("no previous generation to restore", log)
            self.assertIn("binding=bound", log)


if __name__ == "__main__":
    unittest.main()
