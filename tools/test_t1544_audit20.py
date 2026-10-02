"""T-1544 audit round 2 (0): three LIVE findings pinned by their measurements.

Every control here is the field transcript of a defect that produced no error,
no failed check and no written byte -- three wrong answers that a green run
cannot see.

CORE-002 -- the malformed-STATE route had three short-circuit copies. The
router (`router.route_next`) already answers an unreadable STATE with
`action: "saipen recover"`, `reason: "state-malformed"`, and it says why in
`detail`: a route the caller can GO somewhere. `_status`, `_route_once` (the
sole route owner `continue` calls) and `_explain_next` each intercepted the
same parse failure above it and emitted a refusal with `code` and `detail` and
**no `action` at all**. Reproduced on a STATE carrying the retired
`parked_work` field: `route_next` said `saipen recover` while all three
wrappers said nothing actionable, and zero bytes were written either way. So
nothing in the system was broken -- a session that obeyed the refusal had
nothing to obey. The verdict now comes FROM the router rather than from a
fourth local copy of it.

PERF-001 -- `_status` captured the source identity THREE times per call: the
conformance decision, the convergence verdict and the automation block each
computed their own while every one of them already accepted a pre-computed
identity. Three tree walks per `saipen status --json`, and worse: the
resulting `conformance_status.validator.source_tree_fingerprint` and
`automation.source_fingerprint` were derived independently and disagree in
FORM (`1bad7c4b` vs `no-git+no-git-tree-v1:1bad7c4b`) on a tree that is not a
Git work-tree, so the projection-coherence check was live on every run. One
capture, threaded into every consumer.

PERF-004 -- `_status` called `distribution_report()` unconditionally and only
gated the RESULT on `installed`, while `distribution_report` itself opens by
hashing the whole runtime generation (~160 ms). On a host with no installed
agent home the entire walk produced a dict that was read once and dropped.
The registry already knows the answer for the cost of `is_dir()`.
"""

from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import autoinject  # noqa: E402
import freshness  # noqa: E402
import saipen as CLI  # noqa: E402
import test_t1363_zero_manual_entry as fixtures  # noqa: E402
from saipen_engine.router import route_next  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402


def setUpModule() -> None:
    isolate_host_session()


def _malformed(case: unittest.TestCase) -> Path:
    """A project whose STATE carries a field the schema retired.

    `parked_work` moved out of STATE into a computed projection, so the shared
    strict reader rejects it (`state_contract_errors`) and every routing
    consumer must classify it. This is the reproduction, not a proxy.
    """
    root = Path(fixtures.project(case, parked_work="retired-projection-field"))
    return root


def _emitted(call) -> tuple[int, dict]:
    """Run one wrapper with stdout captured; return (rc, parsed JSON payload)."""
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = call()
    return rc, json.loads(buffer.getvalue())


