# RAPORT — SAIPEN ingress: a shell redirect operator becomes the operator's request

- **Report id:** RAPORT-SAIPEN-INGRESS-SHELL-OPERATOR-20260918
- **Date:** 2026-09-18
- **Reporter:** agent `buffy` (SAIPEN seat inherited from project STATE), host opencode (`SAIFREN`)
- **Reporter project:** `V:\___VAC\__K\__CODE\_PY\_AUDAPACK`
- **Project lineage:** `lineage-79944d6c0334416ebe1001e97de6c1cc`
- **Protocol version (all homes):** 8.0.1
- **Observed runtime home:** `C:\Users\vac34\.config\opencode\skills\saipen`
- **Protocol home (source):** `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN`
- **Guard plugin:** `C:\Users\vac34\.config\opencode\plugins\saipen-guard.js`
- **Defect class:** `ingress-payload-extraction` / `shell-operator-as-request` + `obligation-laundering`
- **Severity:** P1

## 0. TL;DR

A shell redirection or pipe operator placed after a `saipen` ingress verb is
extracted as the **request payload**. The guard then refuses the line
`INGRESS_TRANSPORT_UNSAFE`, records a transport obligation over those operator
bytes, and prints `saipen start --hex <hex>` as the route. `BOOT.md` instructs
the session to run the named route; running it discharges the obligation and
**mints a real ticket + source receipt from shell punctuation**.

Measured on this host this session, read-only, by importing the engine directly:

```
ingress_payload('saipen start 2>&1')          -> '2>&1'
ingress_rewrite('saipen start 2>&1')          -> 'saipen start --hex 323e2631'
ingress_payload('saipen start > out.txt')     -> '> out.txt'
ingress_rewrite('saipen start > out.txt')     -> 'saipen start --hex 3e206f75742e747874'
ingress_payload('saipen start | cat')         -> '| cat'
ingress_rewrite('saipen start | cat')         -> 'saipen start --hex 7c20636174'
ingress_payload('saipen start 2>/dev/null')   -> '2>/dev/null'
```

`0x323e2631` decoded is `2>&1`. The recorded obligation digest
`2642b5d63833864f9c0c6138c0a17d8c320ddd6258dfcdaf7a05abd9fbf24a8a` is exactly
`sha256(b"2>&1")` (verified). The chain is closed: the guard fabricated a
request out of shell syntax, the refusal carried a route to persist it, and the
route did what it promised.

This is **not** covered by any prior report. `RAPORT-SAIPEN-GUARD-20260917`
covers a backslash **path** dropping the canonical exemption; the restart reports
cover a plugin **freshness race**; the read-only probe report covers a closed
**verb set**. None of them touch payload **extraction** — the parser making a
request out of shell metacharacters.

## 1. Reproduction (read-only import; no project mutation)

```py
import sys, hashlib
sys.path.insert(0, r"V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_SAIPEN\tools")
from saipen_engine import guard_events as g

g.ingress_payload("saipen start 2>&1")     # -> '2>&1'
g.ingress_rewrite("saipen start 2>&1")     # -> 'saipen start --hex 323e2631'
g.ingress_payload("saipen start | cat")    # -> '| cat'
g.ingress_payload("saipen start --json")   # -> None   (correctly NOT a payload)
```

Observed output on 8.0.1:

```
'saipen start > out.txt'     -> '> out.txt'    | 'saipen start --hex 3e206f75742e747874'
'saipen start 2> err.txt'    -> '2> err.txt'   | 'saipen start --hex 323e206572722e747874'
'saipen start >nul'          -> '>nul'         | 'saipen start --hex 3e6e756c'
'saipen start 2>/dev/null'   -> '2>/dev/null'  | 'saipen start --hex 323e2f6465762f6e756c6c'
'saipen user-request 2>&1'   -> '2>&1'         | 'saipen start --hex 323e2631'
'saipen start --json'        -> None           | None
'saipen start | cat'         -> '| cat'        | 'saipen start --hex 7c20636174'
```

`--json` (an option) correctly yields no payload; `> out.txt`, `| cat`,
`2>/dev/null` (all shell operators) yield one. The parser's guard is
`payload.startswith("-")` (`guard_events.py:973`), which rejects option-shaped
tokens but not operator-shaped ones.

