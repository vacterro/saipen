"""T-1934: a repaired adapter artifact must reach the host, not just the clone.

MEASURED 26.10.26 (during T-1933): a repair added `declared_action()` to
`extensions/adapters/zaicode/saipen-guard.py` (sha256 4317be7f...) and the
ticket closed green, while the hook the operator's host actually executes
(`~/.zcode/hooks/saipen-guard.py`) stayed the pre-fix generation (sha256
57f81cfd..., no `declared_action`). Every prompt therefore kept being sealed as
`continue`, `operator_origin` never minted a persistent grant, and the 20-ticket
safety valve kept tripping.

Detection was never the missing piece: `install_host_guard.py zaicode --check`
had already answered `current:false problems:["artifact-stale"]`. What these
tests hold is the pair of properties a redeploy needs, for EVERY host the
installer can act on:

  * editing the SHIPPED artifact makes an already-installed hook read STALE,
    `artifact-stale` named and the artifact still `installed` (a diagnostic
    that said "missing" would send the operator to the wrong repair);
  * re-running the installer puts the shipped bytes on the host surface
    byte-for-byte, and the very next check reads current with no problems.

The verdicts are asserted through `install(...)` for every host, and through
the CLI an operator actually runs. The last test is the red control: with the
shipped-bytes comparison blinded, the same drifted fixture reports CURRENT,
which is what proves the tests above exercise the comparison and not the
fixture.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
REPO = TOOLS.parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import install_host_guard as G  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

#: The hosts `tools/install_host_guard.py` accepts (its CLI argument choices).
#: Spelled here so a host the installer cannot act on never silently enters the
#: matrix below; `test_the_matrix_covers_every_host_the_installer_accepts`
#: pins this list against the installer itself.
INSTALLER_HOSTS = ("claude", "codex", "gemini", "kiro", "zaicode")

#: A source root that proves a generation needs the manifest-declared surface,
#: not only the artifact under test (T-1342 compares generations, not paths).
_MINI_MANIFEST = {
    "copy_trees": [
        {"src": "tools", "dst": "tools"},
        {"src": "extensions/adapters", "dst": "extensions/adapters"},
    ],
    "files": [
        {"src": "saipen/MANIFEST.json", "required": True},
        {"src": "saipen/BOOT.md", "required": True},
        {"src": "saipen/CORE.md", "required": True},
        {"src": "VERSION", "required": True},
    ],
}


def setUpModule() -> None:
    # An outer ZAICODE/Claude session must never bind these fixtures: the
    # carriers it exports include ZAICODE_HOME and CLAUDE_CONFIG_DIR, and an
    # installer fixture that inherited either would deploy into the operator's
    # real profile instead of the throwaway home below.
    isolate_host_session()


def _registry(root: Path) -> dict:
    return json.loads((root / "extensions" / "adapters" / "registry.json").read_text(encoding="utf-8"))


def _source_root(base: Path) -> Path:
    """A minimal source root the installer accepts as its authority."""
    (base / "saipen").mkdir(parents=True)
    (base / "saipen" / "MANIFEST.json").write_text(
        json.dumps(_MINI_MANIFEST, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    (base / "saipen" / "BOOT.md").write_text("# BOOT\n", encoding="utf-8")
    (base / "saipen" / "CORE.md").write_text("# CORE\n", encoding="utf-8")
    (base / "VERSION").write_text("7.t\n", encoding="utf-8")
    (base / "tools").mkdir()
    (base / "tools" / "saipen.py").write_bytes((REPO / "tools" / "saipen.py").read_bytes())
    (base / "extensions" / "adapters").mkdir(parents=True)
    shutil.copy(
        REPO / "extensions" / "adapters" / "registry.json",
        base / "extensions" / "adapters" / "registry.json",
    )
    for entry in _registry(REPO)["adapters"]:
        artifact = entry.get("hook_artifact")
        if not artifact:
            continue
        destination = base / artifact
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(REPO / artifact, destination)
    return base


class _Fixture(unittest.TestCase):
    """A throwaway source root + host home, with the installer's authority bound."""

    def fixture(self) -> tuple[Path, Path]:
        base = Path(tempfile.mkdtemp(prefix="t1934-deploy-"))
        self.addCleanup(shutil.rmtree, base, True)
        root = _source_root(base / "source")
        home = base / "home"
        home.mkdir()
        patcher = mock.patch.object(G, "ROOT", root)
        patcher.start()
        self.addCleanup(patcher.stop)
        return root, home

    def shipped(self, root: Path, host: str) -> Path:
        entry = next(item for item in _registry(root)["adapters"] if item["id"] == host)
        return root / entry["hook_artifact"]

    def install(self, host: str, home: Path, root: Path) -> dict:
        result = G.install(host, home, root)
        self.assertTrue(result["installed"], result)
        activation = result.get("activation")
        self.assertTrue(activation is None or activation.get("activated"), result)
        return result

    def check(self, host: str, home: Path, root: Path) -> dict:
        return G.install(host, home, root, check=True)


