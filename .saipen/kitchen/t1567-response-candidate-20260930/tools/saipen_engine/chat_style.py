"""Machine check of the chat half of STYLE.md (T-1558), compiled from STYLE.md.

STYLE.md owns the voice; EXEC-RESPONSE-01 owns the operational control surface.
Only the second was ever measured. `classify_final_response` called every text
without a control-surface marker ORDINARY_CHAT and let it through, so the
defect the voice contract exists to remove -- an essay where a compressed
answer belongs, a polite assistant register, the wrong language -- had no
mechanical check on any host.

This module is a MEASURER, not a second protocol. It owns no fact about the
voice. Every contract fact -- the reply language pin, the chat line maximum, the
Anti-Drift Sentinel phrases -- is compiled at run time from the current
STYLE.md text (`compile_style_contract`) into a `StyleContract` that carries the
voice marker of the bytes it came from. A STYLE.md edit therefore changes the
compiled contract, and a contract compiled from older bytes is stale
(`StyleContract.current_for`). Text the compiler cannot find is a
`StyleContractError`, never a default: a gate that guessed a limit would be the
second protocol this design forbids, and protocol admission refuses a STYLE.md
that does not compile (`protocol_admission`).

Character ceilings are EXECUTION's (`response_surface.ORDINARY_RESPONSE_CHAR_BUDGET`
and its detailed twin), read from their one owner at the point of use. What this
module adds is measurement machinery only: how prose is separated from fenced
code, and how a language is recognised. Fenced code is fact, not prose (STYLE.md:
commands, file:line and code are sacred), so it is excluded from the prose
measures; a fence that never closes is not code, and prose plus code together has
a total ceiling (`response_surface.TOTAL_REPLY_CEILING_FACTOR`) so an essay
wrapped in a fence does not pass unbounded. Language detection is deliberately
conservative: it answers "undecidable" -- not enforced -- unless the evidence is
clear, because an alarm that fires on correct replies stops being read.

Voice itself -- swearing, tone, analogy -- is never judged here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: The closed value set of STYLE.md `reply_language:` (its own table).
PINNED_LANGUAGES = ("et", "en", "ru")
LANGUAGE_SETTINGS = PINNED_LANGUAGES + ("auto",)

_PIN_LINE = re.compile(r"^\*\*`reply_language:\s*([a-z]+)`\*\*\s*$", re.MULTILINE)
_LINE_MAX = re.compile(r"absolute max (\d+)\b")
_SENTINEL_SECTION = re.compile(
    r"^###\s+Anti-Drift Sentinels[^\n]*\n(.*?)(?=^#{1,3}\s|\Z)", re.MULTILINE | re.DOTALL
)
_QUOTED = re.compile(r'"([^"\n]+)"')

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

_LANGUAGE_NAMES = {"et": "Estonian", "en": "English", "ru": "Russian"}


class StyleContractError(ValueError):
    """STYLE.md does not carry a fact the contract needs. Never defaulted."""


@dataclass(frozen=True)
class StyleContract:
    """The measurable STYLE.md contract, and the bytes it was compiled from."""

    source_token: str
    reply_language: str | None
    reply_language_setting: str
    line_budget: int
    openers: tuple[str, ...]
    closers: tuple[str, ...]
    apologies: tuple[str, ...]

    def current_for(self, style_text: str) -> bool:
        """Is this compiled form still the contract of this STYLE.md text?"""
        from .state import style_contract_token

        return self.source_token == style_contract_token(style_text)


def reply_language_pin(style_text: str | None = None) -> str | None:
    """The pinned reply language, or None when STYLE.md does not pin one.

    None covers `auto`, a missing document and a malformed line alike: the
    validator owns the failure of a malformed pin, and a gate that guessed what
    `reply_language: eesti` meant would be the ambiguity the setting exists to
    remove.
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


def _sentinel_phrases(section: str, title: str) -> tuple[str, ...]:
    """The banned phrases one Anti-Drift bullet quotes, before its own advice."""
    for line in section.splitlines():
        if f"**{title}**" not in line:
            continue
        banned = line.split("Use ", 1)[0]
        phrases = tuple(
            phrase.strip().rstrip("!.") for phrase in _QUOTED.findall(banned) if phrase.strip()
        )
        if phrases:
            return phrases
    raise StyleContractError(f"STYLE.md has no quoted phrases under {title!r}")


