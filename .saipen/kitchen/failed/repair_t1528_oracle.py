"""One-shot repair of the T-1528 abort oracle body (backspace-byte damage).

An earlier in-place rewrite wrote literal 0x08 bytes where regex word
boundaries belong. This replaces the whole predicate between its `def` and the
next `def` with the intended sentence-scoped implementation.
"""

from pathlib import Path

TARGET = Path("tools/run_scenarios.py")

NEW_BODY = '''        verb = r"\\b(?:preserv\\w*|retain\\w*|keep\\w*|remain\\w*|stay\\w*)\\b"
        where = (
            r"(?:\\b(?:original|same|existing|current)\\s+(?:paths?|locations?|files?)\\b"
            r"|\\bwhere\\s+(?:they|drafts?)\\s+(?:were|are)\\s+"
            r"(?:written|created|saved|kept)\\b)"
        )
        for sentence in re.split(r"(?<=[.;])\\s+", re.sub(r"\\s+", " ", clause)):
            if (
                re.search(r"\\bdrafts?\\b", sentence, re.IGNORECASE)
                and re.search(verb, sentence, re.IGNORECASE)
                and re.search(where, sentence, re.IGNORECASE)
            ):
                return True
        return False

    '''

src = TARGET.read_text(encoding="utf-8")
start = src.index("    def _abort_contract_preserves_draft_locations")
end = src.index("    def _abort_contract_rewrite")

# Keep the def, the section lookup, and the `.discarded` guard; drop
# everything from the explanatory comment onward (that is the damaged part).
region = src[start:end]
comment_at = region.index("        # The DRAFTS, a preservation verb")
prefix = src[:start] + region[:comment_at]

TARGET.write_text(prefix + NEW_BODY + src[end:], encoding="utf-8")
text = TARGET.read_text(encoding="utf-8")
print("oracle body repaired; 0x08 bytes remaining:", "\x08" in text)