class MatrixTests(_Fixture):
    def test_the_matrix_covers_every_host_the_installer_accepts(self):
        # The installer's CLI takes a CLOSED set of ids. An adapter the registry
        # gives a hook to but the CLI refuses would be silently uncovered, so
        # the matrix is pinned against the CLI's own help output rather than
        # against a list that can drift.
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "install_host_guard.py"), "--help"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        choices = proc.stdout.split("{", 1)[1].split("}", 1)[0].split(",")
        self.assertEqual(sorted(choices), sorted(INSTALLER_HOSTS), proc.stdout)
        for host in INSTALLER_HOSTS:
            with self.subTest(host=host):
                entry = next(item for item in _registry(REPO)["adapters"] if item["id"] == host)
                self.assertTrue(entry.get("hook_artifact"), entry)
                self.assertTrue(entry.get("hook_install_surface"), entry)

    def test_a_source_artifact_edit_makes_an_installed_hook_read_stale(self):
        for host in INSTALLER_HOSTS:
            with self.subTest(host=host):
                root, home = self.fixture()
                surface = Path(self.install(host, home, root)["artifact"])
                self.assertEqual(surface.read_bytes(), self.shipped(root, host).read_bytes())
                before = self.check(host, home, root)
                self.assertTrue(before["current"], before)
                self.assertEqual(before["problems"], [], before)

                # The repair ships in the SOURCE artifact -- the T-1933 shape.
                shipped = self.shipped(root, host)
                shipped.write_bytes(shipped.read_bytes() + b"\n# source repair\n")

                after = self.check(host, home, root)
                self.assertFalse(after["current"], after)
                self.assertIn("artifact-stale", after["problems"], after)
                # The hook is still there and still configured: the ONLY thing
                # wrong is its bytes, and the diagnostic has to say exactly that.
                self.assertTrue(after["installed"], after)
                self.assertTrue(after["configured"], after)
                self.assertEqual(after["effective"], "ENFORCEMENT_GAP", after)
                # The operator's host still holds the pre-repair generation.
                self.assertNotEqual(surface.read_bytes(), shipped.read_bytes())

    def test_redeploy_puts_the_shipped_bytes_on_the_surface(self):
        for host in INSTALLER_HOSTS:
            with self.subTest(host=host):
                root, home = self.fixture()
                surface = Path(self.install(host, home, root)["artifact"])
                shipped = self.shipped(root, host)
                shipped.write_bytes(shipped.read_bytes() + b"\n# source repair\n")
                self.assertFalse(self.check(host, home, root)["current"])

                self.install(host, home, root)

                self.assertEqual(surface.read_bytes(), shipped.read_bytes())
                after = self.check(host, home, root)
                self.assertTrue(after["current"], after)
                self.assertEqual(after["problems"], [], after)


class CommandLineTests(unittest.TestCase):
    """The operator and every gate read this JSON, never a module return value."""

    def test_the_check_cli_separates_current_from_drifted(self):
        home = Path(tempfile.mkdtemp(prefix="t1934-cli-"))
        self.addCleanup(shutil.rmtree, home, True)

        def run(*arguments: str) -> tuple[int, dict]:
            proc = subprocess.run(
                [sys.executable, str(TOOLS / "install_host_guard.py"), *arguments],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(REPO),
            )
            return proc.returncode, json.loads(proc.stdout)

        code, installed = run("zaicode", "--home", str(home))
        self.assertEqual(code, 0, installed)
        self.assertTrue(installed["current"], installed)

        code, fresh = run("zaicode", "--home", str(home), "--check")
        self.assertEqual(code, 0, fresh)
        self.assertTrue(fresh["current"], fresh)
        self.assertEqual(fresh["problems"], [], fresh)
        self.assertEqual(fresh["effective"], "UNKNOWN", fresh)

        # Drift the INSTALLED surface. Editing the shipped artifact instead
        # would mean mutating the operator's live repository from a test; the
        # source-edit direction is proven per host above, and the verdict this
        # asserts is the one an operator reads.
        artifact = Path(installed["artifact"])
        artifact.write_bytes(artifact.read_bytes() + b"\n# drifted\n")

        code, drifted = run("zaicode", "--home", str(home), "--check")
        self.assertEqual(code, 0, drifted)
        self.assertFalse(drifted["current"], drifted)
        self.assertEqual(drifted["problems"], ["artifact-stale"], drifted)
        self.assertTrue(drifted["installed"], drifted)
        self.assertEqual(drifted["effective"], "ENFORCEMENT_GAP", drifted)


class RedControlTests(_Fixture):
    def test_a_blinded_byte_comparison_would_call_a_drifted_hook_current(self):
        """Without the comparison the fixture is indistinguishable from a deploy.

        This is the defect restated: `--check` answered `artifact-stale` and the
        installation still differed from the source. If the shipped-bytes
        comparison is what produces that verdict, blinding it must make the same
        drifted fixture read CURRENT -- otherwise the tests above prove the
        fixture, not the check.
        """
        root, home = self.fixture()
        surface = Path(self.install("zaicode", home, root)["artifact"])
        shipped = self.shipped(root, "zaicode")
        surface.write_bytes(surface.read_bytes() + b"\n# not the shipped artifact\n")

        honest = self.check("zaicode", home, root)
        self.assertFalse(honest["current"], honest)
        self.assertEqual(honest["problems"], ["artifact-stale"], honest)

        with mock.patch.object(G, "content_bytes", lambda raw: b"identical"):
            blinded = self.check("zaicode", home, root)
        self.assertTrue(blinded["current"], blinded)
        self.assertEqual(blinded["problems"], [], blinded)
        self.assertNotEqual(surface.read_bytes(), shipped.read_bytes())


if __name__ == "__main__":
    unittest.main()
