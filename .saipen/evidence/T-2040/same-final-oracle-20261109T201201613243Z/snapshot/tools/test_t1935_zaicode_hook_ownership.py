"""T-1935: the ZAICODE guard hook needs an owner that DEPLOYS and SEES it.

MEASURED 26.10.26 while closing T-1934. ZAICODE was the only adapter that ships
a `hook_artifact` while declaring neither `install.hook` nor `hook_installer`.
Two consequences, both reproduced in a throwaway home with `USERPROFILE`, `HOME`
and `ZAICODE_HOME` redirected:

  * `bootstrap/inject.ps1` and `bootstrap/inject.sh` run their hook step only
    under `install.hook`, so the canonical injector deployed ZAICODE's skill and
    instruction block and silently skipped its guard hook. The T-1933 repair
    reached the live surface only because it was installed by hand -- which is
    exactly how the 20-ticket safety valve kept tripping after a green ticket;
  * `runtime_bootstrap.hook_problems` returns `[]` when `install.hook` is
    absent, so `saipen runtime --prelaunch` and `saipen host doctor` -- the two
    observers wired to the prelaunch gate -- called a drifted ZAICODE hook
    current. The same drifted bytes answered `[]` for the shipped entry and
    `["hook-stale"]` once `install.hook` was added.

The repair is a registry declaration, not a deployment-topology change: ZAICODE
already executes `~/.zcode/hooks/saipen-guard.py` (its `cli/config.json` names
it), so `hook_install_surface` always described that file. These tests pin the
declaration, the split between the isolated home and the profile hook surface,
and both observers.

Every fixture is a temp directory. Nothing here reads or writes the operator's
real `~/.zcode`.
"""

from __future__ import annotations

import json
import os
import shutil
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
from saipen_engine import runtime_bootstrap as RB  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

REGISTRY = REPO / "extensions" / "adapters" / "registry.json"
#: The host-side variables that select a ZAICODE profile. All three have to be
#: redirected: `install.hook` expands `~`, the skill expands `$ZAICODE_HOME`,
#: and an inherited CLAUDE_CONFIG_DIR would move the claude adapter's surfaces.
ZAICODE_CARRIERS = ("USERPROFILE", "HOME", "ZAICODE_HOME", "CLAUDE_CONFIG_DIR")


def setUpModule() -> None:
    isolate_host_session()


def _adapter() -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8-sig"))
    return next(entry for entry in registry["adapters"] if entry["id"] == "zaicode")


class Redirected:
    """A throwaway operator profile plus a throwaway isolated ZAICODE home."""

    def __init__(self) -> None:
        self.base = Path(tempfile.mkdtemp(prefix="t1935-zaicode-"))
        self.profile = self.base / "profile"
        self.profile.mkdir()
        self.zaicode_home = self.base / "zhome"
        (self.zaicode_home / ".zcode").mkdir(parents=True)
        self._saved: dict[str, str | None] = {}

    def __enter__(self) -> "Redirected":
        for name in ZAICODE_CARRIERS:
            self._saved[name] = os.environ.get(name)
        os.environ["USERPROFILE"] = os.environ["HOME"] = str(self.profile)
        os.environ["ZAICODE_HOME"] = str(self.zaicode_home)
        os.environ.pop("CLAUDE_CONFIG_DIR", None)
        return self

    def __exit__(self, *exc_info) -> None:
        for name, value in self._saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
        shutil.rmtree(self.base, ignore_errors=True)

    @property
    def hook(self) -> Path:
        return self.profile / ".zcode" / "hooks" / "saipen-guard.py"


