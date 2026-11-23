"""T-1613: a published generation and a converged consumer are two facts.

Measured live on 2026-10-04 while publishing 70b30291. The injector copies
`~/.gemini/skills/saipen` (Gemini's own surface) and, for the Antigravity
adapter, two plugin-local copies under `~/.gemini/config/plugins/*/skills`.
The running Antigravity IDE holds those two directories open, so the
destination swap cannot rename them and `Copy-Skill` returned a failure --
which the report counted as fatal, which made `inject.ps1` exit 1, which made
`schedule-run.ps1` restore the PREVIOUS published source, while the seven
consumer homes it had already written stayed on the new generation.

Two defects, one incident:

  A. an adapter the registry declares `blocking_capability: false` acquired
     stronger global authority than the registry grants it, and
  B. a valid publication was rolled back because a downstream consumer had
     not converged -- a rollback that could never restore the consumers it
     was supposed to undo, so it only ever manufactured generation skew.

Windows behaviour used here is the one already established in
`.saipen/KNOWLEDGE/cards/windows-replace-read-sharing-race.md`: a
sharing/replace collision is CONTENTION. The tests hold a directory open the
way the IDE does (`CreateFileW` with no share mode) instead of faking an
error string, so what is asserted is the real failure class.

The matrix the repair has to survive is A-L:
  A/B. two locked non-blocking plugin consumers -> publication CURRENT, both
       DEFERRED_RETRYABLE, the writable Gemini surface APPLIED;
  C/K. unlock, run again -> both converge, pending clears;
  D.   an install that already holds this generation -> ALREADY_CURRENT;
  E.   a host this machine never installed -> SKIPPED_NOT_INSTALLED;
  F.   a dirty injected surface -> refused before publication, previous
       generation retained;
  G.   a failure on a BLOCKING consumer -> real failure, publication rolled
       back;
  H/I. successful consumers and the publication are not rolled backward, and
       status reports publication and convergence separately;
  J.   the live topology never asks a human for anything;
  L.   the surrounding install/distribution suites stay green.
"""

from __future__ import annotations

import ctypes
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from ctypes import wintypes
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
POWERSHELL = shutil.which("powershell") or shutil.which("pwsh")
IS_WINDOWS = os.name == "nt"

sys.path.insert(0, str(ROOT / "tools"))

from test_hermetic_env import isolate_host_session, nested_run  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _surface_files() -> list[str]:
    """The runtime surface, read from the ONE owner (saipen/MANIFEST.json).

    The publisher snapshots a whole git commit, so the fixture commit is kept
    to the injected surface: an evidence archive is not runtime and copying
    it would make every test pay for it.
    """
    manifest = json.loads((ROOT / "saipen" / "MANIFEST.json").read_text(encoding="utf-8"))
    files: list[str] = []
    for tree in manifest.get("copy_trees") or ():
        for path in (ROOT / tree["src"]).rglob("*"):
            if path.is_file():
                files.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    for entry in manifest.get("files") or ():
        files.append(entry["src"])
    extra = ["VERSION", "saipen/MANIFEST.json"]
    files.extend(extra)
    return sorted(set(files))

_GENERATION = re.compile(r"fixture generation (\d+)")

def _generation_of(text: str) -> int:
    found = _GENERATION.search(text)
    return int(found.group(1)) if found else 0


