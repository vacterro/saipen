# T-1914: Installed-Runtime Parity Report (SRC-324 Gap E)

**Ticket:** T-1914 [P0]  
**Source Receipt:** SRC-324 § Gap E  
**Scope:** Canonical vs Installed Runtime Parity for Native Operator Origin Path  
**Date:** 2026-10-25T14:52:00Z  
**Verdict:** **DRIFT_DETECTED -- BLOCKING**

---

## 1. Measured Evidence Matrix (E01 - E10)

| Clause | Dimension | Measured Value | Measuring Command | Parity Status |
|---|---|---|---|---|
| **E01** | Canonical source hook hash | `fad31c4af85db4e9c7974efa0989ab39e334b414c147224755d4f4c2b1bd819e` | `python -c "import hashlib; print(hashlib.sha256(open('extensions/adapters/zaicode/saipen-guard.py', 'rb').read()).hexdigest())"` | Baseline Source |
| **E02** | Installed hook hash | `f99b50c60b9e64360d9a5d401cba8a5b1b4ffba63034b2caddfac3e48d41391e` | `python -c "import hashlib; print(hashlib.sha256(open('C:/ProgramData/SAI/SAIPEN/runtime/d838d464759d97d3/extensions/adapters/zaicode/saipen-guard.py', 'rb').read()).hexdigest())"` | **DRIFT DETECTED** (Mismatch) |
| **E03** | Installed client module hash | `5eebb3a52ceb2424c6d0455ae3a4154b94a07bd2709def52fe82394dfe6d4e1a` (Source: `f2f1878e8b6f1b879dcca3ca649d079ce55c668921ff960a6599b4d174577963`) | `python -c "import hashlib; print(hashlib.sha256(open('C:/ProgramData/SAI/SAIPEN/runtime/d838d464759d97d3/tools/saipen_engine/host_authority_client.py', 'rb').read()).hexdigest())"` | **DRIFT DETECTED** (Mismatch) |
| **E04** | Installed broker module hash | `0f8d854d69fed1bf190e78b7c35ca04808fe9cc9f03418e93c6ae261e4077eb2` (Source: `0f8d854d69fed1bf190e78b7c35ca04808fe9cc9f03418e93c6ae261e4077eb2`) | `python -c "import hashlib; print(hashlib.sha256(open('C:/ProgramData/SAI/SAIPEN/runtime/d838d464759d97d3/tools/saipen_engine/host_authority_broker.py', 'rb').read()).hexdigest())"` | **MATCH** |
| **E05** | Running broker service generation | Registered: `svc-d86cd9f97afc8f881fab7843`, PID 13252 in `broker.json` (DEAD / no live listener). Live account brokers: `sai-accounts.exe --broker` (PIDs 20648, 22860). | `python -c "import sys; sys.path.insert(0, 'tools'); from saipen_engine import host_authority_broker; print(host_authority_broker.read_status())"` | **STALE ENDPOINT / ABSENT** |
| **E06** | Active ZAICODE executable generation | Executable: `V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\zcode\packages\desktop\dist\win-unpacked\ZAICODE.exe`, PID 1064, SHA256: `f18f9848d7984061eb7a1bbeb8388567a0c915be428d77312deb4a01e82e46a4` | `python -c "import hashlib, psutil; [print(p.pid, p.exe(), hashlib.sha256(open(p.exe(), 'rb').read()).hexdigest()) for p in psutil.process_iter(['pid', 'name']) if p.info['name'] and 'zaicode' in p.info['name'].lower()][:1]"` | Measured Running Process |
| **E07** | Actual OS ancestry | Process tree: `ZAICODE.exe (PID 1064) -> ZAICODE.exe (PID 26952) -> ZAICODE.exe (PID 23828) -> ZAICODE.exe (PID 5380)`. Hook execution chain in `broker.log`: `['python.exe', 'python.exe', 'bash.exe', 'bash.exe', 'bash.exe', 'zaicode.exe', 'zaicode.exe', 'zaicode.exe']`. | `python -c "import psutil; p = psutil.Process(1064); parents = []; curr = p; ..."` and tail of `C:\Users\vac34\.saipen\authority\broker.log` | Measured Process Hierarchy |
| **E08** | Real UserPromptSubmit payload | Schema: `{"hookEventName": "UserPromptSubmit", "prompt": "<request_text>", "session_id": "...", "turn_id": "...", "cwd": "..."}` mapping to ingress envelope `{"request_text": prompt, "request_digest": ingress_digest(prompt), "session_id": session, "message_id": turnId}`. Observed in `.saipen/cache/ingress/`. | `python -c "import glob, json; print(json.load(open(glob.glob('.saipen/cache/ingress/*.json')[0]))['message_id'])"` | Verified Envelope Structure |
| **E09** | Exact origin issuance verdict | `(None, 'absent')` | `python -c "import sys; sys.path.insert(0, 'tools'); from saipen_engine import host_authority_client; print(host_authority_client.issue_operator_origin(project='V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_SAIPEN', session='sess-1', host='zaicode', request_text='cc', event_id='evt-1', action='continue', diagnose=True))"` | **FAILED (SERVICE_UNAVAILABLE / ABSENT)** |
| **E10** | Exact worker registration verdict | `(None, 'absent')` | `python -c "import sys; sys.path.insert(0, 'tools'); from saipen_engine import host_authority_client; print(host_authority_client.register_operator_worker({}, 1234, diagnose=True))"` | **FAILED (SERVICE_UNAVAILABLE / ABSENT)** |

---

## 2. Analysis of Parity Discrepancies

1. **Hook Drift (E01 vs E02)**:
   The canonical source hook at `extensions/adapters/zaicode/saipen-guard.py` contains the latest hardening from SRC-324 (including `seal_diagnostic`, typed refusal classes, and bounded renewal). The deployed hook in the machine runtime directory `C:/ProgramData/SAI/SAIPEN/runtime/d838d464759d97d3` is an earlier generation and lacks these updates.

2. **Client Module Drift (E03)**:
   `tools/saipen_engine/host_authority_client.py` in canonical source differs from `C:/ProgramData/SAI/SAIPEN/runtime/d838d464759d97d3/tools/saipen_engine/host_authority_client.py`. The deployed runtime does not have the updated client contracts.

3. **Broker Service Deadlock (E05, E09, E10)**:
   The registered authority broker PID 13252 in `C:\Users\vac34\.saipen\authority\broker.json` has exited. Live calls from `host_authority_client` return `(None, 'absent')`. The forensic log `broker.log` proves that previous attempts from ZAICODE failed with `HOOK_NOT_FOUND` because the broker's hook hash verification refused the drifted hook.

---

## 3. Parity Determination

Per the verification requirements of T-1914 and SRC-324 Gap E:
- Source parity is NOT running-process parity.
- The observed drifts in E02, E03, E05, E09, and E10 are **BLOCKING**.
- Runtime components cannot be assumed equal to canonical source without an authorized runtime synchronization / reinstallation cycle.