class DeclarationTests(unittest.TestCase):
    def test_the_adapter_declares_a_deployer_and_a_hook_freshness_surface(self):
        adapter = _adapter()
        # Before T-1935 both of these were absent, which is what made the hook
        # undeployable and unobservable at once.
        self.assertEqual(adapter["hook_installer"], "tools/install_host_guard.py")
        self.assertTrue((REPO / adapter["hook_installer"]).is_file())
        self.assertIn("hook", adapter["freshness_surfaces"])
        self.assertIn("hook", adapter["install"])
        # The declared surface and the executable surface are the same file.
        self.assertEqual(adapter["install"]["hook"], adapter["hook_install_surface"])

    def test_the_skill_and_instruction_surfaces_stay_in_the_isolated_home(self):
        adapter = _adapter()
        for key in ("home", "skill", "instruction"):
            with self.subTest(key=key):
                self.assertTrue(
                    adapter["install"][key].startswith("$ZAICODE_HOME/"),
                    adapter["install"][key],
                )


class DeployTests(unittest.TestCase):
    def test_the_canonical_installer_puts_the_shipped_hook_on_the_profile(self):
        with Redirected() as world:
            result = G.install("zaicode", world.profile, REPO)
            self.assertTrue(result["current"], result)
            self.assertEqual(result["problems"], [], result)
            self.assertEqual(
                world.hook.read_bytes(),
                (REPO / _adapter()["hook_artifact"]).read_bytes(),
                "the installed hook must be the shipped bytes",
            )

    def test_the_injector_shell_hook_step_reaches_zaicode(self):
        """The registry row is what the injector's loop reads.

        The full injector is exercised by `test_t1504_zaicode_adapter`; what
        this pins is the exact predicate that skipped ZAICODE before the
        repair, read from the shipped registry rather than a fixture copy.
        """
        install = _adapter().get("install") or {}
        self.assertIn("hook", install, "inject.ps1/inject.sh gate on install.hook")
        self.assertTrue(install["hook"], install["hook"])


class ObserverTests(unittest.TestCase):
    def test_runtime_hook_problems_sees_zaicode_drift(self):
        """`prelaunch` and `doctor` both decide from this one function."""
        adapter = _adapter()
        with Redirected() as world:
            G.install("zaicode", world.profile, REPO)
            self.assertEqual(RB.hook_problems(adapter, REPO), [])
            world.hook.write_bytes(world.hook.read_bytes() + b"\n# drift\n")
            self.assertEqual(RB.hook_problems(adapter, REPO), ["hook-stale"])

    def test_prelaunch_refuses_a_drifted_zaicode_hook(self):
        with Redirected() as world:
            G.install("zaicode", world.profile, REPO)
            world.hook.write_bytes(world.hook.read_bytes() + b"\n# drift\n")
            report = RB.prelaunch("zaicode", skill_root=REPO, resync=False)
        self.assertFalse(report["ok"], report)
        self.assertEqual(report["code"], RB.PRELAUNCH_STALE, report)
        self.assertEqual(report["hook_problems"], ["hook-stale"], report)
        self.assertTrue(report["stale_before"], report)

    def test_prelaunch_resync_restores_the_shipped_hook_bytes(self):
        """The gate must repair, not just complain: the installer runs and the
        post-resync verdict is taken from the same observer."""
        with Redirected() as world:
            G.install("zaicode", world.profile, REPO)
            world.hook.write_bytes(world.hook.read_bytes() + b"\n# drift\n")
            report = RB.prelaunch("zaicode", skill_root=REPO, resync=True)
            restored = world.hook.read_bytes()
        self.assertTrue(report["ok"], report)
        self.assertEqual(report["code"], RB.PRELAUNCH_RESYNCED, report)
        self.assertEqual(report["hook_problems"], [], report)
        self.assertEqual(report["engine_diff"], [], report)
        self.assertTrue(report["resynced"], report)
        self.assertEqual(
            restored,
            (REPO / _adapter()["hook_artifact"]).read_bytes(),
            "resync must leave the shipped hook bytes on the profile surface",
        )