class _DirectoryLock:
    """Hold a directory open the way a running IDE holds a plugin dir.

    `CreateFileW` on a directory needs `FILE_FLAG_BACKUP_SEMANTICS`, and a
    share mode of 0 means no other handle may open it -- including one
    carrying delete access, which is exactly what a directory rename needs.
    That refusal (ERROR_ACCESS_DENIED on the rename) is the failure the
    incident produced.
    """

    GENERIC_READ = 0x80000000
    DELETE = 0x00010000
    OPEN_EXISTING = 3
    FILE_FLAG_BACKUP_SEMANTICS = 0x02000000

    def __init__(self, path: Path, asks_delete: bool = True):
        self.path = Path(path)
        # The two real shapes a Windows holder produces, measured live on
        # 2026-10-04: a holder that asked for delete access refuses the rename
        # with ERROR_SHARING_VIOLATION, and one that did not refuses it as
        # "Access to the path ... is denied" -- which carries no usable HRESULT
        # at all. Both must land on the same answer.
        self._asks_delete = asks_delete
        self._handle = None

    def __enter__(self) -> "_DirectoryLock":
        if not IS_WINDOWS:
            raise unittest.SkipTest("the collision under test is a Windows sharing violation")
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateFileW.restype = wintypes.HANDLE
        kernel32.CreateFileW.argtypes = (
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            wintypes.DWORD,
            wintypes.HANDLE,
        )
        access = self.GENERIC_READ | (self.DELETE if self._asks_delete else 0)
        handle = kernel32.CreateFileW(
            str(self.path),
            access,
            0,
            None,
            self.OPEN_EXISTING,
            self.FILE_FLAG_BACKUP_SEMANTICS,
            None,
        )
        # HANDLE is unsigned: INVALID_HANDLE_VALUE arrives as 2**64-1.
        if not handle or handle == ctypes.c_void_p(-1).value:
            raise OSError(ctypes.get_last_error(), f"cannot hold {self.path}")
        self._handle = handle
        return self

    def __exit__(self, *_exc) -> None:
        if self._handle is not None:
            kernel32 = ctypes.WinDLL("kernel32")
            kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel32.CloseHandle.restype = wintypes.BOOL
            kernel32.CloseHandle(self._handle)
            self._handle = None