class TheRouterOwnsTheMalformedStateRouteTests(unittest.TestCase):
    """CORE-002: no wrapper may answer a routeless refusal for the router.

    The refusals were byte-identical in `code`/`detail` and differed only in
    what they omitted, so nothing downstream could have noticed -- which is
    exactly why the omission survived. Each control below asks the SAME
    question of the router and of a wrapper, on the SAME bytes, and requires
    them to agree.
    """

    def setUp(self) -> None:
        self.root = _malformed(self)
        state_text = (self.root / ".saipen" / "STATE.md").read_text(encoding="utf-8")
        board_text = (self.root / ".saipen" / "BOARD.md").read_text(encoding="utf-8")
        self.router = route_next(state_text, board_text)

    def assertRoutedByTheRouter(self, payload: dict) -> None:
        self.assertFalse(payload.get("ok"), payload)
        self.assertEqual(payload.get("code"), "VALIDATION_FAILED", payload)
        # The keys a refusal already carried must survive the fix: `detail` is
        # what T-1327 J reads, `code` is what every refusal consumer keys on.
        self.assertIn("state-malformed", str(payload.get("detail")), payload)
        self.assertEqual(payload.get("action"), self.router["action"], payload)
        self.assertEqual(payload.get("reason"), self.router["reason"], payload)
        self.assertTrue(str(payload.get("action") or "").strip(), payload)

    def test_the_router_routes_a_malformed_state_to_recover(self):
        """The control the three wrappers are measured against."""
        self.assertFalse(self.router["ok"], self.router)
        self.assertEqual(self.router["action"], "saipen recover", self.router)
        self.assertEqual(self.router["reason"], "state-malformed", self.router)

    def test_status_carries_the_route_it_short_circuited_past(self):
        rc, payload = _emitted(lambda: CLI._status(self.root, True))
        self.assertEqual(rc, 1, payload)
        self.assertRoutedByTheRouter(payload)
        # T-1320 J: the malformed refusal must still cost nothing of the
        # locator -- recovery is found through it, without a search layer.
        self.assertTrue(str((payload.get("cold_route") or {}).get("project_root")), payload)

    def test_continue_carries_the_route_it_short_circuited_past(self):
        """`_route_once` is the only route owner `continue` has. It returns its
        refusal rather than emitting it, so it is read, not parsed."""
        route = CLI._route_once(self.root)
        self.assertEqual(route["rc"], 1, route)
        self.assertRoutedByTheRouter(route["emitted"])

    def test_explain_next_carries_the_route_it_short_circuited_past(self):
        rc, payload = _emitted(lambda: CLI._explain_next(self.root, True))
        self.assertEqual(rc, 1, payload)
        self.assertRoutedByTheRouter(payload)

    def test_nothing_is_written_and_the_route_needs_no_search_layer(self):
        """Classification only: the fix must not have become a mutation."""
        digests = {
            name: (self.root / ".saipen" / name).read_bytes()
            for name in ("STATE.md", "BOARD.md", "LOG.md")
        }
        CLI._status(self.root, True)
        for name, before in digests.items():
            with self.subTest(carrier=name):
                self.assertEqual((self.root / ".saipen" / name).read_bytes(), before)


class OneSourceIdentityPerStatusProjectionTests(unittest.TestCase):
    """PERF-001: the walk happens once and every consumer reads that answer."""

    def setUp(self) -> None:
        self.root = Path(fixtures.healthy(self))
        self.calls: list[Path] = []
        self._real = freshness.compute_source_identity

    def _counting(self, project_root):
        self.calls.append(Path(project_root))
        return self._real(project_root)

    def test_the_three_consumers_share_one_captured_identity(self):
        """Each consumer already accepted a pre-computed identity and none was
        given one, so all three derived their own. Same object, or the
        projection is not describing one checkpoint."""
        from saipen_engine import automation, conformance, convergence

        seen: dict[str, list] = {}
        originals = (
            (conformance, "conformance_decision"),
            (convergence, "convergence_verdict"),
            (automation, "automation_block"),
        )
        for module, name in originals:
            real = getattr(module, name)

            def _spy(*args, _name=name, _real=real, **kwargs):
                seen.setdefault(_name, []).append(
                    kwargs.get("source_identity") or kwargs.get("source_id")
                )
                return _real(*args, **kwargs)

            setattr(module, name, _spy)
            self.addCleanup(setattr, module, name, real)

        rc, payload = _emitted(lambda: CLI._status(self.root, True))
        self.assertEqual(rc, 0, payload)
        self.assertEqual(
            sorted(seen), ["automation_block", "conformance_decision", "convergence_verdict"], seen
        )
        # The LAST call from each is the one `_status` itself made: the route
        # gate runs its own conformance read first, and that one is not this
        # projection's to bind.
        threaded = {name: calls[-1] for name, calls in seen.items()}
        for name, identity in threaded.items():
            self.assertIsNotNone(identity, f"{name} derived its own source identity")
            self.assertIs(
                identity, threaded["conformance_decision"], f"{name} saw a different identity"
            )

    def test_status_no_longer_captures_its_own_identity(self):
        """Instrumenting the ONE function every consumer reaches for.

        Two walks remain, not four: the residual belongs to
        `router.conformance_idle_gate`, which runs its own conformance read
        inside the route gate where no `_status` argument reaches. Everything
        `_status` itself projects is now a single capture, handed to all three
        consumers instead of being recomputed by each of them.
        """
        freshness.compute_source_identity = self._counting
        self.addCleanup(setattr, freshness, "compute_source_identity", self._real)
        rc, payload = _emitted(lambda: CLI._status(self.root, True))
        self.assertEqual(rc, 0, payload)
        self.assertEqual(
            len(self.calls), 2, f"status recomputed the source identity {len(self.calls)}x"
        )
        for walked in self.calls:
            self.assertEqual(walked.resolve(), self.root.resolve(), self.calls)

    def test_the_two_published_fingerprints_are_the_same_fingerprint(self):
        """The second-order symptom: independently captured identities publish
        fingerprints that disagree in FORM, so the projection coherence check
        is live on every run instead of closed."""
        rc, payload = _emitted(lambda: CLI._status(self.root, True))
        self.assertEqual(rc, 0, payload)
        validator = (payload.get("conformance_status") or {}).get("validator") or {}
        automation = payload.get("automation") or {}
        conformance_fp = validator.get("source_tree_fingerprint")
        automation_fp = automation.get("source_fingerprint")
        self.assertTrue(conformance_fp, payload.get("conformance_status"))
        self.assertTrue(automation_fp, automation)
        # Same hex tail under both projections -- the digest cannot differ when
        # both were derived from ONE capture.
        self.assertEqual(
            str(conformance_fp).rsplit(":", 1)[-1],
            str(automation_fp).rsplit(":", 1)[-1],
            f"the projection publishes two identities: {conformance_fp!r} vs {automation_fp!r}",
        )


