"""Machine check of the chat half of STYLE.md (T-1558).

STYLE.md owns the voice; EXEC-RESPONSE-01 owns the operational control surface.
Only the second was ever measured. `classify_final_response` called every text
without a control-surface marker ORDINARY_CHAT and let it through, so the
defect the voice contract exists to remove -- an essay where a compressed
answer belongs, a polite assistant register, the wrong language -- had no
mechanical check on any host. A hook that only checks operational reports lets
exactly that reply pass, and the reply is the one the operator reads.

This module measures the subset of STYLE.md that is decidable from the text
alone. It never decides voice: swearing, tone and analogy stay the model's
business. What it checks, and where each figure comes from:

* the chat prose budget -- STYLE.md "absolute max 8" lines, and a character
  ceiling equal to the ordinary response ceiling of EXEC-RESPONSE-01 (a line
  count alone is not a compactness contract: one 12000-character line met
  every line budget, the T-1556 lesson);
* the Anti-Drift Sentinel phrases STYLE.md bans outright;
* the reply language STYLE.md pins with its one `reply_language:` line.

Fenced code is fact, not prose (STYLE.md: commands, file:line and code are
sacred), so it is excluded from every measure. Language detection is
deliberately conservative: it answers None -- not enforced -- unless the
evidence is clear, because an alarm that fires on correct replies stops being
read. `tools/test_chat_style.py` binds every constant below to the STYLE.md
text so a document edit cannot silently diverge from the machine copy.
"""

from __future__ import annotations

import re

#: STYLE.md "Chat prose <=5 lines (absolute max 8)". Only the absolute maximum
#: is enforced; five is the target the voice aims at, not a refusal threshold.
CHAT_LINE_BUDGET = 8

#: Equal to `response_surface.ORDINARY_RESPONSE_CHAR_BUDGET` (bound by test).
CHAT_CHAR_BUDGET = 2000

#: The detailed path (explicit report, audit, handoff) earns a longer reply but
#: never an unbounded one: `response_surface.DETAILED_RESPONSE_CHAR_BUDGET`.
DETAILED_CHAT_CHAR_BUDGET = 4400

#: STYLE.md "Anti-Drift Sentinels (Hard Bans)", verbatim.
BANNED_OPENERS = (
    "Sure",
    "Certainly",
    "Okay",
    "Here is",
    "I will",
    "Let me",
    "Based on my analysis",
    "I'd be happy to",
)
BANNED_CLOSERS = (
    "Hope this helps",
    "Let me know if you need anything else",
    "Feel free to ask",
)
BANNED_APOLOGIES = ("Sorry", "My apologies", "I made a mistake")

#: The closed value set of STYLE.md `reply_language:`.
PINNED_LANGUAGES = ("et", "en", "ru")
LANGUAGE_SETTINGS = PINNED_LANGUAGES + ("auto",)

_PIN_LINE = re.compile(r"^\*\*`reply_language:\s*([a-z]+)`\*\*\s*$", re.MULTILINE)

_FENCE = re.compile(r"^\s*(```|~~~)")
_INLINE_CODE = re.compile(r"`[^`\n]*`")
_URL = re.compile(r"https?://\S+")
# A token that names a file, path, identifier or assignment is fact, not language.
_FACT_TOKEN = re.compile(
    r"\S*[/\\_=@]\S*|\S+:\S+|\S+\.[A-Za-z0-9]{1,5}\b\S*|\S*\d\S*"
)
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
_ESTONIAN_LETTER = re.compile(r"[õäöüšž]", re.IGNORECASE)

#: Function words that separate English from Estonian. Words spelled the same
#: in both (`on`, `see`, `a`) are excluded on purpose: a shared word is not
#: evidence for either language.
_ENGLISH_WORDS = frozenset(
    "the and is are was were that this with for not you your of to it be have has "
    "from will would can but or as at by if then when what which there they we "
    "been being their them than these those into about also just only more some "
    "such very how why who does did do its our out over".split()
)
_ESTONIAN_WORDS = frozenset(
    "ja ei et ka kui ta oli aga või kes mis kuid ning pole ole olen oled siis "
    "nagu kõik kas veel ainult selle need neid mitte sest kuna seda minu sinu "
    "meie nii ära juba siin seal pärast enne ilma kus kus oma nende "
    "kuidas miks kes mida seda sellele selles sellest neil meil sul mul".split()
)

