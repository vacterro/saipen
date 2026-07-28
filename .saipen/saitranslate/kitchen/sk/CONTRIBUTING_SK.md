<!-- TRANSLATED TO SK -->
# Contributing to SAIPEN

SAIPEN is a specification first, an implementation second. Most contributions
are changes to `saipen/RFC.md`, a `phases/*.md` file, or the conformance
tooling in `tests/` -- not application code.

## Before proposing a change

Run the [SAIPEN Litmus Test](SPEC.md#the-saipen-litmus-test) against your
idea:
1. Does it make the transition between agents more reliable?
2. Does it make the behavior of different models more uniform?
3. Does it reduce the probability of context loss?

If the answer is "no" to at least two of these, it's out of scope for this
protocol, however useful it might be elsewhere.

## Reporting a gap

Open an issue describing:
- which file/section the gap is in (RFC.md, a phase doc, a schema, a test)
- the concrete evidence (a quote, a command and its output, a scenario where
  current behavior breaks)
- what you'd expect instead

Vague reports ("this feels off") are harder to act on than a specific
`grep`/reproduction. See the bug report issue template for the shape this
should take.

## Making a change

1. Read `saipen/RFC.md` and the relevant `phases/*.md` file(s) fully before
   editing -- most apparent gaps turn out to already be addressed elsewhere,
   or deliberately scoped a certain way for a documented reason.
2. Check `CHANGELOG.md` and `.saipen/KNOWLEDGE/decisions.md` for prior art.
   Don't silently reopen a decision that was already made and rejected --
   if you have new evidence a past rejection was wrong, say so explicitly
   in the PR description.
3. Every normative change (a MUST/MUST NOT/SHOULD) needs a `CHANGELOG.md`
   entry and, where practical, coverage in `tests/validate.sh` +
   `tests/validate.ps1` (both platforms) or a fixture under
   `tests/scenarios/`.
4. Pred otvorením PR spustite kanonický validátor:
   ```bash
   python tools/validate.py
   ```
   Toto je ten, na ktorom záleží – kontroluje `STATE.md` proti
   `extensions/schemas/state.schema.json`, prechádza graf udalostí `LOG.md`
   cez uzavreté segmenty a overuje runtime manifest a injector prepojenie.
   `tests/validate.sh` / `validate.ps1` sú **zmrazená prenosná podlaha**
   pre hostiteľov bez Pythonu (uvádzajú to na začiatku každého súboru):
   menej kontrol, ponechané len aby hostiteľ bez Pythonu nebol bez ničoho.
   Spustite ich tiež, ak sa vaša zmena dotýka niektorého z nich, ale nikdy
   *namiesto* – prejdenie len podlahy dokazuje oveľa menej, než sa zdá.
   CI spúšťa kanonický validátor pri každom pushi a PR bez ohľadu na to
   (`.github/workflows/validate.yml`).
5. Bump `VERSION` per the scheme in `phases/ship.md` (patch for docs-only
   clarifications, minor for new normative behavior, major for breaking
   contract changes) and keep `README.md`'s version badge in sync --
   `tests/validate.sh`/`.ps1` check this automatically when run from a
   clone of this repo.

## Style

- Protocol and phase docs: terse, RFC-2119 keywords where they matter, no
  filler. See `saipen/STYLE.md`.
- Everything in this file, commit messages, code comments, and the
  CHANGELOG: plain and professional. The project's own chat/LOG voices
  (`saipen/STYLE.md`) don't apply to artifacts.

## What's out of scope

- Turning SAIPEN into a distributed consensus system. See
  `SPEC.md`'s Concurrency & Distribution Boundaries section.
- Machine-parseable LOG marker grammar beyond the existing skeleton.
  `LOG.md` stays prose around a fixed shape.
- A `saipen doctor` command or similar redundant with `saipen validate` +
  `saipen status`.

These have each been proposed and evaluated before; reopening them needs
new evidence, not just re-asking.
