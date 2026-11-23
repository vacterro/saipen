# Traps

## Never write repo files with PowerShell Set-Content / Add-Content

Windows PowerShell 5.1 `-Encoding utf8` writes a **BOM** and mangles
non-ASCII: an em-dash, an arrow or a section sign each come back as a
two- or three-character Cyrillic sequence -- the UTF-8 bytes read as
cp1251 and re-encoded. The sequences are deliberately not reproduced
here: `tools/validate.py` FAILs any shipped doc that contains one, and a
warning that trips over its own example is one nobody can keep. Bit us twice:
the FreeBuff skill copy was unreadable for this exact reason (v1.2.2), then
the same command corrupted README.md at v3.1.1 seconds after we fixed it.

Use the editor tools (Write/Edit) for any file with prose or Unicode.
PowerShell is fine for git commands, not for authoring.

Appending one LOG line is no exception -- `Add-Content` is exactly how a
LOG landed with invalid UTF-8 in the middle of a run, and the "recovery"
was a byte-patch that quietly transliterated the text. Safe appends:

- PowerShell: `[System.IO.File]::AppendAllText('.saipen/LOG.md', $line + [Environment]::NewLine, (New-Object System.Text.UTF8Encoding($false)))`
- bash: `printf '%s\n' 'LINE' >> .saipen/LOG.md`
- Python: `open('.saipen/LOG.md', 'a', encoding='utf-8').write(line + '\n')`

Recovery: `git checkout <tag> -- <file>` restores clean bytes; strip a BOM
with `sed -i '1s/^\xEF\xBB\xBF//' <file>`.

## Never ask "continue?" when board empty

RFC § 2.1 ZERO-PROMPT AUTO-TRANSITION: bare command + empty `## TODO` = MUST
go to HUNT, never WAIT at DONE. If HUNT clean, MUST go to ADD immediately.
A `WAIT:` at DONE with an empty `## TODO` is legal only in the fixed forms
RFC § 1.2 lists; anything else there is drift, and `tools/validate.py` FAILs
it. Read the count there, never from here. An untriaged MARKHUNT ticket in
`## BLOCKED` is one of those forms -- NOT, as this paragraph used to claim, a
board that has not halted: § 2.1 defines the halt as no workable `## TODO` and
no `## DOING`, and says outright that `## DONE` and `## BLOCKED` tickets never
count against it. The board HAS halted; the brake is a whitelisted pause. This paragraph said the
MARKHUNT case was the *only* legal WAIT until v7.101.0, which had been wrong
for nine releases. Violated this session: stopped at
DONE asking vague "continue?" instead of running ADD.

## Never write LOG timestamps from local clock

LOG timestamps MUST be UTC (RFC § 1.2). Using local clock produces off-by-hours
drift that corrupts Recovery's audit trail. `tools/validate.py` FAILs a timestamp more than 3h in the *future* and WARNs
when one moves backwards by more than 5 minutes. It also once carried a third
check that compared the absolute difference -- that one never fired at all
(its regex did not match a LOG line) and was removed in v7.99.0. This line
said "WARNs on >3h drift" until v7.101.0, describing neither the severity nor
the check that actually exists. Violated this session: wrote 07:55-08:25 timestamps when UTC was
~01:21.

## Never skip REVIEW phase STATE update

BUILD -> VERIFY -> REVIEW -> SHIP -> DONE. Each phase gets its own STATE.md
entry, even if REVIEW is a quick diff check. Skipping it (going VERIFY -> SHIP
without `phase: REVIEW`) creates a jump the protocol's transition table
doesn't show. Violated this session on T-200 and T-202.

## Readers that skip junctions

`~/.agents/skills` (FreeBuff-class) and Antigravity plugin dirs only see
real directories with lowercase names — junctions/symlinks are ignored, and
the IDE holds a lock so junctions can't even be created while it runs. The
injector copies files there instead, which means those copies go stale:
re-run `inject.ps1` after every `git pull`.

## A harness reporting total failure is broken, not the subject

Three times in one session a scratch harness claimed everything was dead.
`audit_floor` said 20 of 20 portable-floor checks never fire; the warn audit
said 8 of 8 categories are unreachable *and* the repo was dirty. All false.
Causes, in order found:

- `subprocess.run(["bash", ...])` from Python on Windows resolves to the WSL
  stub in System32, not git-bash. With no distro installed it emits a UTF-16
  error and runs nothing, so the harness saw empty output and scored every
  case as never-fired. Invoke git-bash by full path instead.
- Matching on `warn()`'s internal category key, which is never printed. The
  output carries the message text, not the key.
- Testing `"FAIL" in output` while several validator messages contain the
  word "FAILs" in ordinary prose.

Rule: a real defect is almost never total; a misconfigured harness almost
always is. Before believing any negative, run a control whose result is
already known and confirm it comes back right. Control silent -> report
nothing and fix the instrument. Codified in `phases/verify.md`.

## Never chain `git tag` after a commit with `;`

Twice in one session a tag reached origin pointing at the wrong commit, both
times from the same shape:

```sh
git commit -F- <<'MSG' ... MSG
git tag -a vX.Y.Z -m "..." && git push origin main && git push origin vX.Y.Z
```

The commit failed -- once on a hook rejection, once on shell quoting -- and the
tag command, being a separate statement, ran anyway and tagged the PREVIOUS
commit. Both then pushed cleanly, because pushing a tag has no opinion about
what it points at.

Use `&&` so the tag cannot outlive a failed commit:
`git commit ... && git tag -a ... && git push origin main && git push origin vX.Y.Z`

The first occurrence published a GitHub Release built from the wrong commit,
carrying the previous version's notes and a VERSION asset that disagreed with
its own tag name. The second was caught by `release.yml`'s tag-vs-VERSION
guard, added because of the first -- the release job failed in 16 seconds and
nothing was published. The guard works; the habit that needs it is the defect.

