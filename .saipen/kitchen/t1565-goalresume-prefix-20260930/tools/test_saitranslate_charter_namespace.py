"""Regression tests for the saitranslate charter/engine namespace contract.

T-1396 adopted the saitranslate charter revision that declares the runtime
namespace the engine already special-cases. These tests pin the invariant in
both directions so neither side can silently drift back:

  - the shipped source charter's declared write_scope IS the namespace the
    engine's resolvers return for the role (producer_namespace,
    crew._role_paths_for, the CrewRole registry OUTBOX);
  - the generic `.saipen/extensions/subs/saitranslate/` namespace that the
    pre-adoption charter declared is NOT any engine-visible runtime surface,
    so a mis-spawned copy there can never become a second live identity;
  - the charter's declared role_revision is the canonical digest of its own
    bytes, and the project-local projection agrees with the source charter
    so `saipen sub sync` has no drift to hide.

Run standalone:
    python tools/test_saitranslate_charter_namespace.py

Exit code 0 when every test passes; 1 on failure.
"""

from __future__ import annotations

import re
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in __import__("sys").path:
    __import__("sys").path.insert(0, str(TOOLS))

from saipen_engine import crew as C  # noqa: E402
from saipen_engine import producer as P  # noqa: E402
from saipen_engine.subs import ROLE_REGISTRY, SUBS_REL  # noqa: E402
from freshness import (  # noqa: E402
    SHORT_DIGEST_MARKER_HEX,
    compute_role_revision,
    digest_marker_matches,
    normalize_version_strings,
    source_content_digest,
)

REPO_ROOT = TOOLS.parent
SOURCE_CHARTER = REPO_ROOT / "extensions" / "subs" / "saitranslate.md"
PROJECTED_CHARTER = REPO_ROOT / SUBS_REL / "saitranslate.md"

SPECIAL_RUNTIME = ".saipen/saitranslate"
GENERIC_RUNTIME = f"{SUBS_REL}/saitranslate"


def _charter_text() -> str:
    raw = SOURCE_CHARTER.read_bytes()
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n").decode("utf-8")


def _charter_field(name: str) -> str:
    """One scalar field from the charter's ```yaml block, engine idiom."""
    text = _charter_text()
    block = re.search(r"(?ms)^```yaml\n(.*?)^```\s*$", text)
    if block is None:
        raise AssertionError("saitranslate charter has no ```yaml block")
    values = re.findall(rf"(?m)^{name}:\s*(.+?)\s*$", block.group(1))
    if len(values) != 1:
        raise AssertionError(f"charter must declare exactly one {name}; found {len(values)}")
    return values[0].strip().strip('"')


class SaitranslateCharterNamespaceTests(unittest.TestCase):
    def test_adopted_write_scope_is_the_engine_namespace(self) -> None:
        """GREEN: charter write_scope == every engine resolver for the role."""
        declared = _charter_field("write_scope").rstrip("/")
        self.assertEqual(declared, SPECIAL_RUNTIME)

        with tempfile.TemporaryDirectory(prefix="sait-charter-ns-") as tmp:
            root = Path(tmp)
            namespace = P.producer_namespace(root, "saitranslate")
            self.assertEqual(namespace, root / ".saipen" / "saitranslate")
            self.assertEqual(
                namespace.relative_to(root).as_posix(), declared
            )  # producer Namespace == charter write_scope

            paths = C._role_paths_for(root, "saitranslate")
            self.assertEqual(
                paths,
                (
                    f"{SPECIAL_RUNTIME}/STATE.md",
                    f"{SPECIAL_RUNTIME}/BOARD.md",
                    f"{SPECIAL_RUNTIME}/LOG.md",
                    f"{SPECIAL_RUNTIME}/kitchen/OUTBOX.md",
                    f"{SUBS_REL}/saitranslate.md",
                ),
            )

    def test_generic_namespace_is_not_an_engine_runtime_surface(self) -> None:
        """RED stays red: the pre-adoption generic namespace contradicts every
        engine resolver, so a copy living there is invisible to crew/collect
        and can never become a second live saitranslate identity."""
        with tempfile.TemporaryDirectory(prefix="sait-charter-red-") as tmp:
            root = Path(tmp)
            self.assertNotEqual(
                P.producer_namespace(root, "saitranslate"), root / GENERIC_RUNTIME
            )
            paths = C._role_paths_for(root, "saitranslate")
            for path in paths:
                self.assertFalse(path.startswith(f"{GENERIC_RUNTIME}/"))
            # The charter file itself stays under extensions/subs/ by design:
            # charter location != runtime namespace.
            self.assertIn(f"{SUBS_REL}/saitranslate.md", paths)

        role = ROLE_REGISTRY["saitranslate"]
        self.assertEqual(role.outbox_path, f"{SPECIAL_RUNTIME}/kitchen/OUTBOX.md")
        self.assertNotEqual(role.outbox_path, f"{GENERIC_RUNTIME}/kitchen/OUTBOX.md")

    def test_declared_role_revision_is_the_canonical_digest(self) -> None:
        declared = _charter_field("role_revision")
        computed = compute_role_revision(SOURCE_CHARTER)
        self.assertEqual(declared, computed)

    def test_projected_charter_agrees_with_source(self) -> None:
        """The project-local projection is the sub-sync image of the source:
        equal normalized bytes and an equal declared revision, so sync has no
        charter drift to hide."""
        if not PROJECTED_CHARTER.is_file():
            self.skipTest("project-local charter projection not present")
        source_raw = SOURCE_CHARTER.read_bytes()
        projected_raw = PROJECTED_CHARTER.read_bytes()
        self.assertEqual(
            projected_raw.replace(b"\r\n", b"\n"), source_raw.replace(b"\r\n", b"\n")
        )
        self.assertEqual(
            compute_role_revision(PROJECTED_CHARTER), compute_role_revision(SOURCE_CHARTER)
        )



