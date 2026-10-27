"""T-1650: a host that renamed its running image on self-update is still that host.

Measured 2026-10-06 19:10:12Z: Claude Code updated itself while a session was
open. Windows cannot replace a running image, so the updater renamed it to
`claude.exe.old.1791313812470.21156` beside a new `claude.exe`. The authority
recognised a host by the registered image basename, so every later hook run of
that session was refused NOT_HOST_DESCENDANT -- 36 admitted before the rename,
none after -- until the host was restarted, which nothing told the operator.

The retired name ends in the pid of the process it belongs to. That is the
proof used here: the suffix is honoured only on a registered image and only
when it carries the pid of the process whose image it is.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import test_t1624_host_integration as T  # noqa: E402

HI, HP, F = T.HI, T.HP, T.F
BIN = "c:/users/v/.local/bin/"


def retired_host(pid: int = 10, suffix_pid: int | None = None, image: str = "claude.exe"):
    name = f"{image}.old.1791313812470.{pid if suffix_pid is None else suffix_pid}"
    return F(pid, 1, BIN + name, name, ("claude.exe",), 100)


class RetiredImageShapeTests(unittest.TestCase):
    def test_the_measured_name_is_the_image_it_was_started_as(self):
        self.assertEqual(
            HI.retired_image(BIN + "claude.exe.old.1791313812470.21156", 21156),
            BIN + "claude.exe",
        )
        self.assertEqual(
            HI.retired_image(r"C:\Users\V\.local\bin\claude.exe.old.1791313812470.21156", 21156),
            BIN + "claude.exe",
        )

    def test_the_suffix_must_name_the_process_itself(self):
        name = BIN + "claude.exe.old.1791313812470.21156"
        for pid in (21157, 2115, 0, None, "x"):
            self.assertIsNone(HI.retired_image(name, pid), pid)

    def test_other_names_are_not_a_retired_image(self):
        for name in (
            "claude.exe",
            "claude.exe.old",
            "claude.exe.old.21156",
            "claude.exe.old.abc.21156",
            "claude.exe.old.123.21156",
            "claude.exe.bak.1791313812470.21156",
            "claude.exe.old.1791313812470.21156.exe",
        ):
            self.assertIsNone(HI.retired_image(BIN + name, 21156), name)


class SelfUpdatedHostTests(unittest.TestCase):
    """The proof on the measured chain shape (host -> bash -> bash -> hook ->
    engine), with the fixtures of the T-1624 identity cases."""

    def prove(self, chain, policy=T.POLICY, signer="Anthropic, PBC"):
        return HI.prove_hook_invocation(
            chain,
            policy,
            signer_of=lambda _path: signer,
            artifact_current=lambda _path: True,
        )

    def assert_refused(self, chain, reason, **kwargs):
        proof = self.prove(chain, **kwargs)
        self.assertFalse(proof.ok, proof.detail)
        self.assertEqual(proof.reason, reason, proof.detail)
        self.assertTrue(proof.detail)

    def test_the_unrenamed_host_is_still_proven(self):
        self.assertTrue(self.prove(self.chain(T.HOST)).ok)

    def chain(self, host):
        return [T.ENGINE_PROC, T.HOOK_PROC, T.BASH_INNER, T.BASH_OUTER, host]

    def test_a_host_running_under_its_retired_image_is_proven(self):
        proof = self.prove(self.chain(retired_host()))
        self.assertTrue(proof.ok, proof.detail)
        self.assertEqual((proof.host_pid, proof.hook_pid), (10, 40))
        self.assertEqual(proof.host_signer, "Anthropic, PBC")

    def test_the_signer_is_read_from_the_file_that_is_running(self):
        asked = []

        def signer(path):
            asked.append(path)
            return "Anthropic, PBC"

        proof = HI.prove_hook_invocation(
            self.chain(retired_host()),
            T.POLICY,
            signer_of=signer,
            artifact_current=lambda _path: True,
        )
        self.assertTrue(proof.ok, proof.detail)
        self.assertEqual(asked, [BIN + "claude.exe.old.1791313812470.10"])

    def test_a_retired_image_with_another_signer_is_refused(self):
        self.assert_refused(
            self.chain(retired_host()), HI.REASON_HOST_IMAGE_UNVERIFIED, signer="Somebody Else"
        )

    def test_a_suffix_naming_another_pid_is_refused_and_says_restart(self):
        chain = self.chain(retired_host(suffix_pid=999))
        self.assert_refused(chain, HI.REASON_NOT_HOST_DESCENDANT)
        detail = self.prove(chain).detail
        self.assertIn("claude.exe.old.1791313812470.999", detail)
        self.assertIn("restart it", detail)

    def test_an_unregistered_image_with_the_suffix_is_refused(self):
        self.assert_refused(
            self.chain(retired_host(image="evil.exe")), HI.REASON_NOT_HOST_DESCENDANT
        )
        self.assertNotIn("restart", self.prove(self.chain(retired_host(image="evil.exe"))).detail)

    def test_a_registered_path_matches_only_its_own_directory(self):
        policy = HI.IdentityPolicy(
            host="claude",
            host_images=(BIN + "claude.exe",),
            hook_artifacts=(T.GUARD,),
        )
        self.assertTrue(self.prove(self.chain(retired_host()), policy=policy).ok)
        elsewhere = F(
            10,
            1,
            "c:/temp/claude.exe.old.1791313812470.10",
            "claude.exe.old.1791313812470.10",
            ("claude.exe",),
            100,
        )
        self.assertFalse(self.prove(self.chain(elsewhere), policy=policy).ok)

    def test_a_tool_shell_under_a_retired_host_is_still_not_the_hook(self):
        cli = F(60, 31, T.PY, "python.exe", (T.PY, "tools/saipen.py", "admission"), 600)
        self.assert_refused(
            [cli, T.TOOL_INNER, T.TOOL_OUTER, retired_host()], HI.REASON_HOOK_NOT_FOUND
        )


class DiagnosticAncestorTests(unittest.TestCase):
    def test_the_name_level_view_sees_the_retired_host(self):
        chain = [T.HOOK_PROC, T.BASH_INNER, T.BASH_OUTER, retired_host()]
        with mock.patch.object(HP, "ancestry", return_value=chain):
            found = HP.host_ancestor(40, ["claude.exe", "claude"])
        self.assertIsNotNone(found)
        self.assertEqual(found.pid, 10)

    def test_the_name_level_view_refuses_another_pid(self):
        chain = [T.HOOK_PROC, T.BASH_INNER, T.BASH_OUTER, retired_host(suffix_pid=999)]
        with mock.patch.object(HP, "ancestry", return_value=chain):
            self.assertIsNone(HP.host_ancestor(40, ["claude.exe", "claude"]))


@unittest.skipUnless(os.name == "nt", "the rename is what a Windows updater does to its image")
class RealRenamedImageTests(unittest.TestCase):
    """Operating-system facts, nothing mocked: the image file of a RUNNING
    process is renamed the way a self-updating host renames its own, and the
    platform is asked what that process's image is."""

    IMAGES = ("claude.exe", "claude")

    def _renamed(self, own_pid: bool):
        folder = Path(tempfile.mkdtemp(prefix="saipen-t1650-"))
        self.addCleanup(shutil.rmtree, folder, True)
        system = Path(os.environ.get("SYSTEMROOT") or "C:/Windows") / "System32" / "ping.exe"
        image = folder / "claude.exe"
        shutil.copyfile(system, image)
        child = subprocess.Popen(
            [str(image), "-n", "30", "127.0.0.1"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.addCleanup(child.wait, 10)
        self.addCleanup(child.kill)
        suffix = child.pid if own_pid else child.pid + 100000
        os.replace(image, folder / f"claude.exe.old.1791313812470.{suffix}")
        fact = HP.process_fact(child.pid)
        self.assertIsNotNone(fact)
        return fact, suffix

    def test_the_platform_reports_the_renamed_path_and_the_host_is_recognised(self):
        fact, suffix = self._renamed(own_pid=True)
        self.assertEqual(fact.name, f"claude.exe.old.1791313812470.{suffix}")
        self.assertFalse(HI._name_matches(fact.image, self.IMAGES))
        self.assertTrue(HI._host_matches(fact, self.IMAGES))

    def test_a_running_image_renamed_with_another_pid_is_not_the_host(self):
        fact, suffix = self._renamed(own_pid=False)
        self.assertEqual(fact.name, f"claude.exe.old.1791313812470.{suffix}")
        self.assertFalse(HI._host_matches(fact, self.IMAGES))


if __name__ == "__main__":
    unittest.main()