Moving a published tag is a force-push on a ref: RFC § 1.1 destructive, ask
first.

## Python string escapes keep eating shell and path text

Four separate times in one session: `\1` in a sed replacement became `chr(1)`
(octal escape) and silently corrupted a fixture's `saipen_version` line and,
later, a YAML workflow; a Windows path written `C:\Program Files\Git\usr\...`
inside a normal triple-quoted string tripped `truncated \uXXXX escape`.

Use raw strings for anything containing a backslash, or write the file with
the editor tools rather than through a Python heredoc. The failure is quiet
when it lands inside data (`chr(1)` in a Markdown file passed review for
weeks) and loud only when it happens to break a parser.

## A global suppressor disarms a per-line check forever

`tools/validate.py`'s timestamp-inversion check has read every LOG line since
v7.99.0 and reported nothing since 27.07.26, because the warning sits behind
`if not documented_inversions:` -- one boolean derived from whether ANY segment
anywhere contains the phrase "observed historical timestamp inversions". Three
sealed DEC lines from July and August 2026 carry it, so the whole check was
switched off for every line written afterwards, in every future segment.

It cost a real defect: E-5171 stamped `26.09.01` between E-5170 at
`01.09.26 08:27` and E-5172 at `01.09.26 13:21` -- the digits in ISO order, so
it parses as 2001-09-26 and lands 25 years behind the segment it sits in. A
25-year backwards jump produced zero output. Found by `tools/saipen_metrics.py`
reading dates for a report, not by 227 red controls.

The shape, not the instance: a suppressor whose scope is "the file" rather than
"the lines it documents" cannot expire. Documented history is documented; the
next line is not, and one acknowledgement of an old problem must never grant
amnesty to problems that have not happened yet. Whenever a check can be quieted,
tie the quieting to the exact evidence it excuses -- an event id, a path, a hash
-- so it stops covering anything written after it.

## Writing ABOUT a detector trips the detector

`verification_evidence` refuses a VERIFY checkpoint whose text claims a red
result, and it is right to: an evidence parser that tried to work out who was
being quoted would be one an agent could talk its way past. The cost lands on
tickets that FIX detectors, because describing the work means writing the
tokens the detector hunts. Three checkpoints were refused this way in one
session -- one quoting a validator refusal verbatim, one containing the word
"failure", one listing `NOT PASS` as a spelling the new grammar rejects.
`_NEGATION_RE` is case-insensitive and matches the negated pass form anywhere
in the line; `_claims_failure` counts every red token and only forgives the
zero-count forms.

Do not weaken the grammar for this. Pre-check the text instead:

```
python -c "import sys;sys.path.insert(0,'tools');from saipen_engine.log import _claims_failure;print(_claims_failure(open('msg.txt',encoding='utf-8').read()))"
```

Write the checkpoint to a file, check it, then pass it. Describe red results
without spelling them: "the near-miss spellings", "a red claim", "a zero
count". The facts stay exact -- gate names, counts and `file:line` are
untouched -- and only the prose around them avoids the tokens.

## An mtime is not evidence, and a concurrent committer is real

Three shipped protocol documents showed fresh timestamps mid-session, two of
them matching HEAD byte for byte, and it read as a phantom writer in a tree
where `T-473`'s clobber class is a known open risk. It was neither a phantom
nor a gate: `ecd77546` at 15:09:59, authored by a session working this repo in
parallel, committing `saipen/phases/hunt.md` and `saipen/MAINTENANCE.md`
directly -- no `ship`/`closure` prefix, no ticket, straight past the board. The
third file was the same session's uncommitted work in progress. The v7.240.1
release built on top of it without noticing.

Two lessons, and the second is the expensive one.

`audit_checks.py` was suspected and is innocent: it mutates a `pristine`
copytree in a worker root, never the live tree. Do not repeat that guess.

The real cost: that commit added a second `deletes, moves and renames nothing`
to `hunt.md`, and `replace()` mutates only the FIRST occurrence -- so the
control `hunt.md regains deletion authority` mutated one, the validator still
found the other, and a red control stopped being evidence with nobody having
touched it. Third instance of this class after the CHANGELOG anchor (T-1245).
**A duplicated anchor is a silently disarmed control.** When editing a document
that `audit_checks.py` names in `CASES`, check whether the new text repeats an
anchor phrase.

## Narrative Authority Leakage

Free-form prose acquiring control authority because a validator searches text
for a magic phrase. A line that merely DISCUSSES the phrase gains the power the
phrase carries, and the discussion is usually written by whoever is diagnosing
the defect.

Three instances, all expensive, all found by accident:

- the timestamp-inversion amnesty was one boolean over the whole corpus, so
  three sealed DEC lines disarmed the check for five weeks;
- repairing it, the SCOUT checkpoint that quoted the marker disarmed the check
  again, one level up, for the very event it was describing;
- the clean-HUNT marker was the same shape and still live: 28 LOG lines
  contained `hunt -> clean @` and only 24 were the canonical record.

`saipen_engine.log.structural_marker_events` is the single owner of the rule.
A marker is authority only when all three hold, and dropping any one reopens
the class:

- **taxonomy** -- a `RUN` reporting an action is not a `DEC` deciding one;
- **anchoring** -- the marker must BEGIN the event text, never appear in it;
- **bounding** -- an `after_event` id, so an exception cannot cover work that
  had not happened when it was granted. A suppressor scoped to "the file"
  cannot expire.

When adding any check that reads free text for meaning, route it through that
helper rather than writing a fourth substring test. And give every suppressor a
red control that goes red once its authorization no longer applies: without
one, "no warning" and "the warning was silenced" are the same observation.
