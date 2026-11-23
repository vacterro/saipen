# T-1891 — one parser decides when a conformance receipt was written

The freshness window is the only thing that stops an old PASS from certifying
the current tree. It was reachable, and one byte of whitespace turned it off.

## The defect

`_strict_iso_utc` **stripped** a stamp before parsing it. `conformance_status`
parsed the **raw** string for its age arithmetic, inside a bare
`except Exception: pass`:

```python
age_seconds = 0
try:
    rdt = datetime.datetime.fromisoformat(receipt["timestamp_utc"].replace("Z", "+00:00"))
    age_seconds = (ref - rdt).total_seconds()
except Exception:
    pass
```

`fromisoformat` refuses a padded string. So the stamp passed validation (the
validator stripped) and failed ageing (the arithmetic did not), the `except`
swallowed it, and `age_seconds` stayed at its initial `0` — maximally fresh.
The `age_seconds > FRESHNESS_WINDOW_SECONDS` branch could not fire.

Measured on one receipt, changing nothing but the whitespace:

| `timestamp_utc` | `_strict_iso_utc` | age arithmetic | true age | classification |
| --- | --- | --- | --- | --- |
| `2020-01-01T00:00:00.000000Z` | accepted | 214963200 s | 214963200 s | `STALE_PASS / aged-beyond-freshness-window` |
| `  2020-01-01T00:00:00.000000Z  ` | accepted | **0 s** | 214963200 s | `CURRENT_PASS` |

214963200 seconds is 6.81 years. The second receipt certified the current tree
without ever being aged. Confirmed through the public classifier, not the
helper:

    clean aged   status=STALE_PASS  stale_reason=aged-beyond-freshness-window
    padded aged  status=CURRENT_PASS stale_reason=None

## Why P2 and not P1

It is not a forgery path. `_strict_validate_receipt` runs first and still
enforces schema, `exit_code`/verdict consistency, `content_hash`, checkpoint
hashes and source binding. What the padding bypassed is the *age* decision, so
an otherwise genuine old receipt could be made to look current. And the bypass
is latent in this project: of 3918 receipts on this checkout, **0** carry a
padded or unparseable stamp. Nothing can exploit it today; it would be
invisible the day something did, which is why it is fixed rather than noted.

## The change

`tools/saipen_engine/conformance.py` — one parser, `_strict_utc_datetime`,
returning the aware instant or `None`:

* `_strict_iso_utc` formats the instant it returns;
* `_future_beyond_skew` measures against it;
* `_parse_utc` (reverify-evidence ordering) consumes it first;
* the ageing branch in `conformance_status` calls it directly.

The ageing branch no longer swallows a parse failure. The strict validator has
already proven the stamp parses, so a `None` there is an internal
contradiction, and it is now reported as `INVALID_RECEIPT` rather than being
silently aged at zero.

`tools/test_t1891_freshness_parser.py` — 12 controls: the padded stamp ages,
the clean stamp keeps its verdict, padding no longer changes the
classification, a fresh receipt stays current, strictness for naive stamps and
non-UTC offsets is unchanged, a future stamp is still never recoverable, and
the pre-fix raw-parse shape cannot return to the ageing branch.

## Verification

**The control.** `.saipen/evidence/T-1891-freshness/red-control.py` runs the
same assertions twice in one process: once on this tree, once with
`conformance_status` replaced by a copy whose *only* difference is the pre-fix
age arithmetic. Transcript in `red-control.log`:

    current tree green         : True
    pre-fix tree green         : False
    pre-fix clean-stamp green  : True
    CONTROL OK -- the age arithmetic is the fix, not the harness.

The pre-fix half fails with exactly the measured defect:

    AssertionError: 'CURRENT_PASS' != 'STALE_PASS'
    timestamp_utc: '  2020-01-01T00:00:00.000000Z  '

and the clean-stamp control still passes there, so the red is the parse
appearing, not the harness failing to run.

**The family.** 10 modules, 286 tests, exit 0 — no red at all:

    test_t1891_freshness_parser, test_t1412_conformance_truth,
    test_t1792_auto_doctor, test_conformance_corpus, test_conformance_lineage,
    test_conformance_projection, test_conformance_remediation_evidence,
    test_conformance_repair_boundary, test_src085_conformance_disposition,
    test_source_receipts

    286 tests in 208.488s — OK  (family-run.log)

**The population.** 3918 receipts on this checkout: 0 padded, 0 unparseable
before the change and 0 unparseable after it, so no live receipt changed class
because of the new parser.

## Not claimed

* This is the conformance family, not the full 7576-test suite. The recorded
  baseline still stands at 55 red and nothing here claims otherwise.
* The bypass needed no operator authority and granted none: it made an old
  genuine receipt look current, and the strict validator still ran first.
* `_parse_utc` still tolerates a naive stamp for *evidence ordering*, where
  its only consumer compares `created_at` values it does not certify. What a
  receipt must prove about its own UTC-ness is decided by
  `_strict_utc_datetime` inside `_strict_validate_receipt`, and the table test
  asserts the two agree on every stamp either one accepts.
* Publication state is `pending`; `saipen ship` still refuses on the foreign
  staged batch, the standing operator blocker.