class DoctorTests(unittest.TestCase):
    """`saipen host doctor` reads `_hook_facts`, not `hook_problems`.

    `_hook_facts` takes the installer path only for adapters with
    `hook_installer`. Before the repair ZAICODE had none, so it fell through to
    `runtime_bootstrap.hook_problems`, which answers `[]` when `install.hook` is
    unset -- doctor called a byte-drifted hook current.
    """

    def test_doctor_flips_the_zaicode_hook_from_current_to_stale(self):
        from saipen_engine import host_integration as HI

        with Redirected() as world:
            G.install("zaicode", world.profile, REPO)
            fresh = HI.doctor(home=world.profile, only="zaicode")
            world.hook.write_bytes(world.hook.read_bytes() + b"\n# drift\n")
            drifted = HI.doctor(home=world.profile, only="zaicode")
        fresh_host = next(h for h in fresh["hosts"] if h["id"] == "zaicode")
        drifted_host = next(h for h in drifted["hosts"] if h["id"] == "zaicode")
        self.assertEqual(fresh_host["hook"], "current", fresh_host)
        self.assertEqual(drifted_host["hook"], "stale", drifted_host)
        self.assertIn(
            "artifact-stale", drifted_host["facts"]["hook"]["problems"], drifted_host
        )
        self.assertEqual(fresh_host["facts"]["hook"]["problems"], [], fresh_host)

    def test_a_different_root_spelling_with_a_proven_generation_is_accepted(self):
        """A FALSE ALARM found on the live host after the declaration landed.

        `_hook_facts` passes the INSTALLED runtime copy as the installer's
        checker, so the expectation it builds names that copy while the hook on
        disk correctly names the canonical source. The ZAICODE branch compared
        the whole argv exactly, which made the `--saipen-root` VALUE contract:
        the live host reported `hook: stale` with
        `problems: ["config-entry-differs", "delegated-root-stale"]` on bytes
        that were already correct.

        Every other branch had settled this (T-1338: the root is a spelling,
        T-1342: the generation it proves is contract, T-1624: the interpreter
        is the installing Python). This pins the same rule for the argv-shaped
        surface by calling the comparison directly -- a doctor fixture cannot
        reproduce it without first fabricating a behind-generation runtime
        copy, and the comparison is the whole defect.
        """
        expected = {
            "type": "process",
            "command": sys.executable,
            "args": ["-c", G.HOOK_BOOTSTRAP, r"C:\hooks\saipen-guard.py",
                     "--host", "zaicode", "--saipen-root", str(REPO)],
            "timeoutMs": 30000,
        }
        # A genuinely different SPELLING of the same root (this is the live
        # shape: doctor's expectation is built around the installed copy while
        # the hook names the canonical source). The old exact-args comparison
        # answered False here; the root-is-a-variable rule answers True.
        owned = {**expected, "args": list(expected["args"])}
        owned["args"][-1] = str(REPO).replace("\\", "/")
        self.assertNotEqual(owned["args"][-1], expected["args"][-1], "spellings must differ")
        self.assertTrue(G._same_process_entry(owned, expected))

    def test_a_root_that_proves_no_generation_is_still_stale(self):
        """The variable root must still prove a generation (T-1342), and every
        non-root argument stays contract."""
        expected = {
            "type": "process",
            "command": sys.executable,
            "args": ["-c", G.HOOK_BOOTSTRAP, r"C:\hooks\saipen-guard.py",
                     "--host", "zaicode", "--saipen-root", str(REPO)],
            "timeoutMs": 30000,
        }
        with Redirected() as world:
            bogus = world.base / "not-a-generation"
            bogus.mkdir()
            for bad in (
                {"args": expected["args"][:-1] + [str(bogus)]},
                # right root, wrong artifact
                {"args": expected["args"][:2] + [r"C:\hooks\other.py"] + expected["args"][3:]},
                # right everything, wrong timeout
                {"timeoutMs": 1000},
                # missing interpreter
                {"command": str(world.base / "no-such-python.exe")},
            ):
                with self.subTest(bad=bad):
                    owned = {**expected, **bad}
                    self.assertFalse(G._same_process_entry(owned, expected))

    def test_the_root_tolerance_hides_no_real_drift(self):
        """The tolerance must not become a blindfold (both observers).

        Loosening the argv comparison is only safe if every OTHER difference
        still reads stale. These are the three shapes the live host can produce:
        repaired bytes not redeployed, a config naming a root that proves no
        generation, and a config field other than the root changed.
        """
        from saipen_engine import host_integration as HI

        with Redirected() as world:
            G.install("zaicode", world.profile, REPO)
            config = world.profile / ".zcode" / "cli" / "config.json"

            def hook_state() -> str:
                seen = HI.doctor(home=world.profile, only="zaicode")
                return next(h for h in seen["hosts"] if h["id"] == "zaicode")["hook"]

            self.assertEqual(hook_state(), "current")

            # 1. artifact drift
            world.hook.write_bytes(world.hook.read_bytes() + b"\n# drift\n")
            self.assertEqual(hook_state(), "stale")

            # 2. a config naming a root that proves no generation
            G.install("zaicode", world.profile, REPO)
            data = json.loads(config.read_text(encoding="utf-8"))
            args = data["hooks"]["events"]["UserPromptSubmit"][0]["hooks"][0]["args"]
            args[args.index("--saipen-root") + 1] = str(world.base / "not-a-generation")
            config.write_text(json.dumps(data, indent=2), encoding="utf-8")
            bogus = G.install("zaicode", world.profile, REPO, check=True)
            self.assertFalse(bogus["current"], bogus)
            self.assertIn("delegated-root-stale", bogus["problems"], bogus)
            self.assertEqual(hook_state(), "stale")

            # 3. a changed field other than the root
            G.install("zaicode", world.profile, REPO)
            data = json.loads(config.read_text(encoding="utf-8"))
            data["hooks"]["events"]["UserPromptSubmit"][0]["hooks"][0]["timeoutMs"] = 5000
            config.write_text(json.dumps(data, indent=2), encoding="utf-8")
            tampered = G.install("zaicode", world.profile, REPO, check=True)
            self.assertFalse(tampered["current"], tampered)
            self.assertIn("config-entry-differs", tampered["problems"], tampered)
            self.assertEqual(hook_state(), "stale")


