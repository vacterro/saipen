"""T-1608: the documented `saipen collect <producer>` route must actually route.

CMD-ROUTING-01 publishes `saipen collect <producer>` as a canonical command
(COMMANDS.md, PROTOCOL.md's targeted complete-package path, REGISTRY.json's
`qqq`/`eee` expansions, and both producer charter trigger lines). The engine
implemented it and the shortcuts dispatched to it, but the spelled-out verb
itself fell through to `unknown command: collect` -- so the one route the
documentation actually shows a reader was a dead end, and every package sat at
`status: ready` with no working integrate command.

These are public-CLI subprocess regressions: the defect was public (an agent
following the docs typed the documented command), so the tests drive the real
`tools/saipen.py` and assert the public JSON contract rather than the engine.

T-1622: the producer-verdict tests run against an isolated explicit fixture
(a throwaway project with its own stale saiwiki package) instead of the
live checkout. The live tree's producer state moves legitimately -- a `qq`
refresh makes it READY, a source edit moves the fingerprint -- and the
family runs six shards in parallel sandboxes, so asserting NOT_READY
against live state made the verdict scheduler-dependent (family FAIL
`SOURCE_IDENTITY_UNKNOWN` while standalone passed). The fixture keeps the
public-CLI subprocess contract and the NOT_READY + qq assertions intact.

Run standalone:
    python tools/test_t1608_collect_verb_route.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
SAIPEN_PY = TOOLS / "saipen.py"
SCENARIO = ROOT / "tests/scenarios/done-wait-deadlock-goal-mode"

if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))


def _make_stale_saiwiki_fixture(testcase: unittest.TestCase) -> Path:
    """An isolated project whose saiwiki package is deterministically stale.

    Built from the tracked scenario fixture plus one stale READY package
    (its recorded head can never match the fixture's live head), so
    `collect saiwiki --dry-run` honestly answers NOT_READY routing to `qq`
    no matter what the live checkout's producer state does -- a concurrent
    source edit, a `qq` refresh that made live READY, or a sandbox copy
    racing a checkpoint. Setup uses the engine API; every assertion below
    still drives the real public CLI subprocess.
    """
    from freshness import compute_source_identity
    from saipen_engine import producer as P
    from saipen_engine import state as S

    temporary = tempfile.TemporaryDirectory(prefix="saipen-t1608-fixture-")
    testcase.addCleanup(temporary.cleanup)
    root = Path(temporary.name) / "project"
    shutil.copytree(SCENARIO, root)
    state_path = root / ".saipen/STATE.md"
    state_path.write_text(
        S.patch_state(
            state_path.read_text(encoding="utf-8"),
            {"saipen_home": str(ROOT.resolve())},
        ),
        encoding="utf-8",
        newline="\n",
    )
    (root / "source.txt").write_text("producer input\n", encoding="utf-8")
    identity = compute_source_identity(root)
    namespace = P.producer_namespace(root, "saiwiki")
    epoch = P.ProducerEpoch.claim(namespace)
    package = P.build_package(
        producer="saiwiki",
        role_revision="role-current",
        base_source_head=identity.source_head + "-stale",
        base_source_tree_fingerprint=identity.source_tree_fingerprint,
        base_discovery_model=identity.discovery_model,
        scope="t1608 isolated stale handoff",
        read_set=P.read_set_from(root, ["source.txt"]),
        write_set={},
        epoch=epoch,
    )
    generation = P.StagingGeneration(namespace, "saiwiki").begin()
    generation.set_package(package)
    published = generation.publish()
    if not published.get("ok"):
        raise AssertionError(f"fixture package did not publish: {published}")
    return root


def _run(*argv: str, cwd: Path | None = None, root: Path | None = None) -> tuple[int, str, str]:
    env = dict(os.environ, PYTHONPATH=str(TOOLS))
    if root is not None:
        proc = subprocess.run(
            [sys.executable, "-B", str(SAIPEN_PY), "--project-root", str(root), *argv],
            capture_output=True,
            text=True,
            cwd=str(cwd or root),
            env=env,
            timeout=600,
        )
        return proc.returncode, proc.stdout, proc.stderr
    proc = subprocess.run(
        [sys.executable, "-B", str(SAIPEN_PY), *argv],
        capture_output=True,
        text=True,
        cwd=str(cwd or ROOT),
        env=env,
        timeout=600,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _json_or_text(out: str, err: str) -> str:
    """The CLI answers a refusal as REFUSE [...] on stderr and a plan as JSON on
    stdout. Normalise both into one searchable blob so a test asserts on the
    refusal text rather than on which stream carried it."""
    return out + err


class CollectVerbRouteTests(unittest.TestCase):
    def test_verb_is_recognised_not_unknown(self):
        """The regression itself: the documented verb must not fall through."""
        _, out, err = _run("collect", "--help")
        blob = _json_or_text(out, err)
        self.assertNotIn("unknown command", blob.lower())

    def test_verb_is_published_in_usage(self):
        _, out, err = _run("--help")
        self.assertIn("collect <producer>", _json_or_text(out, err))

    def test_known_producer_routes_to_engine(self):
        """A real producer reaches the targeted flow. The fixture's package is
        stale, so the honest engine answer is NOT_READY routing to `qq` -- the
        point is that it is a producer verdict, not an unknown command."""
        root = _make_stale_saiwiki_fixture(self)
        rc, out, err = _run("collect", "saiwiki", "--dry-run", root=root)
        del rc  # the verdict, not the status, is what this asserts
        blob = _json_or_text(out, err)
        self.assertNotIn("unknown command", blob.lower())
        self.assertIn("NOT_READY", blob)
        self.assertIn("qq", blob)

    def test_non_producer_role_is_refused_by_role(self):
        """saihunt is a read-only sub, not a producer. The documented verb takes
        exactly one PRODUCER, so it must refuse with the role, which is the
        refusal that distinguishes this command from `saipen sub collect`."""
        _, out, err = _run("collect", "saihunt", "--dry-run")
        blob = _json_or_text(out, err)
        self.assertIn("INVALID_ROLE", blob)
        self.assertIn("saihunt", blob)

    def test_surplus_arguments_refused(self):
        """One producer, exactly. A second name is a usage error, not a silent
        pick of one of them."""
        rc, out, err = _run("collect", "saiwiki", "saitranslate", "--dry-run")
        blob = _json_or_text(out, err)
        self.assertIn("VALIDATION_FAILED", blob)
        self.assertEqual(rc, 2)

    def test_does_not_shadow_sub_collect_namespace(self):
        """`saipen sub collect <role>` keeps its own backlog-oriented semantics.
        Adding the spelled-out verb must not repoint the subcommand at the
        producer path, which would silently change what an existing script does."""
        _, out, err = _run("sub", "collect", "saiwiki", "--dry-run")
        blob = _json_or_text(out, err)
        self.assertNotIn("unknown command", blob.lower())
        # saiwiki is owned by producer-specific SC-9, so the sub route refuses
        # with its policy code -- not with the producer path's NOT_READY.
        self.assertIn("EXPLICIT_POLICY", blob)


class SpelledOutVerbMatchesShortcutTests(unittest.TestCase):
    def test_verb_and_shortcut_agree(self):
        """The whole point of the repair: the documented string and the working
        shortcut are the same operation, so they must reach the same verdict.
        If these ever diverge again, one of the two published routes is a lie."""
        root = _make_stale_saiwiki_fixture(self)
        _, direct_out, direct_err = _run("collect", "saiwiki", "--dry-run", root=root)
        _, short_out, short_err = _run("qqq", "--dry-run", root=root)

        def verdict(out: str, err: str) -> tuple[str, str]:
            blob = _json_or_text(out, err)
            code = ""
            for raw in blob.splitlines():
                candidate = raw.strip().strip(",")
                if candidate.startswith("code:"):
                    code = candidate.split(":", 1)[1].strip().strip('"')
                    break
            return code, blob

        direct_code, _ = verdict(direct_out, direct_err)
        shortcut_code, _ = verdict(short_out, short_err)
        self.assertEqual(direct_code, shortcut_code)
        self.assertNotEqual(direct_code, "", "both routes must emit a code")
        self.assertNotIn("unknown command", direct_code.lower())


if __name__ == "__main__":
    unittest.main()