## 2. Root cause (exact sources)

### 2.1 The parser accepts any token after the verb as the request

`tools/saipen_engine/guard_events.py:954-975` (`ingress_payload`):

```py
text = command.strip()
head = text.split(" ", 2)
if len(head) < 3 or head[0] != "saipen" or head[1] not in (
    command_effects.INGRESS_PAYLOAD_VERBS
):
    return None
payload = head[2].strip()
if len(payload) >= 2 and payload[0] in "'\"" and payload[-1] == payload[0]:
    payload = payload[1:-1]
payload = payload.strip()
if not payload or len(payload) > MAX_INGRESS_REWRITE_CHARS or payload.startswith("-"):
    return None
return payload
```

`head[2]` is everything after `saipen start` — including `2>&1`, `> out.txt`,
`| cat`. The only rejection is a leading `-`. There is no check against the
shell-syntax class `_SHELL_SYNTAX_CHARS` (line 184), even though that set is
exactly the guard's own definition of "this line is shell, not a request".

### 2.2 Why this line reaches the ingress path at all

`guard_events.py:1286-1295` (`map_event`):

```py
cli_tokens = _saipen_cli_tokens(command) if command else None
verb = _saipen_cli_verb(command) if cli_tokens is not None else None
if verb is None and command:
    ingress_route = ingress_rewrite(command)
```

`>` and `&` are in `_SHELL_SYNTAX_CHARS`, so `_saipen_cli_tokens` bails into
`_ingress_payload_tokens` (`:997`), which requires ONE quoted token and returns
`None` when there is none. `verb` is therefore `None`, and the line is handed to
`ingress_rewrite` — which fabricates a payload from `head[2]`.

### 2.3 The refusal arms a persisted obligation

`guard_events.py:1469-1497`:

```py
if mapped.get("canonical_next_command"):
    verdict["canonical_next_command"] = mapped["canonical_next_command"]
    verdict["ingress_transport"] = "hex"
    if verdict.get("code") not in _INTRINSIC_REFUSALS:
        verdict["admitted"] = False
        verdict["code"] = "INGRESS_TRANSPORT_UNSAFE"
        _record_pending_ingress(event, project_root, mapped)
```

`_record_pending_ingress` (`:1413-1443`) calls `pending_ingress.record(root,
payload, mapped["canonical_next_command"])`, which writes
`.saipen/recovery/pending-ingress.json` with `digest = sha256("2>&1")`
(`pending_ingress.py:82-112`).

### 2.4 BOOT tells the session to run the route; the route launders the bytes

`BOOT.md` entry table: *"`next: saipen start --hex <hex>` — run exactly that"*.
`entry.py:232-245` consumes the obligation:

```py
obligation = pending_ingress.pending(root)
owed = pending_ingress.enforce(root, text, supersede=supersede_ingress, commit=not dry_run)
if owed is not None:
    return _refuse(owed.pop("code"), owed.pop("detail"), **owed)
provenance = operator_task.witness(text, obligation_met=bool(obligation) and not obligation.get("malformed"))
```

A `--hex 323e2631` call decodes to `2>&1` (`saipen.py:2749-2762`), matches the
recorded digest, discharges the obligation, and proceeds to mint the receipt and
the ticket with witness `transport_obligation`. The provenance mechanism (T-1372)
does exactly what it was built to do — **the defect is upstream: what it was
given to protect was never a request.**

## 3. Observed consequence (this session, disclosed)

A single command — `saipen start 2>&1`, typed to see the guard's own answer —
produced this chain on `_AUDAPACK`:

```
E-1450  DEC: user request SRC-055 projected as T-199 (user_explicit)
E-1451  DEC: claimed via SAIOPS -- owner buffy
```

- `.saipen/intake/active/SRC-055.md` body: `2>&1`
- `SRC-055.meta.json` `request_provenance.compared_digest`:
  `2642b5d63833864f9c0c6138c0a17d8c320ddd6258dfcdaf7a05abd9fbf24a8a`
