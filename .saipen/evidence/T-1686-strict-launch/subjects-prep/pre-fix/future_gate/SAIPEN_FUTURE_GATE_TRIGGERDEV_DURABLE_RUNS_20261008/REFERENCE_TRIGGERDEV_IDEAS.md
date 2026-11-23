# Trigger.dev Ideas Relevant to SAIPEN

This note records the concepts that inspired the Future Gate. It is not a claim that SAIPEN should copy Trigger.dev's implementation.

Repository:
https://github.com/triggerdotdev/trigger.dev

## Source-derived concepts

Trigger.dev describes itself as an open-source platform for AI workflows with long-running tasks, retries, queues, observability, and elastic scaling.

Its current public README highlights:

- long-running tasks without ordinary serverless-style timeouts;
- durability;
- retries;
- queues;
- idempotency;
- human-in-the-loop;
- realtime/streaming;
- observability;
- checkpointing;
- versioning;
- concurrency controls;
- structured task inputs/outputs.

Relevant public references:

- README:
  https://github.com/triggerdotdev/trigger.dev/blob/main/README.md

- Waitpoint tokens:
  https://github.com/triggerdotdev/trigger.dev/blob/main/docs/wait-for-token.mdx

- Errors and retrying:
  https://github.com/triggerdotdev/trigger.dev/blob/main/docs/errors-retrying.mdx

- How it works:
  https://github.com/triggerdotdev/trigger.dev/blob/main/docs/how-it-works.mdx

- Runtime task payload schemas:
  https://github.com/triggerdotdev/trigger.dev/blob/main/docs/tasks/schemaTask.mdx

## Mapping to SAIPEN

### Durable tasks -> Durable Runs

Trigger.dev treats long-running execution as durable logical work.

SAIPEN mutation:
make `/goal` create or own a durable Run identity.

### Checkpoint/resume -> SAIPEN semantic checkpoints

Trigger.dev explicitly exposes checkpoint/resume concepts.

SAIPEN mutation:
persist resume-safe semantic boundaries so process/model death does not require reconstruction from prose.

### Waitpoint tokens -> Canonical Waitpoints

Trigger.dev wait tokens expose:
- an ID;
- status;
- timeout;
- completion;
- optional idempotency key;
- output payload.

SAIPEN mutation:
WAIT_USER and WAIT_EXTERNAL become first-class typed wait objects.

### Retries -> Attempt model

Trigger.dev separates logical task behavior from retries/attempts.

SAIPEN mutation:
Work/ticket remains stable while different executor attempts may fail, retry, or fail over.

### Idempotency -> Duplicate-safe transitions/effects

Trigger.dev documents idempotency as a reliability primitive.

SAIPEN mutation:
phase transitions, wait completion, evidence registration, provisioning and publication should have replay/duplicate semantics.

### Queues/concurrency -> Capability lanes

Trigger.dev uses queues/concurrency to control execution.

SAIPEN mutation:
schedule Work into capability-aware lanes instead of handing tasks to incompatible sessions.

### Checkpointed waiting -> Release premium executors

Trigger.dev's execution model separates waiting from continuous compute.

SAIPEN mutation:
WAIT_USER / long external waits should release model/executor leases and reacquire later.

### Versioning -> Run runtime pinning

Trigger.dev exposes versioned deployments/runs.

SAIPEN mutation:
a live Run binds to a compatible protocol/runtime generation; upgrades must not silently reinterpret it.

### Structured task schema -> Structured Work envelope

Trigger.dev validates task payload schemas.

SAIPEN mutation:
critical Work requirements move into machine-readable envelopes:
required capabilities, validation contract, sources, outputs, effects.

### Observability -> Run trace graph

Trigger.dev emphasizes tracing/logging.

SAIPEN mutation:
trace Run -> Work -> Attempt -> Executor -> Validation -> Evidence -> Effect -> Waitpoint.

### Cached completed subtask results during retry -> Selective result reuse

Trigger.dev documents workflows where completed child task results can be reused on retry.

SAIPEN mutation:
late-stage failure should not automatically invalidate earlier exact-fingerprint proof.

## What not to copy blindly

Do not copy merely because Trigger.dev has it:

- cloud deployment;
- SaaS control plane;
- TypeScript SDK shape;
- frontend hooks;
- Kubernetes/self-hosting model;
- autoscaling infrastructure;
- web dashboard architecture.

SAIPEN's immediate environment is different.

The value is in durable orchestration primitives, not product surface parity.

## Core lesson

The strongest conceptual lesson is:

A long-running job should be a durable logical execution, not a process that must remain alive.

For SAIPEN:

model, provider, process, Windows session and compatible runtime instance may disappear.

The Run should remain.