class _Publisher:
    """A throwaway machine: source tree, user home, LOCALAPPDATA, runner."""

    def __init__(self, base: Path):
        self.base = base
        self.source = base / "source"
        self.home = base / "user home"
        self.local = self.home / "AppData" / "Local"
        self._generation = 1
        self._build_source()
        self.host_is_installed()

    # -- fixture ---------------------------------------------------------
    def _build_source(self) -> None:
        self.source.mkdir(parents=True)
        for rel in _surface_files():
            src = ROOT / rel
            if not src.is_file():
                continue
            dst = self.source / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        for name in (".gitignore",):
            src = ROOT / name
            if src.is_file():
                shutil.copy2(src, self.source / name)
        self._git("init", "-q")
        self._git("add", "-A")
        self._git("-c", "user.name=fixture", "-c", "user.email=f@x",
                  "commit", "-q", "-m", "fixture")

    def _git(self, *args: str) -> str:
        out = subprocess.run(
            ["git", "-C", str(self.source), *args],
            capture_output=True,
            text=True,
            check=True,
        )
        return out.stdout

    def env(self) -> dict:
        env = {k: v for k, v in os.environ.items() if not k.startswith("SAIPEN_")}
        env.update(
            HOME=str(self.home),
            USERPROFILE=str(self.home),
            HOMEDRIVE=str(self.home.drive),
            HOMEPATH=str(self.home.anchor),
            LOCALAPPDATA=str(self.local),
            XDG_CONFIG_HOME=str(self.home / ".config"),
            PYTHONUTF8="1",
            PYTHONDONTWRITEBYTECODE="1",
            SAIPEN_PYTHON=sys.executable,
        )
        env.pop("ZAICODE_HOME", None)
        self.home.mkdir(parents=True, exist_ok=True)
        self.local.mkdir(parents=True, exist_ok=True)
        return env

    # -- host surfaces ---------------------------------------------------
    def plugin_skill(self, plugin: str) -> Path:
        return self.home / ".gemini" / "config" / "plugins" / plugin / "skills" / "saipen"

    def gemini_skill(self) -> Path:
        return self.home / ".gemini" / "skills" / "saipen"

    def host_is_installed(self) -> None:
        """This machine has exactly the hosts the incident machine had.

        Host detection is per-adapter and honest: a home the user never
        installed is SKIPPED, so the fixture has to look like a machine where
        Gemini runs and the Antigravity IDE has loaded two plugins. Nothing
        else -- no Claude, no Codex, no Kiro -- which is what makes test E
        meaningful.
        """
        self.gemini_skill().parent.mkdir(parents=True, exist_ok=True)
        for plugin in ("my_custom", "science"):
            self.plugin_skill(plugin).parent.mkdir(parents=True, exist_ok=True)

    def install(self) -> None:
        """Publish generation 1 for real, so every install is a real install.

        A hand-written stub directory would prove nothing: the injector would
        only ever create it, never swap it, and the code under test here is the
        swap. After this call the consumer homes hold a genuine generation with
        provenance, which is exactly what the incident left behind.
        """
        run = self.publish()
        if run.returncode != 0:
            raise AssertionError(
                f"fixture install failed rc={run.returncode}" + chr(10)
                + run.stdout + run.stderr + self.log_text()
            )
        surfaces = [self.gemini_skill()]
        surfaces += [self.plugin_skill(p) for p in ("my_custom", "science")]
        for skill in surfaces:
            if not (skill / ".saipen_runtime.json").is_file():
                raise AssertionError(f"fixture install left no provenance in {skill}")

    def bump_generation(self) -> None:
        """Ship a NEW runtime generation, so a later run has work to do.

        `saipen/BOOT.md` is declared in saipen/MANIFEST.json, so editing it in
        the fixture commit changes the manifest-derived fingerprint both the
        installed copies and the source are proven against.
        """
        self._generation += 1
        boot = self.source / "saipen" / "BOOT.md"
        with boot.open("a", encoding="utf-8") as handle:
            handle.write(f"\n<!-- fixture generation {self._generation} -->\n")
        self._git("add", "-A")
        self._git("-c", "user.name=fixture", "-c", "user.email=f@x",
                  "commit", "-q", "-m", f"fixture generation {self._generation}")

    def provenance(self, skill: Path) -> dict:
        return json.loads((Path(skill) / ".saipen_runtime.json").read_text(encoding="utf-8"))

    # -- the run ---------------------------------------------------------
    def publish(self, timeout: int = 900) -> subprocess.CompletedProcess:
        return subprocess.run(
            [
                POWERSHELL,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(self.source / "bootstrap" / "schedule-run.ps1"),
                "-CloneRoot",
                str(self.source),
            ],
            env=self.env(),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )

    # -- what came out ---------------------------------------------------
    @property
    def log(self) -> Path:
        return self.local / "saipen" / "inject.log"

    def log_text(self) -> str:
        return self.log.read_text(encoding="utf-8", errors="replace") if self.log.is_file() else ""

    def convergence(self) -> dict:
        path = self.local / "saipen" / "convergence.json"
        if not path.is_file():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def published(self) -> Path:
        return self.local / "saipen" / "scheduled-source"

    def published_head(self) -> str:
        head = self.published() / "VERSION"
        return head.read_text(encoding="utf-8").strip() if head.is_file() else ""

    def published_generation(self) -> int:
        """Which fixture generation the published source actually carries.

        VERSION is identical across fixture generations, so the marker written
        into a shipped runtime document is the only honest witness of which
        generation a rollback left behind.
        """
        boot = self.published() / "saipen" / "BOOT.md"
        return _generation_of(boot.read_text(encoding="utf-8") if boot.is_file() else "")

    def source_version(self) -> str:
        return (self.source / "VERSION").read_text(encoding="utf-8").strip()

    def source_generation(self) -> int:
        return _generation_of((self.source / "saipen" / "BOOT.md").read_text(encoding="utf-8"))

    def consumer(self, name: str) -> dict | None:
        for row in self.convergence().get("consumers") or ():
            if row.get("consumer") == name:
                return row
        return None