- `.saipen/BOARD.md` `## DOING`: `T-199 [P1] 2>&1` (claimed)
- `.saipen/STATE.md`: `phase: SCOUT`, `task: T-199`

The project is now in a **claimed state whose Work text is shell punctuation**,
and its `phase`/`task` were moved by a non-request. It is not self-cleanable by
the agent: `ticket retire` (OPS.md) requires an operator-authority receipt whose
own bytes carry a grant capsule, and the receipt in question (`SRC-055`) is
`2>&1`. Operator action is required to retire it.

## 4. Severity and impact

- **P1.** Any `saipen start`/`user-request` line with a trailing shell redirect
  or pipe — a natural thing to type, and exactly what a model does to *capture*
  the guard's output — silently becomes protocol Work. The most common forms are
  `2>&1` (capture stderr) and `| cat`/`| more`.
- The created Work carries **operator authority** (`transport_obligation`
  witness), so no downstream gate can distinguish it from a genuine request.
  This is the same class T-1376 exists to prevent — authority laundering — with
  the bytes supplied by the shell, not the model.
- The refusal's own route (`--hex`) makes the accident **worse**: following the
  guard's instruction is what commits the garbage.
- Any Windows or POSIX session using the guard's advertised recovery transport
  is exposed.

## 5. Suspected owner

- `tools/saipen_engine/guard_events.py` — `ingress_payload` (`:954-975`) and
  `ingress_rewrite` (`:978-994`); the missing shell-syntax rejection.
- `tools/saipen_engine/guard_events.py` — `map_event` (`:1286-1295`) and the
  `INGRESS_TRANSPORT_UNSAFE` verdict (`:1469-1497`), which arm the obligation.
- `tools/saipen_engine/pending_ingress.py` — `record`/`enforce`; correct as
  written, but it faithfully persists a payload the upstream parser should never
  have produced.

## 6. Repair candidates (non-binding; maintainer decides)

1. In `ingress_payload`, reject a payload whose first character (or any
   unstructured operator token) is in `_SHELL_SYNTAX_CHARS`:
   `if payload[0] in _SHELL_SYNTAX_CHARS: return None`. A request never
   legitimately begins with `>`, `<`, `|`, `&`, `;`.
2. Better: require a recognized transport shape. A bare unquoted `head[2]` that
   is not a quoted string is unlikely to be a real request; only accept the
   `head[2]` unquoted form when it is not shell syntax.
3. At the refusal site, if `ingress_payload` returns `None` for a line that
   *does* contain shell syntax, classify it `shell` (ordinary refusal / no
   obligation) rather than fabricating an `INGRESS_TRANSPORT_UNSAFE` route.
4. Add a normalized-digest sanity rule: an obligation whose payload is pure shell
   punctuation (no alphanumeric character) is a defect, not a request, and must
   not be recorded.

## 7. Related

- `RAPORT-SAIPEN-GUARD-20260917` (home `.saipen/evidence/`) — backslash path
  drops the canonical-operation exemption; adjacent classification family, but a
  different mechanism (path parsing, not payload extraction).
- `RAPORT-SAIPEN-GUARD-RESTART-20260918`, `RAPORT-SAIPEN-GUARD-PRODUCER-DIVERGENCE-20260918`
  (home `.saipen/evidence/`) — plugin freshness race; independent.
- `SAI-DEFECT-20260918-guard-readonly-probe-gap`, `SAI-DEFECT-20260918-saipenview-guard-restart`
  (protocol_incidents inbox) — same "one question, two answers" family.
- `SRC-053` (home intake) — the still-unimplemented canonical incident channel.

## 8. Side effects disclosed

- One protocolist packet was written to
  `%LOCALAPPDATA%\saipen\protocol_incidents\inbox\SAI-DEFECT-20260918-ingress-shell-operator-as-request.md`.
- The `_AUDAPACK` project side effect in §3 is real and disclosed; this reporter
  did **not** fabricate a closure for it. It requires operator authority to
  retire (`T-199`/`SRC-055`).
- No canonical SAIPEN protocol-tree file was hand-edited by this report.
- Every parser probe above was a read-only import in a scratch interpreter; the
  only writes in this session are this report and the packet.

— end of report —
