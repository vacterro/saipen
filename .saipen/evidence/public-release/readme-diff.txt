diff --git a/CHANGELOG.md b/CHANGELOG.md
index 26d6ae03..f3dec1cc 100644
--- a/CHANGELOG.md
+++ b/CHANGELOG.md
@@ -1,6 +1,16 @@
 # Changelog
 > Older entries live in [CHANGELOG_ARCHIVE.md](CHANGELOG_ARCHIVE.md) -- this file keeps the most recent ~10.
 
+## 8.1.0 -- 2026-10-04 -- Public installation and removal
+
+- Make the documented install, set, cold continue, validate, uninstall, and reinstall lifecycle executable through the installed launchers on Windows, macOS, Linux, and Git Bash.
+- Preserve instruction-file bytes, user settings and hooks, project memory, added files, and edited installed files during removal. Record per-file ownership instead of recursively deleting skill directories.
+- Fix Git Bash removal of native hooks when Windows Python emits CRLF; preserve edited OpenCode guard artifacts.
+- Integrate completed continuation, recovery, module-identity, evidence-cleanup, closure, and remediation fixes from the development branches. Leave unfinished source normalization and failed operator-WAIT work in their existing branches.
+- Preserve exact project-memory bytes across checkouts. Validate exported closed quarantine records without requiring private bodies that are deliberately excluded; authority reads and recovery still require the originals.
+- Refresh Quick Start with Python prerequisites, exact platform commands, installed terminal launchers, cold-start behavior, removal guarantees, and reinstall steps.
+- Require successful validation of the exact tagged commit before GitHub creates a release. All runtime operations remain local and use Python's standard library.
+
 ## 8.0.2 -- 2026-10-02 -- A tree that actually runs (T-1582, T-1593)
 
 The committed tree at the previous tag could not execute: 33 modules failed to import, so every command that touched them was dead on arrival. This release ships the accumulated `tools/` delta as four commits and restores the run.
