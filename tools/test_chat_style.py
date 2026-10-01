"""T-1558: the chat half of STYLE.md is measured, on every host that classifies.

The failure this closes: a reply with no control-surface marker was
ORDINARY_CHAT and passed unmeasured, so an essay where a compressed answer
belongs, a banned assistant opener and the wrong pinned language all reached
the operator through a host whose operational gate was green. These controls
hold four things:

* the machine constants equal the STYLE.md text they claim to copy;
* each measurable rule refuses its own violation and accepts its own compliance
  (a control that cannot go red is not a control);
* the canonical classifier returns CHAT_STYLE_DRIFT for a violating ordinary
  reply and leaves operational turns and valid boundaries alone;
* the same verdict reaches a host through `saipen response check --classify`.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
for _entry in (str(TOOLS), str(ROOT)):
    if _entry not in sys.path:
        sys.path.insert(0, _entry)

from saipen_engine import chat_style as CS  # noqa: E402
from saipen_engine import response_surface as RS  # noqa: E402
from test_guard_hostile_matrix import fresh_project  # noqa: E402
from test_hermetic_env import isolate_host_session  # noqa: E402

STYLE = (ROOT / "saipen" / "STYLE.md").read_text(encoding="utf-8-sig")


def setUpModule() -> None:
    isolate_host_session()


ENGLISH_ESSAY = "\n".join(
    [
        "Sure, I would be happy to explain what is going on here in detail.",
        "The style you are supposed to use is the compressed voice, and the reason this did "
        "not happen is that the agent never read the file that defines it.",
        "There are several contributing factors, and it is worth going through each of them "
        "carefully so that the picture becomes clear.",
        "First, the style file was not loaded, which means the agent had no way of knowing "
        "which language was required.",
        "Second, the skill that sets the default style was not invoked, because nothing "
        "forced it to happen at the start of the session.",
        "Third, the host system prompt says that readable prose matters more than concise "
        "prose, and that pulls in the opposite direction.",
        "Fourth, drift is the default failure mode: long conversations dilute the style "
        "instructions into a polite assistant tone.",
        "To fix this in the future, each session should read the style file first and only "
        "then write the first word.",
        "It would also help to add a mechanical check that refuses replies which are too "
        "long or written in the wrong language.",
        "I hope this explanation is useful, and please feel free to ask if anything is unclear.",
    ]
)

# Compressed English drops articles and copulas: the shape the voice contract asks
# for, in the wrong language for an `et` pin. Function-word counting alone cannot
# see it; the Estonian-marker floor does.
COMPRESSED_ENGLISH = (
    "Root cause found. Validator piped root names through locale encoding. Stray hook "
    "file outside cp1251 crashed capture. Fixed with explicit utf-8. Regression test "
    "red before fix, green after. Chat gate next: classifier passes every essay "
    "unmeasured, host hook checks operational reports only. Wiring now, then registry "
    "claim and adapter docs."
)

ESTONIAN_COMPRESSED = (
    "Juurpõhjus leitud. Valideerija saatis juurkausta nimed läbi lokaali kodeeringu. "
    "Hooki tekitatud prügifail väljaspool cp1251 kukutas jäädvustuse. Parandatud "
    "otsese utf-8-ga. Regressioonitest oli enne parandust punane, pärast roheline. "
    "Järgmine on vestlusvärav: klassifikaator laseb iga essee mõõtmata läbi, hosti "
    "hook kontrollib ainult operatiivseid aruandeid."
)

ESTONIAN_FULL = (
    "See vastus on liiga pikk ja ei järgi stiili, sest agent ei lugenud faili enne "
    "esimest vastust. Kui reeglid on olemas, siis peab neid ka kontrollima, muidu "
    "jäävad need ainult sooviks. Seetõttu lisasime värava, mis keeldub vastusest, "
    "mis on kas liiga pikk või kirjutatud vales keeles."
)

RUSSIAN = (
    "Ответ слишком длинный и не следует стилю, потому что агент не прочитал файл "
    "перед первым ответом. Если правила есть, их надо проверять, иначе они остаются "
    "пожеланием. Поэтому добавили ворота, которые отказывают в длинном ответе."
)

# The reference reply of future_gate/SAIPEN_agent_stillWritesProses.md is Estonian
# with Russian sentences mixed in: exactly the "decorative mixing" STYLE.md bans.
MIXED_ET_RU = (
    "Õige stiil: caveman-дед. reply_language: et pin. Eesti, igal vastusel, isegi kui "
    "sa rusise. Минус: система тянет в другую сторону. Miks romaan: STYLE.md polnud "
    "loetud enne esimest vastust. Он прямо конфликтует с правилом, и дрейф — это "
    "молчаливый провал по умолчанию, а не случайность."
)


class ConstantsMatchStyleTests(unittest.TestCase):
    """The machine copy is bound to the document it copies."""

    def test_every_sentinel_phrase_is_in_style_md(self):
        for phrase in CS.BANNED_OPENERS + CS.BANNED_CLOSERS + CS.BANNED_APOLOGIES:
            self.assertRegex(STYLE, rf'"{re.escape(phrase)}[!.]?"', phrase)

    def test_the_chat_line_budget_is_the_documented_absolute_max(self):
        self.assertRegex(STYLE, rf"absolute max {CS.CHAT_LINE_BUDGET}\b")

    def test_character_ceilings_equal_the_execution_owner(self):
        self.assertEqual(CS.CHAT_CHAR_BUDGET, RS.ORDINARY_RESPONSE_CHAR_BUDGET)
        self.assertEqual(CS.DETAILED_CHAT_CHAR_BUDGET, RS.DETAILED_RESPONSE_CHAR_BUDGET)

    def test_the_language_value_set_is_the_documented_table(self):
        rows = set(re.findall(r"^\| `([a-z]+)`\s*\|", STYLE, re.MULTILINE))
        self.assertEqual(rows, set(CS.LANGUAGE_SETTINGS))

    def test_the_pin_reader_returns_what_style_md_declares(self):
        declared = re.search(r"^\*\*`reply_language:\s*([a-z]+)`\*\*\s*$", STYLE, re.MULTILINE)
        self.assertIsNotNone(declared)
        expected = declared.group(1) if declared.group(1) in CS.PINNED_LANGUAGES else None
        self.assertEqual(CS.reply_language_pin(STYLE), expected)
        self.assertEqual(CS.reply_language_pin(), expected)

    def test_a_malformed_or_absent_pin_is_not_guessed(self):
        self.assertIsNone(CS.reply_language_pin("**`reply_language: eesti`**"))
        self.assertIsNone(CS.reply_language_pin("**`reply_language: auto`**"))
        self.assertIsNone(CS.reply_language_pin("no setting here"))
        both = "**`reply_language: et`**\n\n**`reply_language: en`**\n"
        self.assertIsNone(CS.reply_language_pin(both))


class BudgetTests(unittest.TestCase):
    def test_eight_lines_pass_and_nine_are_refused(self):
        eight = "\n".join(f"Line {n} fact." for n in range(CS.CHAT_LINE_BUDGET))
        self.assertEqual(CS.chat_style_errors(eight), [])
        nine = eight + "\nOne more."
        errors = CS.chat_style_errors(nine)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("9 lines", errors[0])

    def test_fenced_code_is_fact_not_prose(self):
        code = "\n".join(f"    step_{n}()" for n in range(30))
        text = f"Ran it.\n```python\n{code}\n```\nDone."
        self.assertEqual(CS.chat_style_errors(text), [])

    def test_one_enormous_line_still_breaks_the_ceiling(self):
        # T-1556 #2: a line count alone is not a compactness contract.
        text = "word " * 600
        errors = CS.chat_style_errors(text)
        self.assertTrue(any("characters" in error for error in errors), errors)

    def test_an_authorized_report_lifts_the_line_budget_only(self):
        nine = "\n".join(f"Finding {n}." for n in range(9))
        self.assertEqual(CS.chat_style_errors(nine, detail_authorized=True), [])
        too_long = "word " * 1200
        self.assertTrue(CS.chat_style_errors(too_long, detail_authorized=True))
        opener = "Sure.\n" + nine
        self.assertTrue(CS.chat_style_errors(opener, detail_authorized=True))

    def test_empty_and_non_text_are_not_judged(self):
        for value in ("", "   \n", None, 42):
            self.assertEqual(CS.chat_style_errors(value), [])


class SentinelTests(unittest.TestCase):
    def test_each_banned_opener_is_refused(self):
        for phrase in CS.BANNED_OPENERS:
            errors = CS.chat_style_errors(f"{phrase} the file is fine.\nSecond line.")
            self.assertTrue(any("banned opener" in e for e in errors), (phrase, errors))

    def test_each_banned_closer_is_refused(self):
        for phrase in CS.BANNED_CLOSERS:
            errors = CS.chat_style_errors(f"Fixed.\n{phrase}.")
            self.assertTrue(any("banned closer" in e for e in errors), (phrase, errors))

    def test_each_banned_apology_is_refused_anywhere(self):
        for phrase in CS.BANNED_APOLOGIES:
            errors = CS.chat_style_errors(f"Fixed.\nBut {phrase.lower()} about the delay.\nDone.")
            self.assertTrue(any("banned apology" in e for e in errors), (phrase, errors))

    def test_a_longer_word_is_not_the_banned_phrase(self):
        for text in ("Surely fine.", "Okayed by review.", "Sorrel soup recipe."):
            self.assertEqual(CS.chat_style_errors(text), [], text)

    def test_an_opener_inside_a_sentence_is_allowed(self):
        self.assertEqual(CS.chat_style_errors("Cache is fine. Sure enough it held."), [])

    def test_a_phrase_inside_fenced_code_is_not_judged(self):
        self.assertEqual(CS.chat_style_errors("Output:\n```\nSorry, not found\n```"), [])


class LanguageTests(unittest.TestCase):
    def test_estonian_pin_accepts_estonian_in_both_registers(self):
        for text in (ESTONIAN_COMPRESSED, ESTONIAN_FULL):
            self.assertEqual(CS.language_errors(text, "et"), [], text[:50])

    def test_estonian_pin_refuses_english_in_both_registers(self):
        for text in (ENGLISH_ESSAY, COMPRESSED_ENGLISH):
            errors = CS.language_errors(text, "et")
            self.assertTrue(errors and "reply_language is et" in errors[0], (text[:40], errors))

    def test_estonian_pin_refuses_russian_and_decorative_mixing(self):
        for text in (RUSSIAN, MIXED_ET_RU):
            errors = CS.language_errors(text, "et")
            self.assertTrue(errors and "Cyrillic" in errors[0], (text[:40], errors))

    def test_english_pin_refuses_estonian_and_accepts_english(self):
        self.assertTrue(CS.language_errors(ESTONIAN_FULL, "en"))
        self.assertEqual(CS.language_errors(ENGLISH_ESSAY, "en"), [])
        self.assertEqual(CS.language_errors(COMPRESSED_ENGLISH, "en"), [])

    def test_russian_pin_refuses_latin_prose_and_accepts_russian(self):
        self.assertTrue(CS.language_errors(ENGLISH_ESSAY, "ru"))
        self.assertTrue(CS.language_errors(ESTONIAN_FULL, "ru"))
        self.assertEqual(CS.language_errors(RUSSIAN, "ru"), [])

    def test_russian_prose_with_english_technical_terms_is_accepted(self):
        text = (
            "Валидатор падает на `git check-ignore`, потому что pipe кодируется через "
            "locale. Исправление: явный utf-8 и regression test, который сначала red, "
            "потом green. Остальные хосты не затронуты."
        )
        self.assertEqual(CS.language_errors(text, "ru"), [])

    def test_a_short_reply_is_not_judged(self):
        for pin in CS.PINNED_LANGUAGES:
            self.assertEqual(CS.language_errors("Done. Tests green.", pin), [])

    def test_facts_do_not_count_as_language(self):
        # Paths, identifiers, codes and inline code are exact facts in any voice.
        text = (
            "Parandatud: tools/validate.py:7684, `git check-ignore --stdin`, "
            "FINDINGS_CAPTURE_FAILED, T-1558, saipen_engine/chat_style.py."
        )
        self.assertEqual(CS.language_errors(text, "et"), [])

    def test_no_pin_means_no_language_verdict(self):
        self.assertEqual(CS.language_errors(ENGLISH_ESSAY, None), [])


class ClassifierTests(unittest.TestCase):
    def test_an_essay_is_chat_style_drift_not_ordinary_chat(self):
        klass, errors = RS.classify_final_response(
            ENGLISH_ESSAY, operational_turn=False, reply_language="et"
        )
        self.assertEqual(klass, RS.CLASS_CHAT_STYLE_DRIFT)
        self.assertTrue(errors)
        self.assertIn(RS.CLASS_CHAT_STYLE_DRIFT, RS.RESPONSE_CLASSES)

    def test_compliant_estonian_stays_ordinary_chat(self):
        klass, errors = RS.classify_final_response(
            ESTONIAN_COMPRESSED, operational_turn=False, reply_language="et"
        )
        self.assertEqual((klass, errors), (RS.CLASS_ORDINARY_CHAT, []))

    def test_the_language_pin_is_only_applied_when_supplied(self):
        klass, _errors = RS.classify_final_response(
            COMPRESSED_ENGLISH, operational_turn=False, reply_language=None
        )
        self.assertEqual(klass, RS.CLASS_ORDINARY_CHAT)

    def test_an_authorized_detail_request_lifts_the_line_budget(self):
        nine = "\n".join(f"Finding {n}." for n in range(9))
        klass, _e = RS.classify_final_response(nine, operational_turn=False)
        self.assertEqual(klass, RS.CLASS_CHAT_STYLE_DRIFT)
        klass, _e = RS.classify_final_response(
            nine, operational_turn=False, detail_mode=RS.DETAIL_MODE_AUDIT
        )
        self.assertEqual(klass, RS.CLASS_ORDINARY_CHAT)

    def test_an_operational_turn_is_never_reclassified_as_chat_drift(self):
        klass, _e = RS.classify_final_response(
            ENGLISH_ESSAY, operational_turn=True, reply_language="et"
        )
        self.assertEqual(klass, RS.CLASS_INVALID_OPERATIONAL_PROSE)


def classify_cli(project: Path, text: str):
    proc = subprocess.run(
        [
            sys.executable,
            str(TOOLS / "saipen.py"),
            "response",
            "check",
            "--stdin",
            "--json",
            "--classify",
            "--auto-eligibility",
            "--project-root",
            str(project),
        ],
        input=text,
        capture_output=True,
        encoding="utf-8",
        cwd=str(ROOT),
        check=False,
    )
    try:
        return proc.returncode, json.loads(proc.stdout)
    except json.JSONDecodeError:
        return proc.returncode, {"raw": proc.stdout[-400:], "err": proc.stderr[-400:]}


class CanonicalCliTests(unittest.TestCase):
    """The host-facing verdict: what a Stop hook actually receives."""

    def test_an_over_budget_reply_is_refused_with_its_class(self):
        project = fresh_project()
        nine = "\n".join(f"Fact {n} is exact." for n in range(9))
        rc, out = classify_cli(project, nine)
        self.assertEqual(rc, 1, out)
        self.assertFalse(out["ok"])
        self.assertEqual(out["class"], RS.CLASS_CHAT_STYLE_DRIFT)
        self.assertEqual(out["code"], "EXEC_RESPONSE_INVALID")
        self.assertTrue(any("9 lines" in e for e in out["errors"]), out["errors"])

    def test_the_pin_comes_from_the_running_style_md_not_the_caller(self):
        pin = CS.reply_language_pin()
        if pin not in CS.PINNED_LANGUAGES:
            self.skipTest("STYLE.md does not pin a reply language")
        wrong = {"et": ENGLISH_ESSAY, "en": ESTONIAN_FULL, "ru": ENGLISH_ESSAY}[pin]
        right = {"et": ESTONIAN_FULL, "en": COMPRESSED_ENGLISH, "ru": RUSSIAN}[pin]
        project = fresh_project()
        # The wrong-language sample must not be caught by the line budget alone.
        wrong = "\n".join(wrong.splitlines()[:6])
        rc, out = classify_cli(project, wrong)
        self.assertEqual(out.get("class"), RS.CLASS_CHAT_STYLE_DRIFT, out)
        self.assertEqual(rc, 1)
        self.assertTrue(any("reply_language" in e for e in out["errors"]), out["errors"])
        rc, out = classify_cli(project, right)
        self.assertEqual((rc, out.get("class")), (0, RS.CLASS_ORDINARY_CHAT), out)

    def test_stdin_is_decoded_as_utf8_not_the_host_locale(self):
        # A hook sends UTF-8 bytes. Decoded with the locale (cp1251 on the
        # operator's host) every Estonian diacritic became a Cyrillic letter,
        # and correct Estonian read as 33% Cyrillic under an `et` pin.
        pin = CS.reply_language_pin()
        if pin != "et":
            self.skipTest("the diacritic probe is Estonian; STYLE.md pins another language")
        text = (
            "Öö õhtul äärmiselt üle õue hüppab "
            "ööbik, ülemäära väärt päev, "
            "õõnes ülemäärane sõbralikult öösel. "
        ) * 2
        project = fresh_project()
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS / "saipen.py"),
                "response",
                "check",
                "--stdin",
                "--json",
                "--classify",
                "--project-root",
                str(project),
            ],
            input=text.encode("utf-8"),
            capture_output=True,
            cwd=str(ROOT),
            check=False,
        )
        out = json.loads(proc.stdout.decode("utf-8"))
        self.assertEqual((proc.returncode, out["class"]), (0, RS.CLASS_ORDINARY_CHAT), out)

    def test_a_compliant_short_reply_is_untouched(self):
        project = fresh_project()
        rc, out = classify_cli(project, "An ordinary explanation.")
        self.assertEqual((rc, out.get("class")), (0, RS.CLASS_ORDINARY_CHAT), out)


class StyleContractTests(unittest.TestCase):
    """The text a host injects is generated from STYLE.md, never hand-copied."""

    def test_the_context_names_the_pin_and_every_documented_ban(self):
        contract = CS.style_contract(STYLE)
        pin = CS.reply_language_pin(STYLE)
        self.assertEqual(contract["reply_language"], pin)
        context = contract["context"]
        if pin:
            self.assertIn(f"({pin})", context)
        self.assertIn(str(CS.CHAT_LINE_BUDGET), context)
        for phrase in CS.BANNED_OPENERS + CS.BANNED_CLOSERS + CS.BANNED_APOLOGIES:
            self.assertIn(phrase, context)
        self.assertNotIn("user own language", context)
        self.assertNotIn("user's own language", context)

    def test_each_pin_is_reflected_and_auto_is_not_invented_into_a_pin(self):
        for pin, name in (("et", "Estonian"), ("en", "English"), ("ru", "Russian")):
            contract = CS.style_contract(f"**`reply_language: {pin}`**\n")
            self.assertEqual(contract["reply_language"], pin)
            self.assertIn(name, contract["context"])
        auto = CS.style_contract("**`reply_language: auto`**\n")
        self.assertIsNone(auto["reply_language"])
        self.assertEqual(auto["reply_language_setting"], "auto")
        self.assertIn("precedence", auto["context"])

    def test_the_cli_prints_the_same_contract(self):
        proc = subprocess.run(
            [sys.executable, str(TOOLS / "saipen.py"), "response", "style", "--json"],
            capture_output=True,
            encoding="utf-8",
            cwd=str(ROOT),
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr[-400:])
        payload = json.loads(proc.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["code"], "STYLE_CONTRACT")
        expected = CS.style_contract()
        for key in ("reply_language", "chat_line_budget", "chat_char_budget", "context"):
            self.assertEqual(payload[key], expected[key], key)


if __name__ == "__main__":
    unittest.main()
