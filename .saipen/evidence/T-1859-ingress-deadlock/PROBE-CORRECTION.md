# Correction: the four hook probes in the 15:01 operator report proved nothing

Date: 2026-10-23 ~15:10 local
Ticket: T-1859 (AC-04), T-1858 (AC-04)
Status: diagnostic correction, no state mutation

## What the report showed

Four invocations of `saipen-guard.py`, each answered:

```
{"ok": true, "ingress_id": null, "sealed": false}
```

They were read as "hook healthy, broker says no". That reading is wrong.

## Why they were hollow

`saipen-guard.py` prints exactly that object at its **early return** when the
event carries no `host_ingress` dict:

```python
ingress = event.get("host_ingress")
if not isinstance(ingress, dict):
    print(json.dumps({"ok": True, "ingress_id": None, "sealed": False}))
    return 0
```

`ok: true` there means "nothing to do", not "hook works". Nothing was written,
no broker was contacted, no origin was requested.

Two independent reasons the report's probes fell into that path or past it:

1. **Unparsable event.** The event was built with Git Bash `printf` and a
   backslash-heavy Windows path. My reproduction of the same shape produced an
   event that did not parse as JSON; the hook's `except (ValueError, OSError)`
   turns that into `event = {}`, which is the early-return branch above.
2. **Wrong `--saipen-root`.** Three probes passed
   `--saipen-root V:\...\_ZAICODE` (the project root). The hook imports the
   engine from `<saipen-root>/tools`, so that root yields
   `ModuleNotFoundError` -> `{"ok": false, "code": "ENGINE_UNREACHABLE"}`.
   The engine lives in the **saipen_home**, `_SAIPEN/tools`, not in the project.

## What a correct probe shows

`--saipen-root V:\...\_SAIPEN` (the `saipen_home:` of `_ZAICODE/.saipen/STATE.md`),
well-formed JSON, valid `request_digest`:

```
{"ok": true, "ingress_id": "ing-f8fe2dda772df52d", "destination_op": "continue", "sealed": false}
```

An ingress id is minted (the envelope is admitted and written), and the origin
is refused: `BROKER_CLIENT_NOT_AUTHENTICATED` — "a shell tool call is not a
hook". That refusal is the security property working, not a defect. It cannot
be lifted from a shell: the broker compares the *process ancestry* against the
registered host's own hook invocation.

## Consequence for the operator question

The probe cannot answer "will cc work after restart". Only a real host-spawned
hook invocation can, i.e. an operator `cc` typed into the ZAICODE prompt.
That is T-1859 AC-01 LIVE and stays open until it is observed.
