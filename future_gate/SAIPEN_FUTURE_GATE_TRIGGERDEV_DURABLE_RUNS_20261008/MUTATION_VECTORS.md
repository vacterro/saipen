# Mutation Vectors After Durable Runs

These are optional directions that become plausible after the durable Run foundation is mature.

They are intentionally not part of the initial acceptance gate.

## 1. Multi-agent fan-out

A parent Run may spawn independent child Runs for:
- audit;
- implementation;
- security review;
- performance verification;
- UI acceptance.

Results converge through machine contracts instead of prose handoffs.

## 2. Speculative parallel attempts

For expensive/high-risk Work:
- start two compatible executor Attempts;
- accept the first valid evidence-backed result;
- cancel the loser safely.

Requires strict effect isolation.

## 3. Cost-aware executor routing

Scheduler may optimize:
- subscription availability;
- latency;
- model strength;
- cost;
- quota;
- task difficulty;
- historical success rate.

Never compromise capability or safety requirements.

## 4. Reliability scoring

Track executor/provider reliability by failure class:
- transient tool failure;
- hallucinated completion;
- test reliability;
- runtime crashes;
- timeout rate.

Use only as routing evidence, not as a permanent model stereotype.

## 5. Dynamic task decomposition

A large Work item can split into child Runs when:
- capability requirements diverge;
- context size grows;
- independent verification is useful;
- one segment can run cheaply.

## 6. Durable scheduled goals

Cron-like or event-driven Runs become possible after Run identity is stable.

Examples:
- nightly audits;
- dependency drift review;
- weekly protocol health;
- periodic runtime doctor;
- delayed re-verification.

## 7. Event-triggered continuation

External events may complete waitpoints:
- GitHub CI;
- file arrival;
- account authentication;
- release approval;
- external service response.

## 8. Local execution cluster

Multiple Windows accounts / hosts may consume capability queues.

Run ownership remains centralized.

Executors become workers.

## 9. Cloud extension

Only later:
- remote worker;
- encrypted project projection;
- cloud queue;
- remote checkpoint store.

Local-first semantics should remain valid.

## 10. Policy-driven autonomy tiers

Run may carry policy such as:
- read-only;
- local-write;
- local-commit;
- release-prep;
- publish-authorized.

Irreversible effect authorization becomes explicit.

## 11. Time and resource budgets

Run/Attempt may declare:
- max wall time;
- max premium executor time;
- max retries;
- max context;
- max tool cost.

Budget exhaustion becomes typed orchestration state.

## 12. Automatic evidence compaction

Old Attempts may retain full raw evidence while active Run context references compact summaries plus immutable hashes.

## 13. Provenance graph

Every artifact/result can answer:
- which Run produced it;
- which Attempt;
- which executor;
- which source receipts;
- which code fingerprint;
- which validation evidence.

## 14. Replay debugger

Operator can inspect a failed Run and simulate:
- retry policy;
- alternate executor choice;
- route transitions;
- waitpoint completion;

without mutating the live Run.

## 15. Autonomous mutation laboratory

A future SAIPEN can use failed Runs as structured training/evolution input:

failure class
-> missing invariant
-> proposed Future Gate
-> isolated mutation
-> regression
-> adoption

This is the long-term bridge between operational failures and protocol mutation.
