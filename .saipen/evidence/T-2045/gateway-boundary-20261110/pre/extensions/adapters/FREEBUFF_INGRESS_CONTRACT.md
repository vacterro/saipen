# Freebuff Native Operator Ingress Contract

Status: NOT_INSTALLED / BLOCKED for T-1822 until a real host-side event source exists.

## Required upstream event

EVENT: `user_message_submitted`

The native Freebuff host must deliver this event to the existing SAIPEN
host-authority broker. A model-writable file, environment variable, MCP tool,
or CLI argument is not sufficient proof.

Required fields:

- `host_identity`: authenticated native Freebuff Desktop identity (name, version,
  executable, code signer where available)
- `host_session_id`: stable Freebuff session identifier
- `event_id`: unique message/event identifier
- `message_digest`: exact SHA-256 digest of the original user message
- `canonical_project`: canonical SAIPEN project identity
- `project_lineage`: SAIPEN project lineage identity
- `operator_action`: one of the broker's bounded actions
  (`start`, `continue`, `goal`, `authorize-goal`, `append`, `handoff`,
  `report`, `resolve-gate`, `retire`, `supersede`)
- `issuer_evidence`: trusted process ancestry / hook evidence
- `freshness`: issued timestamp and expiry
- `replay_key`: unique replay-prevention key
- `consumption`: one-time consumption state recorded by the broker

## Broker requirements

The broker must independently derive and verify:

- project identity and lineage
- session binding
- exact request digest
- current task/budget epoch
- host process ancestry
- expiry and replay state
- one-time consumption
- canonical Source binding where a Source is used

## Explicit non-goals

- Do not advertise `supported_carrier_mechanisms` until real installed-host
  acceptance passes.
- Do not treat byte equality of a staged file as human-origin authentication.
- Do not let a model-controlled process invoke the trusted ingress route.
- Do not confuse an MCP tool callable by the model with an authenticated
  human-message hook.

## Current registry state

`extensions/adapters/registry.json` keeps Freebuff as:

- `host_prompt_available: false`
- `prompt_to_work_binding: NOT_INSTALLED`
- `supported_carrier_mechanisms: []`

This must remain unchanged until Freebuff Desktop implements and passes the
contract above.
" 