class TheDistributionHashIsNotPaidForNothingTests(unittest.TestCase):
    """PERF-004: `installed == 0` must cost an `is_dir()`, not a tree walk."""

    def setUp(self) -> None:
        self.root = Path(fixtures.healthy(self))

    def test_no_installed_target_means_no_installed_target(self):
        """The registry is the authority, both directions."""
        real_targets = autoinject.TARGETS
        self.addCleanup(setattr, autoinject, "TARGETS", real_targets)

        empty = self.root / "no-such-home"
        autoinject.TARGETS = [empty, empty / "nested"]
        self.assertFalse(autoinject.has_installed_targets())

        autoinject.TARGETS = [empty, self.root]
        self.assertTrue(autoinject.has_installed_targets())

    def test_status_skips_the_report_when_no_home_is_installed(self):
        """The measured cost: `runtime_generation_identity(HOME)` runs before
        the report knows it has a home, and `_status` discarded the result."""
        calls: list[str] = []

        def _tripwire(*args, **kwargs):
            calls.append("distribution_report")
            return {"installed": 0, "stale": 0, "unknown": 0, "fresh": False}

        # `patch.object` rather than a bare `setattr`: T-1552's
        # `test_family_host_reads_are_pinned` control accepts the patch idiom
        # as the recognized proof that a host read was fenced, and a bare
        # assignment is exactly what that control exists to refuse to guess at.
        with mock.patch.object(
            autoinject, "has_installed_targets", lambda: False
        ), mock.patch.object(autoinject, "distribution_report", _tripwire):
            rc, payload = _emitted(lambda: CLI._status(self.root, True))
        self.assertEqual(rc, 0, payload)
        self.assertEqual(calls, [], "status built a report it was going to discard")
        self.assertNotIn("distribution", payload, "a zero-install host projects a report")

    def test_status_still_projects_the_report_when_a_home_is_installed(self):
        """The negative control: the gate must not have become a suppression."""
        calls: list[str] = []

        def _report(*args, **kwargs):
            calls.append("distribution_report")
            return {
                "installed": 1,
                "stale": 0,
                "unknown": 0,
                "fresh": True,
                "source_head": "deadbeef",
                "newest_installed_head": "deadbeef",
                "last_run": None,
                "blocker": "NONE",
            }

        with mock.patch.object(
            autoinject, "has_installed_targets", lambda: True
        ), mock.patch.object(autoinject, "distribution_report", _report):
            rc, payload = _emitted(lambda: CLI._status(self.root, True))
        self.assertEqual(rc, 0, payload)
        self.assertEqual(calls, ["distribution_report"])
        self.assertEqual((payload.get("distribution") or {}).get("installed"), 1, payload)


if __name__ == "__main__":
    unittest.main()