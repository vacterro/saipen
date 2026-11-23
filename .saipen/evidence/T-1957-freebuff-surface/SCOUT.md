# T-1957 SCOUT -- what the shipped FreeBuff code actually reads

## The question

The registry declares two FreeBuff loaders that read home dotfiles:

```json
"instruction_loaders": [
  { "name": "freebuff CLI",      "surfaces": ["~/.knowledge.md", "~/.AGENTS.md", "~/.claude.md"] },
  { "name": "FreeBuff Desktop",  "surfaces": ["~/.AGENTS.md", "~/.CLAUDE.md"] }
]
```

T-1956 proved the desktop half stale. SCOUT asked the same question of the CLI
half rather than inheriting T-1427's 2026-09 measurement, because both hosts
shipped after it.

## Method

Neither claim is taken from documentation or from our own test constants. Each
is read out of the artifact that runs, by byte:

| host | artifact | bytes | mtime |
|---|---|---|---|
| freebuff CLI | `~/.config/manicode/freebuff.exe` | 123,988,736 | 2026-10-22 09:11:33 |
| CLI wrapper | `~/.config/manicode/freebuff-metadata.json` | `version: 0.2.34, target: win32-x64` | -- |
| FreeBuff Desktop | `%LOCALAPPDATA%/Programs/@codebufffreebuff-desktop/resources/orchestrator/orchestrator.js` | 9,387,635 | 2026-10-29 08:27:12 |

The CLI wrapper at `C:\nodejs\node_modules\freebuff\index.js` is 1,038 bytes,
`launcher.js` downloads and execs `~/.config/manicode/freebuff.exe`, and the
whole knowledge logic lives in **that** binary -- so the .exe is the oracle,
not the npm package.

## Finding 1: the CLI home rule is `.AGENTS.md` then `.CLAUDE.md`, and has no `.knowledge.md`

The home reader, verbatim from the binary (`Ro$`, offset 100333821):

```js
async function Ro$(H){
  let {fs:A,logger:$}=H, L=H.homeDir??SWA.homedir(), D={}, I;
  try{I=await A.readdir(L)}catch(M){return $..., D}
  let E=new Map;
  for(let M of I){ if(!M.startsWith("."))continue;
    let P=M.slice(1).toLowerCase();
    if(v7.includes(P)) E.set(P,M) }
  for(let M of v7){ let f=E.get(M);
    if(f){ let P=Be.join(L,f); try{ let F=await A.readFile(P,"utf8"), U=`~/${f}`;
      D[U]=F; break } ... } }
  return D }
```

with `Nz=["AGENTS.md","CLAUDE.md"]; v7=Nz.map(h=>h.toLowerCase())`.

Three consequences, each measured:

- the accepted home names are exactly **`agents.md`, `claude.md`**, matched
  case-insensitively against dot-prefixed entries, so `.AGENTS.md` and
  `.CLAUDE.md` (and `.claude.md`, `.agents.md`) all match;
- the loop `break`s, so it reads **the first existing, in `v7` order**:
  `.AGENTS.md` before `.CLAUDE.md`;
- `~/.knowledge.md` is **not** a home surface: stripped it is `knowledge.md`,
  absent from `v7`.

`\.knowledge\.md` occurs **exactly once** in the 123,988,736-byte binary, and
that occurrence is the *project* predicate `D8A`:

```js
function D8A(H){ let A=sS$.basename(H).toLowerCase();
  if(v7.includes(A))return!0;
  if(A.endsWith(".knowledge.md"))return!0; return!1 }
```

So `*.knowledge.md` is a **project-file** name, never a home one. The registry's
`~/.knowledge.md` entry for the CLI names a path the running CLI never opens,
and its `~/.claude.md` spelling names the same file the `.CLAUDE.md` spelling
does, but at the wrong position in the order.

The CLI also reads **project** files, through `pWA`/`wo$` rooted at `cwd`:

```js
async function wo$({cwd:A,filePaths:$,...}){ ... E[M]=await L.readFile(Be.join(A,M),"utf8") }
```

## Finding 2: FreeBuff Desktop has no home surface at all

Re-measured in the artifact `app.asar` → `/electron/main.cjs` →
`resolveOrchestrator()` names:

- `loadUserKnowledgeFiles` 0, `selectKnowledgeFilePaths` 0;
- `userKnowledgeFiles` 1, and it is an unassigned **schema field** in the
  turn-state record, never a home read;
- the only loader is `loadClaudeProjectInstructions(cwd)`:
  `[KNOWLEDGE_FILE_NAMES.map(n => join(cwd, n)).find(isFile), join(cwd, ".claude", "CLAUDE.md")]`,
  with `KNOWLEDGE_FILE_NAMES = ["AGENTS.md", "CLAUDE.md"]`, gated at
  `turn.projectInstructions ? loadClaudeProjectInstructions(turn.cwd) : ""`;
- zero `join(<homedir>, '*.md')` call sites.

**Desktop's instruction surface is the project root, exclusively.**

## Finding 3: the freshness verdict is currently wrong on this machine

Measured live, before any change:

```
$ python -c "import autoinject; ..."
overall: current
  {'loader': 'freebuff CLI',     'surface': '~/.knowledge.md', 'status': 'current'}
  {'loader': 'FreeBuff Desktop', 'surface': '~/.AGENTS.md',    'status': 'current'}
```

Both rows are false claims about the loader named. The desktop row is the
T-1956 finding; the CLI row is new here -- it reports `current` from a file the
0.2.34 CLI does not read, and it would keep reporting `current` even if
`~/.AGENTS.md` (the file the CLI *does* read) were absent and stale.

The machine state, measured:

```
~/.agents/skills/saipen   exists (installed home)
~/.AGENTS.md              exists, carries the block
~/.knowledge.md           exists, carries the block
~/.CLAUDE.md              absent
AGENTS.md (project root)  absent   -> saipen host instructions: PROJECT_BLOCK_ABSENT
```

## The design question, and why one option is closed

The ticket offers: declare the project-root surface, *or* record that this host
no longer receives home activation.

Declaring the project root as an installer target is closed by `project_block.py`'s
own contract, which is not this ticket's to change:

> a block is never created, and text outside the markers is never rewritten

So the installer may not author a project `AGENTS.md` where none exists. What it
may do is stop claiming delivery it does not perform, and hand the project half
to the owner that already measures it (`project_block.status`, `HOST_SURFACE`
avoidance, `PROJECT_BLOCK_ABSENT`).

## Scope decision carried into BUILD

1. `instruction_loaders[].surfaces` becomes the **measured home contract** -- the
   thing the verdict is computed from. `.knowledge.md` leaves the CLI list;
   Desktop's list empties and it gains `scope: project` + `project_surfaces`.
2. `instruction_surfaces` (what the installer *writes*) stays a deliberate
   superset: it still writes `~/.knowledge.md` so an operator on an older CLI
   keeps activation. Writing a harmless file is not a false claim; *reporting*
   it as delivery is.
3. `instruction_contract_status` must stop counting a project-scoped loader as a
   home delivery, and must not report `current` for any loader from a surface
   that loader does not read.

That is the whole change. It removes a false `current` and adds no authority.

## What SCOUT deliberately did not do

- Did not re-run the injector against a scratch home yet (BUILD).
- Did not touch `project_block.py`, `protocol_admission.py`, or the installer's
  write list -- the first two only union `surfaces` (which shrinks, correctly),
  and the third is the compatibility superset described above.
- Did not claim the 2026-10-29 desktop update is a regression; T-1956 settled
  that with a revert-and-rerun control.
