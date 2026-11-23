Test: an agent that has worked this project before resumes, and checks the
files before trusting what it remembers.

RFC § 1.1's "MUST NOT rely on chat context for project state" reads naturally
as advice for a cold agent -- which is the harmless case. A cold agent has no
memory to mislead it, and BOOT.md is written for exactly that: "you are
continuing a project whose entire brain persists in `.saipen/`."

The dangerous case is the warm agent. It worked here earlier, it remembers
real specifics, and it is wrong because somebody else moved the project in
between. Recollection feels like knowledge, so nothing prompts a re-read, and
the resulting mistakes are stated with full confidence.

A real incident: an agent resumed believing it had last shipped `v7.80.0`.
Another agent had taken the project to `v7.83.0` in the meantime -- 36 logged
events and an entire subSaipen refactor. It was about to review "the protocol"
against a three-version-old mental model and report those findings as fact. It
caught the drift only by chance, noticing a field in `tools/validate.py` it
knew it had never written.

The check is mechanical and costs one comparison, using fields that already
exist:

- `STATE.md`'s `agent:` is not you -> someone else wrote the last checkpoint.
- `STATE.md`'s `updated:` is newer than your own last write -> the project
  moved without you.

Either one means your memory is stale by definition. Re-read `STATE`, `BOARD`
and the active `LOG` tail from disk, and treat every prior belief -- version
numbers, ticket states, what you think you shipped -- as unverified until a
file says otherwise.

The failure this catches: an agent confidently reviewing, reporting, or
building on a project state that stopped existing several versions ago.
Confident staleness is worse than ignorance, because ignorance asks.

Behavioral, README-only: the assertion is about an agent choosing to verify
its own recollection, which no static fixture can express -- a fixture could
only show the end state, and the end state looks perfectly valid. Correctly
declares no expected outcome, so `tools/run_scenarios.py` skips it.

## Incident (moved out of RFC.md in v7.93.0)

A real incident: an agent resumed believing it had last shipped `v7.80.0`, while another agent had taken the project to `v7.83.0` in between (36 events, a whole refactor). It was about to review "the protocol" against a three-version-old mental model and report the findings confidently; it noticed only by chance, spotting a field in `tools/validate.py` it knew it had never written.

RFC.md keeps the rule and one clause of why; the narrative lives here so the
constitution stays readable for a weak model on a cold start.
