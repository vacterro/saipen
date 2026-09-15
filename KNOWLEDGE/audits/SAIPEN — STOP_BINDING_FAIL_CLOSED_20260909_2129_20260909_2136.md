SAIPEN — STOP_BINDING_FAIL_CLOSED_20260909_2129

TARGET

Harden slash/skill handling for:

    /saipen stop
    saipen stop
    st

against agent-side project-root wandering.

PROBLEM

Observed with Solar Pro 4:

1. user issued only:
       /saipen stop

2. agent failed to resolve its assumed project path;

3. instead of returning a binding refusal, it searched unrelated filesystem
   locations for `.saipen`;

4. it opened unrelated SAIPEN projects;

5. it proceeded to run status/recover/continue/source/audit commands.

This is forbidden behavior even though the mechanical CLI itself is already
fail-closed.

TARGET BEHAVIOR

STOP is a bounded command.

Allowed pre-dispatch work:

    resolve loaded saipen_home
    resolve project_root using ONLY:
        explicit --project-root
        current Git worktree
        nearest ancestor .saipen

Then exactly one of:

A. bound project exists:

       execute canonical saipen stop

B. no bound project:

       return NOT_SAIPEN_PROJECT / BLOCKED
       name the cwd
       state that an explicit project root is required

       STOP IMMEDIATELY

No discovery.

FORBIDDEN AFTER BINDING FAILURE

No:

    find ... -name .saipen
    recursive home-directory search
    sibling search
    probing AppData for projects
    reading unrelated STATE.md
    saipen status on another candidate
    recover
    continue
    audit ingest
    source close
    attempt
    project guessing

A binding failure is TERMINAL for this invocation.

Do not try to be helpful by locating another project.

DIRECT RULE

For command class:

    STOP
    STATUS
    CONTINUE
    checkpoint-bound project commands

a failed canonical project-root resolution MUST NOT trigger model-driven
project discovery.

If the user did not provide an explicit root and no canonical root is
available:

    return the refusal.

Do not ask the filesystem to guess user intent.

REGRESSION

Fixture:

    cwd = directory with no Git owner and no ancestor .saipen

Input:

    saipen stop

Required:

    NOT_SAIPEN_PROJECT
    zero filesystem traversal outside cwd ancestry
    zero reads of unrelated .saipen directories
    zero writes
    zero secondary SAIPEN commands

Add a hostile fixture containing:

    sibling/project-a/.saipen/
    sibling/project-b/.saipen/

Required:

    neither sibling is inspected.

SLASH ADAPTER

If the host slash-command adapter knows the active workspace/project path,
forward it explicitly as:

    --project-root <bound workspace root>

Do not make the model rediscover information the host already knows.

If the host does NOT expose a project root:

    use the canonical cwd resolver
    fail closed when unresolved.

DEFINITION OF DONE

1. `/saipen stop` cannot initiate recursive project discovery;
2. unresolved project binding terminates the invocation;
3. unrelated SAIPEN projects cannot be selected heuristically;
4. no recovery/continue/audit/source command follows a failed STOP binding;
5. existing valid-project STOP behavior remains unchanged.