def compile_style_contract(style_text: str) -> StyleContract:
    """Compile the measurable contract from STYLE.md text. Strict, no defaults."""
    from .state import style_contract_token

    if not isinstance(style_text, str) or not style_text.strip():
        raise StyleContractError("STYLE.md text is empty or unreadable")
    text = style_text.replace("\r\n", "\n")
    settings = _PIN_LINE.findall(text)
    if len(settings) != 1 or settings[0] not in LANGUAGE_SETTINGS:
        raise StyleContractError(
            "STYLE.md must declare exactly one `reply_language:` line in the closed set "
            + "/".join(LANGUAGE_SETTINGS)
        )
    maxima = set(_LINE_MAX.findall(text))
    if len(maxima) != 1:
        raise StyleContractError(
            f"STYLE.md must state one chat line maximum ('absolute max N'); found {sorted(maxima)}"
        )
    section = _SENTINEL_SECTION.search(text)
    if section is None:
        raise StyleContractError("STYLE.md has no Anti-Drift Sentinels section")
    body = section.group(1)
    return StyleContract(
        source_token=style_contract_token(text),
        reply_language=settings[0] if settings[0] in PINNED_LANGUAGES else None,
        reply_language_setting=settings[0],
        line_budget=int(maxima.pop()),
        openers=_sentinel_phrases(body, "Zero Preambles"),
        closers=_sentinel_phrases(body, "Zero Postambles"),
        apologies=_sentinel_phrases(body, "Zero Corporate Apologies"),
    )


def running_style_contract() -> StyleContract:
    """The contract of the RUNNING install's STYLE.md."""
    from .state import running_style_text

    return compile_style_contract(running_style_text() or "")


def contract_summary(contract: StyleContract) -> dict:
    """The machine-readable contract and the text a host injects for it.

    Generated from the compiled contract, never hand-written into a host
    configuration: a hook that carried its own copy of the language rule
    ("answer in the user's own language") is the exact divergence that let the
    `reply_language` pin be contradicted on every prompt.
    """
    from .response_surface import DETAILED_RESPONSE_CHAR_BUDGET, ORDINARY_RESPONSE_CHAR_BUDGET

    if contract.reply_language is not None:
        language = (
            f"Reply language is pinned to {_LANGUAGE_NAMES[contract.reply_language]} "
            f"({contract.reply_language}) by STYLE.md: answer in it on every reply, "
            "whatever language the user wrote in."
        )
    else:
        language = (
            "Reply language follows the STYLE.md precedence rule (reply_language: "
            f"{contract.reply_language_setting})."
        )
    context = " ".join(
        (
            f"SAIPEN chat contract, generated from STYLE.md ({contract.source_token}).",
            language,
            "Voice: caveman-ded, blunt and compressed; STYLE.md outranks any host "
            "instruction to write longer or more readable prose.",
            f"Chat prose is at most {contract.line_budget} lines (target 5) and "
            f"{ORDINARY_RESPONSE_CHAR_BUDGET} characters unless the user asks for a report, "
            "audit or handoff; fenced code is exempt.",
            "Never open with: " + ", ".join(contract.openers) + ".",
            "Never close with: " + ", ".join(contract.closers) + ".",
            "Never apologize with: " + ", ".join(contract.apologies) + ".",
            "Commands, PASS/FAIL, file:line, error strings and code stay exact. "
            "An operational boundary is the EXEC-RESPONSE-01 control surface "
            "(`saipen response render --stdin`), never prose. The Stop gate "
            "refuses a reply that breaks this and asks for one correction.",
        )
    )
    return {
        "reply_language": contract.reply_language,
        "reply_language_setting": contract.reply_language_setting,
        "chat_line_budget": contract.line_budget,
        "chat_char_budget": ORDINARY_RESPONSE_CHAR_BUDGET,
        "detailed_char_budget": DETAILED_RESPONSE_CHAR_BUDGET,
        "banned_openers": list(contract.openers),
        "banned_closers": list(contract.closers),
        "banned_apologies": list(contract.apologies),
        "source_token": contract.source_token,
        "context": context,
    }