class DeclarationIsLoadBearingTests(unittest.TestCase):
    """The RED control: undo the two declarations and both observers go blind.

    This is what the pre-T-1935 registry looked like, measured on the same
    drifted bytes. If a future edit drops `install.hook` or `hook_installer`
    from the ZAICODE row it will look harmless in every green test above, so
    the blindness itself is pinned here.
    """

    def test_removing_the_declaration_blinds_prelaunch_and_doctor(self):
        from saipen_engine import host_integration as HI

        adapter = json.loads(json.dumps(_adapter()))
        adapter["install"].pop("hook", None)
        adapter.pop("hook_installer", None)
        with Redirected() as world:
            G.install("zaicode", world.profile, REPO)
            world.hook.write_bytes(world.hook.read_bytes() + b"\n# drift\n")
            # `hook_problems` -- the blind observer, unchanged behaviour.
            self.assertEqual(RB.hook_problems(adapter, REPO), [])
            # `doctor` -- the pre-repair outcome, on genuinely drifted bytes.
            with mock.patch.object(
                HI, "load_registry", lambda *a, **k: {"adapters": [adapter]}
            ):
                report = HI.doctor(home=world.profile, only="zaicode")
        host = next(h for h in report["hosts"] if h["id"] == "zaicode")
        self.assertEqual(
            host["hook"], "current",
            "WITHOUT the declaration doctor cannot see the drift; if this now "
            "fails, the blindness was fixed somewhere else and this control "
            "should be retired rather than forced green",
        )


if __name__ == "__main__":
    unittest.main()