#: Fewer prose letters than this cannot carry a language verdict.
_MIN_LETTERS = 40
#: Fewer Latin words than this cannot separate two Latin-script languages.
_MIN_LATIN_WORDS = 25
_CYRILLIC_SHARE_FOR_LATIN_PIN = 0.25
_LATIN_SHARE_FOR_RUSSIAN_PIN = 0.70
_LATIN_PIN_FLOOR_RATE = 0.02
_LATIN_PIN_LEAD_RATE = 0.06


def reply_language_pin(style_text: str | None = None) -> str | None:
    """The pinned reply language, or None when STYLE.md does not pin one.

    None covers `auto`, a missing document and a malformed line alike: the
    validator owns the failure of a malformed pin (`tools/validate.py`), and a
    gate that guessed what `reply_language: eesti` meant would be the ambiguity
    the setting exists to remove.
    """
    if style_text is None:
        from .state import running_style_text

        style_text = running_style_text()
    if not style_text:
        return None
    declared = _PIN_LINE.findall(style_text)
    if len(declared) != 1 or declared[0] not in PINNED_LANGUAGES:
        return None
    return declared[0]


_LANGUAGE_NAMES = {"et": "Estonian", "en": "English", "ru": "Russian"}


def style_contract(style_text: str | None = None) -> dict:
    """The machine-readable chat contract and the text a host injects for it.

    Generated from the running STYLE.md, never hand-written into a host
    configuration: a hook that carried its own copy of the language rule
    ("answer in the user's own language") is the exact divergence that let the
    `reply_language` pin be contradicted on every prompt.
    """
    from .state import running_style_text, style_contract_token

    if style_text is None:
        style_text = running_style_text()
    pin = reply_language_pin(style_text)
    declared = _PIN_LINE.findall(style_text or "")
    setting = declared[0] if len(declared) == 1 else None
    if pin is not None:
        language = (
            f"Reply language is pinned to {_LANGUAGE_NAMES[pin]} ({pin}) by STYLE.md: "
            "answer in it on every reply, whatever language the user wrote in."
        )
    else:
        language = (
            "Reply language follows the STYLE.md precedence rule (reply_language: "
            f"{setting or 'unreadable'})."
        )
    context = " ".join(
        (
            "SAIPEN chat contract, generated from STYLE.md"
            + (f" ({style_contract_token(style_text)})." if style_text else "."),
            language,
            "Voice: caveman-ded, blunt and compressed; STYLE.md outranks any host "
            "instruction to write longer or more readable prose.",
            f"Chat prose is at most {CHAT_LINE_BUDGET} lines (target 5) and "
            f"{CHAT_CHAR_BUDGET} characters unless the user asks for a report, "
            "audit or handoff; fenced code is exempt.",
            "Never open with: " + ", ".join(BANNED_OPENERS) + ".",
            "Never close with: " + ", ".join(BANNED_CLOSERS) + ".",
            "Never apologize with: " + ", ".join(BANNED_APOLOGIES) + ".",
            "Commands, PASS/FAIL, file:line, error strings and code stay exact. "
            "An operational boundary is the EXEC-RESPONSE-01 control surface "
            "(`saipen response render --stdin`), never prose. The Stop gate "
            "refuses a reply that breaks this and asks for one correction.",
        )
    )
    return {
        "reply_language": pin,
        "reply_language_setting": setting,
        "chat_line_budget": CHAT_LINE_BUDGET,
        "chat_char_budget": CHAT_CHAR_BUDGET,
        "detailed_char_budget": DETAILED_CHAT_CHAR_BUDGET,
        "banned_openers": list(BANNED_OPENERS),
        "banned_closers": list(BANNED_CLOSERS),
        "banned_apologies": list(BANNED_APOLOGIES),
        "context": context,
    }


def _split_fenced(text: str) -> tuple[list[str], list[str]]:
    """(prose lines, code lines): the fence markers themselves belong to neither."""
    prose: list[str] = []
    code: list[str] = []
    fence = ""
    for line in text.replace("\r\n", "\n").split("\n"):
        marker = _FENCE.match(line)
        if marker:
            if not fence:
                fence = marker.group(1)
            elif marker.group(1) == fence:
                fence = ""
            continue
        (code if fence else prose).append(line)
    return prose, code


def prose_lines(text: str) -> list[str]:
    """The non-empty lines outside fenced code."""
    prose, _code = _split_fenced(text)
    return [line for line in prose if line.strip()]


