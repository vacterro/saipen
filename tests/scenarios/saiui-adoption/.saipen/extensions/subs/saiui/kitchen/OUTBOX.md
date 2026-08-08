# OUTBOX

## UI-001: add missing Save/Cancel controls to edit dialog
- **status:** ready
- **summary:** Edit dialog lacks explicit Save/Cancel; add controls per UI.md Iron Law 5
- **main_project_refs:** [src/ui/edit_dialog.py]
- **critical:** false
- **severity:** P2
- **producer:** saiui
- **source_head:** no-git
- **source_tree_fingerprint:** no-git-tree-v1:73748e1d840762e246d7581d5358bdcc6a1a3e151393c13730a968f4df2faaee
- **role_revision:** sha256:f2e3685b908a3b9837917f12c5414628d847c35fb72567f0306e2c8b19a8dab8
- **coverage:** edit_dialog.py, test_edit_dialog.py
- **payload:** unified diff for edit_dialog.py
- **verified:** pytest PASS (12 passed), ruff clean
- **instructions:** apply patch, run pytest, verify Save/Cancel visible at 640x480
- **base_head:** abc1234
- **patch:**
  ```diff
  +    def save_changes(self): ...
  +    def cancel_edit(self): ...
  ```
- **details:**
  User task: edit a queued item, save or discard changes.
  User cost: no visible confirm/cancel forces guesswork.
  Evidence: edit_dialog.py:45-67 has inline text field but no explicit
  save or cancel action; keyboard-only users are stuck.
  Existing capability: the backend EditQueueItem API already supports
  save/discard -- the controls are missing from UI.
  Golden Default violation: Iron Law 5 (predictable behavior) -- the
  same text field in view mode does not accept edits, but in edit mode
  it does, with no visible state change beyond cursor.
  Patch boundary: adds Save and Cancel buttons below the text field;
  does not change backend, persistence, or queue semantics.
  Backend contracts deferred: none -- all called APIs already exist.
  Residual risk: keyboard focus order needs testing; covered by
  existing test_edit_dialog.py which passes.
