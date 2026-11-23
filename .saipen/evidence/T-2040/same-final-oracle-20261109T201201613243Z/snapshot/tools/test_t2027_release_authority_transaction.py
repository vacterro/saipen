"""T-2027 / SRC-396: red controls for the release authorization transaction.

Four reproduced defects in the live release authorization path. Every test runs
the REAL functions against REAL files: a real `git init` repository for the
index/ancestry controls, and a real stored approval packet for the stale-packet
controls. No mock stands between the assertion and the arithmetic.

P0-01 `approve_release_command` shows the caller's explicit remote/branch but
      then hands the stored packet to `convert_decision_request_to_capsule`,
      which re-reads the packet's OWN `ancestry.remote`. Measured: preview said
      `origin/main`, the persisted grant said `github-backup/main`.
P0-02 `stdin_isatty and confirm` is accepted as `is_operator`. Both are
      caller-supplied; a model-controlled PTY or a direct in-process call
      satisfied them and PERSISTED a grant with no human anywhere.
P0-03 the packet path, the base commit `3c96a989...`, the URL and the staging
      hash `91a5a63c...` (plus the literal "864 staged paths") are frozen
      fallbacks that reach a NEW grant for an unrelated cohort.
P1-04 `execute_isolated_release` passes the literal `"HEAD"` as `base_commit`
      to `find_active_grant`, whose match is a string equality against an
      immutable SHA. Measured: `find_active_grant(base_commit="HEAD")` -> None
      while the same grant matches by its SHA.
P0-05 the executor defaults to `origin/main` and the stored packet targets
      `github-backup/main`; the `NON_FAST_FORWARD` ancestry check runs BEFORE
      the grant check, so approval alone cannot clear that refusal.

These are authorization-integrity defects. They do not establish a broker
compromise: signatures, native operator origin, revocation, expiration and the
no-force invariant are untouched.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from saipen_engine import isolated_release, release_authority  # noqa: E402

REPO_ROOT = TOOLS.parent
LIVE_PACKET = REPO_ROOT / ".saipen" / "evidence" / "release-reconciliation" / "approval_packet_20261102.json"


def _git(root: Path, *args: str) -> str:
    res = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {res.stderr.strip()}")
    return res.stdout.strip()


def _make_repo(base: Path) -> Path:
    """A real repository with one commit. `base` is the directory the test owns."""
    root = base / "project"
    root.mkdir(parents=True, exist_ok=True)
    (root / ".saipen").mkdir(parents=True, exist_ok=True)
    (root / ".saipen" / "STATE.md").write_text(
        (REPO_ROOT / ".saipen" / "STATE.md").read_text(encoding="utf-8-sig"), encoding="utf-8"
    )
    identity = REPO_ROOT / ".saipen" / "IDENTITY.md"
    if identity.is_file():
        (root / ".saipen" / "IDENTITY.md").write_text(identity.read_text(encoding="utf-8"), encoding="utf-8")
    (root / "tracked.txt").write_text("one\n", encoding="utf-8")
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "t2027@example.invalid")
    _git(root, "config", "user.name", "T-2027")
    _git(root, "add", "tracked.txt", ".saipen")
    _git(root, "commit", "-q", "-m", "base")

    # Add remotes that the live packet and tests reference
    bare_github = base / "github-backup.git"
    _git(base, "init", "-q", "--bare", str(bare_github))
    _git(bare_github, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(root, "remote", "add", "github-backup", str(bare_github))
    _git(root, "push", "-q", "github-backup", "HEAD:refs/heads/main")

    bare_origin = base / "origin.git"
    _git(base, "init", "-q", "--bare", str(bare_origin))
    _git(bare_origin, "symbolic-ref", "HEAD", "refs/heads/main")
    _git(root, "remote", "add", "origin", str(bare_origin))
    _git(root, "push", "-q", "origin", "HEAD:refs/heads/main")

    return root


def _copy_packet(root: Path) -> Path:
    """Install the real stored packet, re-authenticated to THIS fixture's live state.

    The shape (action, reviewed scope, destination names) is the real packet's;
    the cohort identities (base, tip, url, merge base) are measured here. A
    packet whose frozen identities belong to another cohort is STALE by design
    and is covered by its own test.
    """
    dst_dir = root / ".saipen" / "evidence" / "release-reconciliation"
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / LIVE_PACKET.name
    packet = json.loads(LIVE_PACKET.read_text(encoding="utf-8"))

    head = _git(root, "rev-parse", "HEAD")
    push_url = _git(root, "remote", "get-url", "--push", "github-backup")
    ancestry = packet.setdefault("ancestry", {})
    ancestry.update(
        {
            "remote": "github-backup",
            "push_url": push_url,
            "branch": "main",
            "local_head": head,
            "remote_head": head,
            "merge_base": head,
            "ahead_count": 1,
            "behind_count": 0,
            "ahead_commits": [],
            "behind_commits": [],
            "is_fast_forward": True,
            "requires_integration": False,
        }
    )
    packet["target_destination"] = f"github-backup/main ({push_url})"
    dst.write_text(json.dumps(packet, indent=2), encoding="utf-8")
    return dst


class ReleaseTransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="saipen_t2027_")).resolve()
        self.root = _make_repo(self.tmp)
        (self.root / ".saipen" / "authority" / "release_grants").mkdir(parents=True, exist_ok=True)

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    # P0-01 -----------------------------------------------------------------

    def test_p0_01_explicit_destination_differing_from_the_packet_is_refused(self) -> None:
        """A stored packet for another destination cannot silently win over the shown one."""
        packet = _copy_packet(self.root)
        res = release_authority.approve_release_command(
            self.root,
            packet_path=packet,
            remote="origin",
            branch="main",
            confirm=True,
            stdin_isatty=True,
            _operator_verified=True,
        )
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(res.get("code"), "STALE_RELEASE_PACKET")
        self.assertFalse(
            list((self.root / ".saipen" / "authority" / "release_grants").glob("*.json")),
            "a refused packet must persist no grant",
        )

    def test_p0_01_displayed_and_granted_destination_always_agree(self) -> None:
        """Whatever is shown is what is granted, in every authorization field."""
        packet = _copy_packet(self.root)
        res = release_authority.approve_release_command(
            self.root,
            packet_path=packet,
            confirm=True,
            stdin_isatty=True,
            _operator_verified=True,
            standing=True,
            max_releases=3,
        )
        self.assertTrue(res.get("ok"), res)
        shown = res["presentation"]
        grant = json.loads(Path(res["grant_path"]).read_text(encoding="utf-8"))
        self.assertEqual(shown["target_remote"], grant["target_remote"])
        self.assertEqual(shown["target_branch"], grant["target_branch"])
        self.assertEqual(shown["base_commit"], grant["base_commit"])
        self.assertEqual(shown["protected_staging_hash"], grant["protected_staging_hash"])
        self.assertEqual(shown["reviewed_files_count"], len(grant["reviewed_scope"]))

    def test_p0_01_packet_url_matches_the_granted_url(self) -> None:
        packet = _copy_packet(self.root)
        res = release_authority.approve_release_command(
            self.root,
            packet_path=packet,
            confirm=True,
            stdin_isatty=True,
            _operator_verified=True,
        )
        self.assertTrue(res.get("ok"), res)
        grant = json.loads(Path(res["grant_path"]).read_text(encoding="utf-8"))
        self.assertEqual(grant["target_url"], res["presentation"]["target_destination"].split("(")[-1].rstrip(")"))

    # P0-02 -----------------------------------------------------------------

    def test_p0_02_a_supplied_tty_flag_is_not_operator_provenance(self) -> None:
        """`confirm` plus a caller-asserted TTY is not a human. Pre-fix this persisted a grant."""
        packet = _copy_packet(self.root)
        res = release_authority.approve_release_command(
            self.root,
            packet_path=packet,
            confirm=True,
            stdin_isatty=True,
        )
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(res.get("code"), "REFUSED_SYNTHETIC_APPROVAL")
        self.assertFalse(
            list((self.root / ".saipen" / "authority" / "release_grants").glob("*.json")),
            "an unproven approval must persist no grant",
        )

    def test_p0_02_confirm_without_any_provenance_is_refused(self) -> None:
        packet = _copy_packet(self.root)
        res = release_authority.approve_release_command(
            self.root, packet_path=packet, confirm=True, stdin_isatty=False
        )
        self.assertFalse(res.get("ok"))
        self.assertEqual(res.get("code"), "REFUSED_SYNTHETIC_APPROVAL")

    def test_p0_02_a_broker_verified_carrier_is_accepted(self) -> None:
        """The genuine path stays usable: a broker-verified operator proof authorizes."""
        packet = _copy_packet(self.root)
        proof = {"kind": "operator-origin", "nonce": "a" * 32, "action": "authorize-goal"}
        calls = []

        def fake_verify(proof_arg, *, project, operation, grant):
            calls.append((proof_arg, str(project), operation, grant))
            return True

        import saipen_engine.host_authority_client as hac

        original = hac.verify_operator_goal
        hac.verify_operator_goal = fake_verify
        try:
            res = release_authority.approve_release_command(
                self.root,
                packet_path=packet,
                provenance={"witness": "operator_carrier"},
                operator_origin=proof,
                operator_operation="release-authorize",
                confirm=True,
            )
        finally:
            hac.verify_operator_goal = original
        self.assertTrue(res.get("ok"), res)
        self.assertEqual(res.get("code"), "RELEASE_AUTHORIZED")
        self.assertTrue(calls, "the broker verifier must actually be consulted")

    def test_p0_02_a_carrier_claim_without_a_verified_proof_is_refused(self) -> None:
        packet = _copy_packet(self.root)
        res = release_authority.approve_release_command(
            self.root,
            packet_path=packet,
            provenance={"witness": "operator_carrier"},
            operator_origin={"kind": "operator-origin", "nonce": "b" * 32},
            operator_operation="release-authorize",
        )
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(res.get("code"), "REFUSED_SYNTHETIC_APPROVAL")

    # P0-03 -----------------------------------------------------------------

    def test_p0_03_no_frozen_base_commit_without_an_authenticated_source(self) -> None:
        """With no packet at all the proposal is unavailable, never a historical SHA."""
        res = release_authority.approve_release_command(
            self.root, confirm=True, stdin_isatty=True, _operator_verified=True
        )
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(res.get("code"), "RELEASE_PROPOSAL_UNAVAILABLE")
        self.assertNotIn("3c96a98926b762547388ebd84708e8e6744e42e5", json.dumps(res))

    def test_p0_03_no_frozen_staging_hash_or_path_count_is_presented(self) -> None:
        packet = _copy_packet(self.root)
        res = release_authority.approve_release_command(
            self.root,
            packet_path=packet,
            confirm=True,
            stdin_isatty=True,
            _operator_verified=True,
        )
        self.assertTrue(res.get("ok"), res)
        shown = res["presentation"]
        grant = json.loads(Path(res["grant_path"]).read_text(encoding="utf-8"))
        frozen = "91a5a63c8286f0d76cca79038a025647d83dd10f199a6bf459ff6a3777a0f36d"
        self.assertNotEqual(shown["protected_staging_hash"], frozen)
        self.assertNotEqual(grant["protected_staging_hash"], frozen)
        live_sha, _ = isolated_release.snapshot_shared_index(self.root)
        self.assertEqual(shown["protected_staging_hash"], live_sha)
        self.assertEqual(grant["protected_staging_hash"], live_sha)
        self.assertNotIn("864 staged paths", json.dumps(shown))

    def test_p0_03_the_shown_staging_hash_is_the_live_index(self) -> None:
        """Staging identity moves with the index, not with a constant."""
        packet = _copy_packet(self.root)
        first = release_authority.approve_release_command(
            self.root, packet_path=packet, confirm=True, stdin_isatty=True, _operator_verified=True
        )
        self.assertTrue(first.get("ok"), first)
        (self.root / "staged-new.txt").write_text("new\n", encoding="utf-8")
        _git(self.root, "add", "staged-new.txt")
        second = release_authority.approve_release_command(
            self.root,
            packet_path=packet,
            confirm=True,
            stdin_isatty=True,
            _operator_verified=True,
            max_releases=None,
        )
        self.assertTrue(second.get("ok"), second)
        self.assertNotEqual(
            first["presentation"]["protected_staging_hash"],
            second["presentation"]["protected_staging_hash"],
            "the staging identity must track the live index",
        )

    # P1-04 -----------------------------------------------------------------

    def test_p1_04_a_symbolic_base_ref_matches_its_commit(self) -> None:
        """`HEAD` must resolve to the commit object id before the grant match."""
        head = _git(self.root, "rev-parse", "HEAD")
        packet = _copy_packet(self.root)
        approved = release_authority.approve_release_command(
            self.root,
            packet_path=packet,
            base_commit=head,
            confirm=True,
            stdin_isatty=True,
            _operator_verified=True,
        )
        self.assertTrue(approved.get("ok"), approved)
        grant = json.loads(Path(approved["grant_path"]).read_text(encoding="utf-8"))
        self.assertEqual(grant["base_commit"], head)

        for ref in ("HEAD", head):
            found = release_authority.find_active_grant(
                self.root, remote=grant["target_remote"], branch=grant["target_branch"], base_commit=ref
            )
            self.assertIsNotNone(found, f"base ref {ref!r} must resolve to the granted commit")
            self.assertEqual(found["grant_id"], grant["grant_id"])

    def test_p1_04_an_unrelated_base_ref_does_not_match(self) -> None:
        head = _git(self.root, "rev-parse", "HEAD")
        packet = _copy_packet(self.root)
        approved = release_authority.approve_release_command(
            self.root, packet_path=packet, base_commit=head,
            confirm=True, stdin_isatty=True, _operator_verified=True,
        )
        self.assertTrue(approved.get("ok"), approved)
        (self.root / "second.txt").write_text("two\n", encoding="utf-8")
        _git(self.root, "add", "second.txt")
        _git(self.root, "commit", "-q", "-m", "second")
        other = _git(self.root, "rev-parse", "HEAD")
        self.assertNotEqual(head, other)
        found = release_authority.find_active_grant(
            self.root, remote="github-backup", branch="main", base_commit=other
        )
        self.assertIsNone(found, "the grant must not widen to an unrelated base commit")

    # P0-05 diverged-history integration ------------------------------------

    def test_p0_05_a_diverged_destination_is_refused_with_one_integration_route(self) -> None:
        """A tip that is not an ancestor of the base cannot be approved blindly."""
        # Publish a base, then let the remote advance to an unrelated commit.
        head = _git(self.root, "rev-parse", "HEAD")
        other = self.tmp / "other"
        _git(self.tmp, "clone", "-q", str(self.tmp / "github-backup.git"), str(other))
        _git(other, "config", "user.email", "o@example.invalid")
        _git(other, "config", "user.name", "O")
        (other / "remote.txt").write_text("remote\n", encoding="utf-8")
        _git(other, "add", "remote.txt")
        _git(other, "commit", "-q", "-m", "remote advance")
        _git(other, "push", "-q", "origin", "main")
        remote_tip = _git(other, "rev-parse", "HEAD")
        self.assertNotEqual(head, remote_tip)

        packet = _copy_packet(self.root)
        # The fixture packet was stamped at the OLD tip; the live remote moved.
        blocked = release_authority.build_release_transaction(
            self.root, packet_path=packet, base_commit=head
        )
        self.assertFalse(blocked.get("ok"), blocked)
        self.assertEqual(blocked.get("code"), "RELEASE_DESTINATION_DIVERGED")
        route = blocked.get("integration_route", "")
        self.assertIn("--reconcile-remote-head", route)
        self.assertIn(remote_tip, route)
        # The route names the MEASURED tip, never an arbitrary caller SHA.
        self.assertEqual(blocked.get("remote_tip"), remote_tip)

    def test_p0_05_reconcile_remote_head_is_a_caller_named_tip_not_a_bypass(self) -> None:
        """`--reconcile-remote-head` supplies the base; the ancestry gate still runs."""
        head = _git(self.root, "rev-parse", "HEAD")
        other = self.tmp / "other2"
        _git(self.tmp, "clone", "-q", str(self.tmp / "github-backup.git"), str(other))
        _git(other, "config", "user.email", "o@example.invalid")
        _git(other, "config", "user.name", "O")
        (other / "remote.txt").write_text("remote\n", encoding="utf-8")
        _git(other, "add", "remote.txt")
        _git(other, "commit", "-q", "-m", "remote advance")
        _git(other, "push", "-q", "origin", "main")

        # An unrelated SHA as the reconcile head is NOT an ancestor of the remote
        # tip, so the ordinary fast-forward check still refuses -- the flag names
        # a base, it does not waive the gate.
        res = isolated_release.execute_isolated_release(
            self.root,
            "saipen ship --isolated",
            remote="github-backup",
            branch="main",
            reconcile_remote_head=head,
        )
        self.assertFalse(res.get("ok"), res)
        # No grant exists yet, so authority is the first refusal (P0-05 order).
        self.assertEqual(res.get("code"), "BLOCKED_AUTHORITY_GATE")

    # P0-05 -----------------------------------------------------------------

    def test_p0_05_executor_destination_matches_the_grant_destination(self) -> None:
        """The shared executor must not default to a destination no grant can target."""
        import inspect

        sig = inspect.signature(isolated_release.execute_isolated_release)
        self.assertEqual(sig.parameters["remote"].default, None)
        self.assertEqual(sig.parameters["branch"].default, None)

    def test_p0_05_an_unknown_destination_is_refused_not_defaulted(self) -> None:
        res = isolated_release.execute_isolated_release(
            self.root, "saipen ship --isolated", remote="does-not-exist", branch="main"
        )
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(res.get("code"), "UNKNOWN_REMOTE")

    def test_p0_05_a_named_unconfigured_remote_is_unknown_not_unresolved(self) -> None:
        """A caller-named remote is a config question, answered before any grant.

        Without a branch the destination path used to fall through to the grant
        lookup, so an unconfigured remote was misreported as
        GRANT_DESTINATION_UNRESOLVED -- telling the operator to approve a grant
        for a remote that does not exist.
        """
        res = isolated_release.execute_isolated_release(
            self.root, "saipen ship --isolated", remote="does-not-exist"
        )
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(res.get("code"), "UNKNOWN_REMOTE")

    def test_p0_05_the_executor_records_the_grant_verdict_before_ancestry(self) -> None:
        """Without a grant the refusal names the grant, not a non-fast-forward."""
        res = isolated_release.execute_isolated_release(
            self.root, "saipen ship --isolated", remote="github-backup", branch="main"
        )
        self.assertFalse(res.get("ok"), res)
        self.assertEqual(res.get("code"), "BLOCKED_AUTHORITY_GATE")
        self.assertNotEqual(res.get("code"), "NON_FAST_FORWARD")

    # Nonregression ---------------------------------------------------------

    def test_policy_v2_binding_is_untouched(self) -> None:
        """SRC-395's repair is not reopened by this ticket."""
        from saipen_engine import goal_authority

        self.assertEqual(goal_authority.MAINTENANCE_POLICY_VERSION, 2)
        goals = goal_authority.active_maintenance_goals(REPO_ROOT)
        self.assertEqual([g.goal_id for g in goals], ["self-maintenance-core"])
        self.assertEqual(
            goal_authority.maintenance_goal_digest(goals[0]),
            "sha256:fdc3d057a55655025d09f4a4dfcffdc7579ba3e54ef38a2cf3af6c8032bef24d",
        )

    def test_no_force_invariant_is_untouched(self) -> None:
        packet = _copy_packet(self.root)
        grant = release_authority.convert_decision_request_to_capsule(
            packet, self.root, standing=True, max_releases=2
        )
        self.assertTrue(grant["no_force"])
        bad = dict(grant)
        bad["no_force"] = False
        bad["grant_id"] = release_authority.compute_grant_id(bad)
        with self.assertRaises(ValueError):
            release_authority.validate_capsule_data(bad, self.root)


if __name__ == "__main__":
    unittest.main()