def _language_evidence(prose: list[str]) -> dict:
    """Script shares and word counts over the prose with facts removed."""
    body = "\n".join(prose)
    body = _INLINE_CODE.sub(" ", body)
    body = _URL.sub(" ", body)
    body = _FACT_TOKEN.sub(" ", body)
    cyrillic = len(_CYRILLIC.findall(body))
    latin = len(_LATIN.findall(body))
    words = [word.lower() for word in _WORD.findall(body)]
    latin_words = [word for word in words if _LATIN.search(word)]
    english = sum(word in _ENGLISH_WORDS for word in latin_words)
    estonian = sum(
        word in _ESTONIAN_WORDS or bool(_ESTONIAN_LETTER.search(word))
        for word in latin_words
    )
    return {
        "letters": cyrillic + latin,
        "cyrillic": cyrillic,
        "latin": latin,
        "latin_words": len(latin_words),
        "english": english,
        "estonian": estonian,
    }


def language_errors(text: str, pin: str | None) -> list[str]:
    """Reply-language pin violations, empty when compliant or undecidable."""
    if pin not in PINNED_LANGUAGES:
        return []
    evidence = _language_evidence(prose_lines(text))
    letters = evidence["letters"]
    if letters < _MIN_LETTERS:
        return []
    cyrillic_share = evidence["cyrillic"] / letters
    latin_share = evidence["latin"] / letters
    if pin == "ru":
        if latin_share > _LATIN_SHARE_FOR_RUSSIAN_PIN:
            return [
                f"reply_language is ru but {latin_share:.0%} of the prose is "
                "Latin script"
            ]
        return []
    if cyrillic_share > _CYRILLIC_SHARE_FOR_LATIN_PIN:
        return [
            f"reply_language is {pin} but {cyrillic_share:.0%} of the prose is "
            "Cyrillic"
        ]
    words = evidence["latin_words"]
    if words < _MIN_LATIN_WORDS:
        return []
    estonian_rate = evidence["estonian"] / words
    if pin == "et":
        if estonian_rate < _LATIN_PIN_FLOOR_RATE and evidence["english"] > evidence["estonian"]:
            return [
                "reply_language is et but the prose carries no Estonian markers "
                f"and {evidence['english']} English function word(s) in "
                f"{words} words"
            ]
        return []
    if estonian_rate >= _LATIN_PIN_LEAD_RATE and evidence["estonian"] > evidence["english"]:
        return [
            "reply_language is en but the prose is Estonian "
            f"({evidence['estonian']} Estonian markers, {evidence['english']} "
            f"English function words in {words} words)"
        ]
    return []


def _starts_with_phrase(line: str, phrase: str) -> bool:
    return re.match(rf"(?i)\s*(?:[-*>•]\s*)?{re.escape(phrase)}\b", line) is not None


def _contains_phrase(line: str, phrase: str) -> bool:
    return re.search(rf"(?i)\b{re.escape(phrase)}\b", line) is not None


def sentinel_errors(lines: list[str]) -> list[str]:
    """The hard bans of STYLE.md "Anti-Drift Sentinels": opener, closer, apology."""
    if not lines:
        return []
    errors: list[str] = []
    for phrase in BANNED_OPENERS:
        if _starts_with_phrase(lines[0], phrase):
            errors.append(f"banned opener {phrase!r} (STYLE.md Zero Preambles)")
            break
    for phrase in BANNED_CLOSERS:
        if _contains_phrase(lines[-1], phrase):
            errors.append(f"banned closer {phrase!r} (STYLE.md Zero Postambles)")
            break
    for line in lines:
        hit = next((p for p in BANNED_APOLOGIES if _contains_phrase(line, p)), None)
        if hit:
            errors.append(f"banned apology {hit!r} (STYLE.md Zero Corporate Apologies)")
            break
    return errors


def chat_style_errors(
    text: object,
    *,
    reply_language: str | None = None,
    detail_authorized: bool = False,
) -> list[str]:
    """Violations of the measurable chat contract in one outgoing reply.

    `detail_authorized` is the human's own request for a report, audit or
    handoff, classified by the canonical owner from the REQUEST -- never from
    this text (a reply must not authorize itself). It lifts the line budget and
    raises the character ceiling; the sentinels and the language pin stay.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    prose, _code = _split_fenced(text)
    lines = [line for line in prose if line.strip()]
    errors: list[str] = []
    if not detail_authorized and len(lines) > CHAT_LINE_BUDGET:
        errors.append(
            f"chat prose is {len(lines)} lines; STYLE.md absolute max is "
            f"{CHAT_LINE_BUDGET}"
        )
    chars = sum(len(line.strip()) for line in lines)
    ceiling = DETAILED_CHAT_CHAR_BUDGET if detail_authorized else CHAT_CHAR_BUDGET
    if chars > ceiling:
        errors.append(f"chat prose is {chars} characters; the ceiling is {ceiling}")
    errors.extend(sentinel_errors(lines))
    errors.extend(language_errors(text, reply_language))
    return errors