diff --git a/README.md b/README.md
index ca3f2f83..423d06b8 100644
--- a/README.md
+++ b/README.md
@@ -26,7 +26,7 @@ uninstall are all local — no cloud service, no daemon, no database.
 [![Release](https://img.shields.io/github/v/release/vacterro/saipen?sort=semver&label=release)](https://github.com/vacterro/saipen/releases)
 [![License: MIT](https://img.shields.io/github/license/vacterro/saipen?color=blue)](LICENSE)
 
-**v8.0.2** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | MIT
+**v8.1.0** | [Spec](SPEC.md) | [Guide](GUIDE.md) | [Core](saipen/CORE.md) | [Maintenance](saipen/MAINTENANCE.md) | [Style](saipen/STYLE.md) | [UI](saipen/UI.md) | [Conformance](saipen/CONFORMANCE.md) | MIT
 
 **Shortcut keys.** A shortcut is the whole message, never a prefix: `cc` continues, `sss` reports status, `st` stops; Cyrillic twins `сс`, `ссс`, `аа`, `ее`, `еее`, `рр` work too. [Full 19-key map](saipen/CORE.md#110-command-surface). `ff` → `focus`; `xx` → `cut`; `vv` → `build`; `zz` → `undo`.
 
@@ -74,40 +74,89 @@ session ends.
 
 ## Quick start
 
-**1. Install once per machine** — teaches Claude Code, Codex, Gemini, OpenCode,
-Aider, Antigravity, and any generic `~/.agents/skills` reader (FreeBuff, etc.):
+Requires **Git, Python 3.11 or newer**, and a coding agent. No `pip` install,
+account, server, or daemon is needed. Keep the clone until you uninstall;
+the installed agent instructions and update checks refer to its location.
+
+**1. Clone once:**
 
 ```bash
 git clone https://github.com/vacterro/saipen
 cd saipen
-powershell -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1     # Windows
-bash bootstrap/inject.sh                                            # macOS / Linux
 ```
 
-<sub>What that touches, so nothing is a surprise: it appends a marked
-`<!-- SAIPEN:BEGIN -->...<!-- SAIPEN:END -->` block to the agent instruction
-files you already have (`~/.claude/CLAUDE.md`, `~/.config/opencode/AGENTS.md`,
-`~/.codex/AGENTS.md`, `~/.gemini/GEMINI.md`) — backing each up to `.bak` first —
-and copies the protocol into the matching skill folders. Nothing outside those
-paths, no daemon, no network calls.</sub>
+**2. Install once per machine** with the command for your platform:
+
+Windows (PowerShell):
+
+```powershell
+powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap\inject.ps1
+```
+
+macOS / Linux / Git Bash:
+
+```bash
+bash bootstrap/inject.sh
+```
+
+The installer adds a marked SAIPEN block to supported agent instructions,
+backs up existing files, copies the runtime into skill folders, and installs
+the matching guard hooks while keeping unrelated settings. It supports Claude
+Code, Codex, Gemini, OpenCode, Aider, Antigravity, and generic
+`~/.agents/skills` readers. Restart an already running agent after installation.
+
+**3. Open your own project in the agent.** These are **chat commands**:
+
+```text
+saipen set
+saipen continue
+saipen validate
+```
+
+`set` creates the project's `.saipen/` memory. In a new empty project,
+`continue` asks for the first goal or backlog; give the agent your task, then
+use `saipen continue` in later sessions. Validation must report PASS.
+
+<details>
+<summary>Run the same smoke check directly in a terminal</summary>
+
+From your project folder, Windows:
+
+```powershell
+& "$env:USERPROFILE\.agents\skills\saipen\bin\saipen.cmd" set
+& "$env:USERPROFILE\.agents\skills\saipen\bin\saipen.cmd" continue
+& "$env:USERPROFILE\.agents\skills\saipen\bin\saipen.cmd" validate
+```
 
-**2. Start a project** — open an agent in your folder, type:
+macOS / Linux / Git Bash:
 
-> `saipen set`
+```bash
+"$HOME/.agents/skills/saipen/bin/saipen" set
+"$HOME/.agents/skills/saipen/bin/saipen" continue
+"$HOME/.agents/skills/saipen/bin/saipen" validate
+```
 
-**No install?** Paste one line to any agent:
+The launcher is installed with the skill; no PATH change is required.
+</details>
 
-> Read &lt;clone&gt;/saipen/BOOT.md first (cold-start kernel), then &lt;clone&gt;/saipen/INDEX.md + &lt;clone&gt;/saipen/STYLE.md and follow them.
+**Uninstall:** return to the clone and run one command:
 
-**Changed your mind?** One command puts it back:
+```powershell
+powershell -NoProfile -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1
+```
 
 ```bash
-powershell -ExecutionPolicy Bypass -File .\bootstrap\uninstall.ps1  # Windows
-bash bootstrap/uninstall.sh                                         # macOS / Linux
+bash bootstrap/uninstall.sh
 ```
 
-It strips exactly the marked block (leaving the rest of your file alone), saves
-a `.uninstalled.bak` copy first, and removes the skill folders.
+Removal strips the marked instruction block, removes SAIPEN hook entries and
+unchanged installed files, and preserves your other settings, hooks, skills,
+later edits, backups, and project `.saipen/` memory. Edited or extra installed
+files remain for you to keep or remove. Run the install command again to
+reinstall. After uninstall, the clone itself can be deleted normally.
+
+**Try without installing:** tell your agent to read
+`<clone>/saipen/BOOT.md` and follow its cold-start router.
 
 ## Why not just chat history?
 
@@ -320,3 +369,20 @@ OpenAI, etc.)? Per-platform notes live in `extensions/adapters/`.
 <p align="center">
   <img src="assets/SAIPEN_design2_alpha.png" alt="SAIPEN Stamp" width="120"/>
 </p>
+
+<!-- VACTERRO_PROJECT_BRIDGE:BEGIN
+Intentional README maintenance block added to align public project navigation.
+Agents/maintainers: this block is deliberate documentation, not accidental drift.
+Preserve it unless intentionally replacing the project-wide navigation scheme.
+-->
+---
+
+## Project network
+
+This repository is part of the broader **SAIPEN / vacterro** project ecosystem.
+
+[**Author hub**](https://github.com/vacterro) · [**SAIPEN HQ**](https://github.com/saipenhq) · [**SAIPEN Core**](https://github.com/vacterro/saipen) · [**ZAICODE**](https://github.com/vacterro/zaicode) · [**FastPrompter**](https://github.com/vacterro/FastPrompter) · [**SAIPEN Community**](https://discord.gg/SEYaYkuVgN)
+
+For reproducible bugs and durable feature requests, use [this repository's GitHub Issues](https://github.com/vacterro/saipen/issues). Use Discord for quick discussion, screenshots, and cross-project feedback.
+
+<!-- VACTERRO_PROJECT_BRIDGE:END -->
diff --git a/VERSION b/VERSION
index 8b22a322..8104cabd 100644
--- a/VERSION
+++ b/VERSION
@@ -1 +1 @@
-8.0.2
+8.1.0