@unittest.skipUnless(IS_WINDOWS and POWERSHELL, "the scheduled publisher is Windows-only")
class PublicationConvergenceTests(unittest.TestCase):
    """One real publisher run per phase, on a real lock."""

    def setUp(self) -> None:
        self._base = Path(tempfile.mkdtemp(prefix="saipen-t1613-"))
        self.box = _Publisher(self._base)

    def tearDown(self) -> None:
        shutil.rmtree(self._base, ignore_errors=True)

    def test_A_B_H_I_the_locked_plugins_defer_and_the_publication_stays(self):
        # The live topology, exactly: Gemini's own surface writable, both
        # plugin-local copies held open by a running IDE.
        box = self.box
        box.install()
        previous = {p: box.provenance(box.plugin_skill(p))["runtime_fingerprint"]
                    for p in ("my_custom", "science")}
        gemini_before = box.provenance(box.gemini_skill())["runtime_fingerprint"]
        box.bump_generation()

        with _DirectoryLock(box.plugin_skill("my_custom")), _DirectoryLock(
            box.plugin_skill("science"), asks_delete=False
        ):
            run = box.publish()
        record = box.convergence()

        with self.subTest("A publication survives a locked non-blocking consumer"):
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr + box.log_text())
            self.assertEqual(record.get("publication"), "CURRENT")
            self.assertEqual(record.get("requires_human"), False)
            self.assertEqual(record.get("convergence"), "DEGRADED")
            self.assertEqual(
                box.published_generation(), box.source_generation(),
                "scheduled-source must hold the generation this run published",
            )
        with self.subTest("A both locked consumers are pending, not failed"):
            self.assertEqual(len(record.get("pending") or []), 2, record)
            for plugin in ("my_custom", "science"):
                row = box.consumer(f"Antigravity [{plugin}]")
                self.assertIsNotNone(row, record)
                self.assertEqual(row["result"], "DEFERRED_RETRYABLE", row)
                self.assertFalse(row["blocking"], "antigravity is declared non-blocking")
        with self.subTest("B the writable primary surface still converged"):
            primary = box.consumer("Gemini CLI / Antigravity skill")
            self.assertIsNotNone(primary, record)
            self.assertEqual(primary["result"], "APPLIED", primary)
        with self.subTest("H nothing rolled the writable consumer back"):
            self.assertTrue((box.gemini_skill() / "BOOT.md").is_file())
            self.assertNotEqual(
                box.provenance(box.gemini_skill())["runtime_fingerprint"], gemini_before,
                "the writable consumer must be on the published generation",
            )
            for plugin, fingerprint in previous.items():
                self.assertEqual(
                    box.provenance(box.plugin_skill(plugin))["runtime_fingerprint"], fingerprint,
                    f"a deferred consumer keeps its known-good {plugin} install",
                )
                leftovers = list(box.plugin_skill(plugin).parent.glob(".*saipen-*"))
                self.assertEqual(leftovers, [], f"stale stage/backup under {plugin}")
        with self.subTest("I status keeps publication and convergence apart"):
            report = self._distribution_report()
            self.assertEqual(report["publication"], "CURRENT")
            self.assertEqual(report["consumer_convergence"], "DEGRADED")
            self.assertEqual(len(report["pending_consumers"]), 2)
            self.assertFalse(report["requires_human"])
            self.assertFalse(report["consumers_converged"], "pending consumers are not convergence")
            self.assertIn("no operator action", report["summary"])
        with self.subTest("J the run never asks a human to close anything"):
            text = box.log_text().lower()
            self.assertNotIn("close antigravity", text)
            self.assertNotIn("wait_user", text)

    def test_C_K_the_next_run_converges_the_deferred_consumers_without_a_human(self):
        box = self.box
        box.install()
        box.bump_generation()
        with _DirectoryLock(box.plugin_skill("my_custom")), _DirectoryLock(
            box.plugin_skill("science"), asks_delete=False
        ):
            locked = box.publish()
        self.assertEqual(locked.returncode, 0, locked.stdout + locked.stderr)
        self.assertEqual(len(box.convergence().get("pending") or []), 2)

        # The only thing that changed between the two runs is that the IDE let
        # go of the directories. No manual invocation, no operator, no restart.
        run = box.publish()
        record = box.convergence()

        with self.subTest("C pending clears once the lock is gone"):
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr + box.log_text())
            self.assertEqual(record.get("publication"), "CURRENT")
            self.assertEqual(record.get("convergence"), "CURRENT")
            self.assertEqual(record.get("pending"), [])
        for plugin in ("my_custom", "science"):
            with self.subTest(f"K {plugin} converged to the published generation"):
                row = box.consumer(f"Antigravity [{plugin}]")
                self.assertIsNotNone(row, record)
                self.assertIn(row["result"], ("APPLIED", "ALREADY_CURRENT"), row)
                installed = box.provenance(box.plugin_skill(plugin))
                self.assertEqual(
                    installed["runtime_fingerprint"],
                    box.provenance(box.gemini_skill())["runtime_fingerprint"],
                    f"{plugin} now proves the same generation as the writable consumer",
                )

    def test_D_an_install_already_holding_this_generation_is_not_rewritten(self):
        box = self.box
        box.install()
        run = box.publish()
        record = box.convergence()
        self.assertEqual(run.returncode, 0, run.stdout + run.stderr + box.log_text())
        applied = [r for r in record["consumers"] if r["result"] == "APPLIED"]
        self.assertEqual(applied, [], "a converged consumer must not be re-copied")
        current = [r for r in record["consumers"] if r["result"] == "ALREADY_CURRENT"]
        self.assertTrue(current, record["consumers"])

    def test_E_a_host_this_machine_never_installed_is_skipped_not_created(self):
        box = self.box
        box.install()
        record = box.convergence()
        row = box.consumer("Kiro")
        self.assertIsNotNone(row, record)
        self.assertEqual(row["result"], "SKIPPED_NOT_INSTALLED", row)
        self.assertFalse((box.home / ".kiro").exists())

    # -- the failure side -------------------------------------------------
    def test_F_a_dirty_injected_surface_refuses_before_publishing(self):
        box = self.box
        box.install()
        generation_before = box.published_generation()
        marker = box.source / "saipen" / "CORE.md"
        marker.write_text(marker.read_text(encoding="utf-8") + "\nedited\n", encoding="utf-8")
        try:
            run = box.publish()
        finally:
            self._git(box, "checkout", "--", "saipen/CORE.md")
        with self.subTest("F the known-good published generation is retained"):
            self.assertNotEqual(run.returncode, 0)
            self.assertIn("DIRTY_SOURCE", box.log_text())
            self.assertEqual(box.published_generation(), generation_before)
            self.assertEqual(box.convergence().get("convergence"), "CURRENT")

    def test_G_a_terminal_failure_on_a_blocking_surface_still_fails_closed(self):
        # A failure that is not contention: the destination's own parent is a
        # FILE, so staging cannot start and no retry can ever help. Gemini is
        # a blocking surface, so the publication must not be left standing on
        # half its consumers.
        box = self.box
        box.install()
        generation_before = box.published_generation()
        skills = box.gemini_skill().parent
        shutil.rmtree(skills, ignore_errors=True)
        skills.write_text("not a directory\n", encoding="utf-8")
        try:
            run = box.publish()
            record = box.convergence()
            log = box.log_text()
        finally:
            skills.unlink()
        with self.subTest("G a blocking failure is fatal, not deferred"):
            self.assertNotEqual(run.returncode, 0, run.stdout + run.stderr)
            row = box.consumer("Gemini CLI / Antigravity skill")
            self.assertIsNotNone(row, record)
            self.assertEqual(row["result"], "FAILED_TERMINAL", row)
            self.assertTrue(row["blocking"], row)
        with self.subTest("G the invalid publication is rolled back"):
            self.assertEqual(record.get("publication"), "ROLLED_BACK")
            self.assertEqual(box.published_generation(), generation_before)
            self.assertIn("exit=1", log)

    # -- helpers ----------------------------------------------------------
    def _git(self, box: "_Publisher", *args: str) -> None:
        subprocess.run(["git", "-C", str(box.source), *args], check=True, capture_output=True)

    def _distribution_report(self) -> dict:
        """The exact object `saipen status` embeds, on the sandbox machine."""
        import autoinject

        env = self.box.env()
        # The pin the T-1552 audit names: the sandbox machine's paths, not the
        # host's, for the whole of the read.
        with mock.patch.dict(
            os.environ,
            {
                "LOCALAPPDATA": env["LOCALAPPDATA"],
                "USERPROFILE": env["USERPROFILE"],
                "HOME": env["HOME"],
            },
        ):
            report = autoinject.distribution_report()
        report["summary"] = autoinject.distribution_line(report)
        return report


class NeighbouringSuitesStayGreenTests(unittest.TestCase):
    """L: the change is contained -- install and distribution owners stay green."""

    def test_L_installation_and_distribution_suites(self):
        if not IS_WINDOWS:
            self.skipTest("Windows-only installers")
        loader = unittest.TestLoader()
        names = [
            "test_distribution_report",
            "test_t1454_distribution_blocker",
            "test_inject_digest",
            "test_runtime_generation_identity",
        ]
        suite = unittest.TestSuite(loader.loadTestsFromName(name) for name in names)
        with open(os.devnull, "w") as sink, nested_run():
            result = unittest.TextTestRunner(stream=sink, verbosity=0).run(suite)
        broken = [str(f[0]) for f in result.failures + result.errors]
        self.assertTrue(result.wasSuccessful(), broken)


if __name__ == "__main__":
    unittest.main()