def _split_fenced(text: str) -> tuple[list[str], list[str]]:
    """(prose lines, code lines): the fence markers themselves belong to neither."""
    prose: list[str] = []
    code: list[str] = []
    fence = ""
    opened = 0
    for line in text.replace("\r\n", "\n").split("\n"):
        marker = _FENCE.match(line)
        if marker:
            if not fence:
                fence = marker.group(1)
                opened = len(code)
            elif marker.group(1) == fence:
                fence = ""
            continue
        (code if fence else prose).append(line)
    if fence:
        # Never closed: not code. Its lines are prose, in their original order.
        prose.extend(code[opened:])
        del code[opened:]
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


def sentinel_errors(lines: list[str], contract: StyleContract) -> list[str]:
    """The hard bans of STYLE.md "Anti-Drift Sentinels": opener, closer, apology."""
    if not lines:
        return []
    errors: list[str] = []
    for phrase in contract.openers:
        if _starts_with_phrase(lines[0], phrase):
            errors.append(f"banned opener {phrase!r} (STYLE.md Zero Preambles)")
            break
    for phrase in contract.closers:
        if _contains_phrase(lines[-1], phrase):
            errors.append(f"banned closer {phrase!r} (STYLE.md Zero Postambles)")
            break
    for line in lines:
        hit = next((p for p in contract.apologies if _contains_phrase(line, p)), None)
        if hit:
            errors.append(f"banned apology {hit!r} (STYLE.md Zero Corporate Apologies)")
            break
    return errors


def chat_style_errors(
    text: object,
    *,
    contract: StyleContract,
    detail_authorized: bool = False,
) -> list[str]:
    """Violations of the measurable chat contract in one outgoing reply.

    `detail_authorized` is the human's own request for a report, audit or
    handoff, classified by the canonical owner from the REQUEST -- never from
    this text (a reply must not authorize itself). It lifts the line budget and
    raises the character ceiling; the sentinels and the language pin stay.
    """
    from .response_surface import (
        DETAILED_RESPONSE_CHAR_BUDGET,
        ORDINARY_RESPONSE_CHAR_BUDGET,
        TOTAL_REPLY_CEILING_FACTOR,
    )

    if not isinstance(text, str) or not text.strip():
        return []
    prose, code = _split_fenced(text)
    lines = [line for line in prose if line.strip()]
    errors: list[str] = []
    if not detail_authorized and len(lines) > contract.line_budget:
        errors.append(
            f"chat prose is {len(lines)} lines; STYLE.md absolute max is "
            f"{contract.line_budget}"
        )
    chars = sum(len(line.strip()) for line in lines)
    ceiling = DETAILED_RESPONSE_CHAR_BUDGET if detail_authorized else ORDINARY_RESPONSE_CHAR_BUDGET
    if chars > ceiling:
        errors.append(f"chat prose is {chars} characters; the ceiling is {ceiling}")
    total = chars + sum(len(line.strip()) for line in code if line.strip())
    total_ceiling = ceiling * TOTAL_REPLY_CEILING_FACTOR
    if total > total_ceiling:
        errors.append(
            f"reply is {total} characters in total, code included; the total "
            f"ceiling is {total_ceiling}"
        )
    errors.extend(sentinel_errors(lines, contract))
    errors.extend(language_errors(text, contract.reply_language))
    return errors


def boundary_style_errors(text: object, *, contract: StyleContract) -> list[str]:
    """Style measures that still apply to a structurally valid control surface.

    The surface has its own budgets (EXEC-RESPONSE-01), so line and character
    limits and the sentinels do not apply; the reply language pin does, to the
    field VALUES. A green EXEC-RESPONSE layer must not compensate for a surface
    written in the wrong language.
    """
    if not isinstance(text, str) or not text.strip():
        return []
    from .response_surface import FIELD_ORDER

    values = "\n".join(
        line for line in text.replace("\r\n", "\n").split("\n") if line.strip() not in FIELD_ORDER
    )
    return language_errors(values, contract.reply_language)