class TranslationDigestMarkerWidthTest(unittest.TestCase):
    """T-125: the marker width the contract documents must actually verify.

    ``phases/translate.md`` mandates a ``<16 hex>`` ``source-digest`` marker
    while the digest the validator computes is a full 64-hex sha256. Before
    this the two were compared for exact equality, so a producer that
    followed the documented contract was reported stale forever and the
    ``translation-stale`` WARN could never be cleared. Both documented widths
    pass; every other width, and every wrong digest, is still stale, so the
    gate did not become a gate that cannot fail.
    """

    WANT = "877128c30331e9502a2b2cde921db503e98f9e63ee38fb9a9acee408eacdbd0b"

    def test_full_width_marker_matches(self):
        self.assertIs(digest_marker_matches(self.WANT, self.WANT), True)

    def test_documented_short_marker_matches(self):
        self.assertIs(
            digest_marker_matches(self.WANT[:SHORT_DIGEST_MARKER_HEX], self.WANT), True
        )

    def test_wrong_digest_is_stale_at_either_width(self):
        self.assertIs(digest_marker_matches("deadbeef" + self.WANT[8:], self.WANT), False)
        self.assertIs(digest_marker_matches("deadbeef" + self.WANT[8:24], self.WANT), False)

    def test_only_the_two_documented_widths_pass(self):
        for width in (1, 4, 8, 15, 17, 32, 63):
            with self.subTest(width=width):
                self.assertIs(
                    digest_marker_matches(self.WANT[:width], self.WANT),
                    width == SHORT_DIGEST_MARKER_HEX,
                )

    def test_empty_and_non_string_markers_are_stale(self):
        self.assertIs(digest_marker_matches("", self.WANT), False)
        self.assertIs(digest_marker_matches(None, self.WANT), False)
        self.assertIs(digest_marker_matches(self.WANT, None), False)



class VersionNormalisationTest(unittest.TestCase):
    """T-127: a release-badge bump must not move the source digest.

    The recipe normalised three numeric components only, so a pre-release
    suffix survived: `0.0.2a3` became `VERSIONa3` and `0.0.2b1` became
    `VERSIONb1`, which moved the digest and faked a `translation-stale`
    warning on exactly the badge bump the gate's own comment claims can never
    cause it. The suffix is now part of the version token.
    """

    def test_numeric_bump_does_not_move_the_digest(self):
        self.assertEqual(
            source_content_digest("v1.2.3"), source_content_digest("v4.5.6")
        )

    def test_prerelease_suffix_bump_does_not_move_the_digest(self):
        """The defect itself: a3 -> b1 must be invisible to the digest."""
        self.assertEqual(
            source_content_digest("v0.0.2a3"), source_content_digest("v0.0.2b1")
        )

    def test_every_documented_token_shape_is_normalised_whole(self):
        for token in ("1.2.3", "0.0.2a3", "0.0.2b1", "10.20.30", "2.0.0rc2"):
            with self.subTest(token=token):
                self.assertEqual(normalize_version_strings(token), "VERSION")

    def test_a_version_inside_a_filename_does_not_swallow_the_filename(self):
        """A greedy tail would hide a real change behind a version prefix."""
        self.assertEqual(
            normalize_version_strings('pip install "saimail-0.0.2a3-py3-none-any.whl"'),
            'pip install "saimail-VERSION-py3-none-any.whl"',
        )
        self.assertNotEqual(
            source_content_digest("saimail-0.0.2a3-cp311.whl"),
            source_content_digest("saimail-0.0.2a3-cp312.whl"),
        )

    def test_prose_around_a_token_is_untouched(self):
        self.assertEqual(
            normalize_version_strings("ship 1.2.3 today, see NOTES.md"),
            "ship VERSION today, see NOTES.md",
        )

    def test_a_bare_digest_is_not_a_version_token(self):
        """A 40-hex commit sha has no dots and must never be normalised."""
        sha = "3fa8f2295f564a6a75733905388ddee55b2f73b8"
        self.assertEqual(normalize_version_strings(sha), sha)

    def test_digest_changes_when_prose_moves(self):
        self.assertNotEqual(
            source_content_digest("v1.2.3 alpha"), source_content_digest("v1.2.3 beta")
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
