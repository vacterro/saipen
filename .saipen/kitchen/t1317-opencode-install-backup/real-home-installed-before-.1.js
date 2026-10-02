// SAIPEN guard adapter for OpenCode (SRC-028:R012 / SRC-030 Part 9).
//
// Installed by the bootstrap injectors into the GLOBAL LOCAL PLUGIN DIRECTORY
// the runtime actually discovers: `~/.config/opencode/plugins/saipen-guard.js`
// (plural `plugins/`; registry.json owns this path and the legacy singular
// surface the injector cleans up so the hook is never loaded twice).
//
// One file, no shared state: uninstall is `rm` of exactly this file, and
// re-install is an overwrite, so unrelated user plugins and configuration are
// never touched.
//
// Verified host contract (OpenCode 1.18.x, `opencode debug config`):
//   * the plugin factory is invoked with a context object
//     ({ project, client, worktree, directory, $ }) and NO session identity,
//   * `tool.execute.before(input, output)` receives the tool name on `input`
//     (`input.tool`, plus the host session on `input.sessionID`) and MUTABLE
//     tool arguments on `output.args`,
//   * throwing from the hook prevents the host tool from executing.
//
// Behavior contract:
//   allowed action            -> host tool proceeds (guard exit 0)
//   guard refusal             -> host tool does not execute (thrown error)
//   guard failure / invalid
//   output / unreachable      -> fail closed for consequential mutations
//   verified built-in reads   -> never consequential; no guard round trip
//
// This file TRANSLATES only: it forwards one bounded JSON event
// (event/host/cwd/tool_name/tool_input/actor/session_id) to
// `saipen guard --event-json -` and blocks on a nonzero exit. All protocol
// semantics -- target sets, patches, canonical operations, ownership -- live
// in the guard. The adapter never re-implements a protocol rule.
//
// Actor identity: the OpenCode session id is NOT a SAIPEN seat identity, so it
// is never used as the actor. `SAIPEN_AGENT` is an optional explicit
// actor/provenance carrier, not authentication. The optional SAIPEN launcher
// can set it together with SAIPEN_PROJECT_ROOT / SAIPEN_PROJECT_LINEAGE. With
// no carrier the event omits actor and Core inherits canonical `STATE.agent`
// through its existing protocol snapshot before applying every safety check.
//
// Factory startup writes one bounded per-process diagnostic under the OS temp
// root. `SAIPEN_GUARD_STARTUP_PROBE` optionally captures the same JSON line for
// native smoke. Both identify the module bytes loaded into this process.

import { spawn, spawnSync } from "node:child_process";
import { createHash } from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const MAX_EVENT_BYTES = 256 * 1024;
const GUARD_TIMEOUT_MS = 15000;
const BUILD_ID = "T-1317-opencode-active-generation-20260913.1";
const MAX_DIAGNOSTIC_BYTES = 4096;

// Module-relative paths under the ES module runtime (no `__dirname`).
const MODULE_PATH = fileURLToPath(import.meta.url);
const MODULE_DIR = path.dirname(MODULE_PATH);
const sha256 = (bytes) => createHash("sha256").update(bytes).digest("hex");
// Capture at module evaluation, before a later injector can replace the file.
const LOADED_SHA256 = sha256(fs.readFileSync(MODULE_PATH));
const ACTIVE_DIAGNOSTIC = path.join(os.tmpdir(), `saipen-opencode-guard-active-${process.pid}.json`);
process.once("exit", () => {
  try { fs.unlinkSync(ACTIVE_DIAGNOSTIC); } catch (_error) { /* diagnostic only */ }
});

// Translation, not policy: these EXACT verified OpenCode built-in read-only
// tools cannot mutate the project, so the adapter never invokes the guard for
// them and a missing runtime cannot wedge diagnostics. The fast-path is
// identity-scoped: a namespaced/MCP/third-party tool whose last segment merely
// spells "read" is NOT read-only and goes to the guard (T-1317 P0-8).
const OPENCODE_READ_ONLY_TOOLS = new Set([
  "read",
  "glob",
  "grep",
  "list",
  "webfetch",
  "skill",
  "question",
]);

function isBuiltinReadOnly(toolName) {
  const name = String(toolName === undefined || toolName === null ? "" : toolName)
    .trim()
    .toLowerCase();
  if (!name || name.includes("__") || name.includes(".")) return false;
  return OPENCODE_READ_ONLY_TOOLS.has(name);
}

function skillRoot() {
  if (process.env.SAIPEN_SKILL_ROOT) return process.env.SAIPEN_SKILL_ROOT;
  // Installed at <config>/opencode/plugins/saipen-guard.js, and the skill copy
  // lives at <config>/opencode/skills/saipen -- one directory up, two down.
  const sibling = path.resolve(MODULE_DIR, "..", "skills", "saipen");
  if (fs.existsSync(path.join(sibling, "tools", "saipen.py"))) return sibling;
  return path.join(os.homedir(), ".config", "opencode", "skills", "saipen");
}

function findPython() {
  const candidates = [process.env.SAIPEN_PYTHON, "python3", "python"].filter(Boolean);
  for (const name of candidates) {
    const probe = spawnSync(name, ["-c", "import sys; print(sys.executable)"], {
      encoding: "utf8", timeout: 5000,
    });
    if (!probe.error && probe.status === 0 && probe.stdout.trim()) return probe.stdout.trim();
  }
  return null;
}

// Async child I/O avoids blocking the host event loop and does not depend on
// the runtime's spawnSync `input` option for the JSON event. Output is bounded.
function runGuard(pythonBin, saipenPy, payload, cwd) {
  return new Promise((resolve) => {
    let child;
    try {
      child = spawn(pythonBin, [saipenPy, "guard", "--event-json", "-", "--json"], {
        cwd, stdio: ["pipe", "pipe", "pipe"], windowsHide: true,
      });
    } catch (error) {
      resolve({ status: null, error });
      return;
    }
    let stdout = "";
    let stderr = "";
    let settled = false;
    let failure = null;
    const finish = (status, signal) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve({ status, signal, stdout, stderr, error: failure });
    };
    const collect = (chunk, stream) => {
      const next = stream + chunk.toString("utf8");
      if (Buffer.byteLength(next, "utf8") > MAX_EVENT_BYTES) {
        failure = new Error("guard output exceeded bound");
        failure.code = "OUTPUT_OVERFLOW";
        child.kill();
        return stream;
      }
      return next;
    };
    child.stdout.on("data", (chunk) => { stdout = collect(chunk, stdout); });
    child.stderr.on("data", (chunk) => { stderr = collect(chunk, stderr); });
    child.on("error", (error) => { failure = error; finish(null, null); });
    child.on("close", (status, signal) => finish(status, signal));
    child.stdin.on("error", () => { /* child exit is reported by close */ });
    const timer = setTimeout(() => {
      failure = new Error("guard timed out");
      failure.code = "ETIMEDOUT";
      child.kill();
      finish(null, null);
    }, GUARD_TIMEOUT_MS);
    try {
      child.stdin.end(payload);
    } catch (error) {
      failure = error;
      child.kill();
      finish(null, null);
    }
  });
}

// Pure decision core: map one guard subprocess result onto block/allow. A refusal,
// a crash and an unreachable guard all
// block; only exit 0 allows.
function decide(result) {
  if (!result || typeof result.status !== "number") {
    return {
      block: true,
      code: "GUARD_UNREACHABLE",
      diagnostic: String((result && result.error && result.error.code) ||
                         (result && result.signal) || "process exited without status"),
    };
  }
  let code = "GUARD_REFUSED";
  try {
    const parsed = JSON.parse(result.stdout || "");
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed) ||
        typeof parsed.admitted !== "boolean" || typeof parsed.code !== "string") {
      return { block: true, code: "GUARD_OUTPUT_INVALID" };
    }
    if (result.status === 0 && parsed.admitted === true) {
      return { block: false, code: parsed.code };
    }
    code = parsed.code;
  } catch (_error) {
    return { block: true, code: "GUARD_OUTPUT_INVALID" };
  }
  return { block: true, code };
}

function bindingActor() {
  const bound = process.env.SAIPEN_AGENT;
  return typeof bound === "string" && bound.trim() ? bound.trim() : null;
}

function buildEvent(context, toolName, toolInput, options) {
  const opts = options || {};
  const cwd = (context && (context.directory || context.worktree)) || process.cwd();
  const actor = opts.actor === undefined ? bindingActor() : opts.actor;
  const event = {
    event: "before_tool",
    host: "opencode",
    cwd,
    tool_name: String(toolName),
    tool_input: toolInput && typeof toolInput === "object" ? toolInput : {},
  };
  if (actor) event.actor = actor;
  if (opts.sessionId) event.session_id = String(opts.sessionId);
  return event;
}

function startupProbe(context, actor, skill, saipenPy) {
  const diagnostic = {
    build_id: BUILD_ID,
    module_sha256: LOADED_SHA256,
    module_path: MODULE_PATH,
    skill_root: skill,
    guard_runtime_path: saipenPy,
    pid: process.pid,
    factory_started_ms: Date.now(),
    cwd: (context && (context.directory || context.worktree)) || process.cwd(),
    actor,
  };
  const line = JSON.stringify(diagnostic);
  if (Buffer.byteLength(line, "utf8") > MAX_DIAGNOSTIC_BYTES) return;
  try {
    fs.writeFileSync(ACTIVE_DIAGNOSTIC, `${line}\n`, { mode: 0o600 });
  } catch (_error) {
    // Diagnostic failure never changes a tool verdict.
  }
  const target = process.env.SAIPEN_GUARD_STARTUP_PROBE;
  if (!target) return;
  try {
    fs.appendFileSync(target, `${line}\n`);
  } catch (_error) {
    // Probe failure is diagnostic only and never changes a verdict.
  }
}

const SaipenGuard = async (context) => {
  const skill = skillRoot();
  const saipenPy = path.join(skill, "tools", "saipen.py");
  const guardInstalled = fs.existsSync(saipenPy);
  const pythonBin = guardInstalled ? findPython() : null;
  // Capture an optional explicit override once per plugin factory instance so
  // sequential calls use stable provenance. This plain environment value is
  // not authenticated identity.
  const launchActor = bindingActor();
  startupProbe(context, launchActor, skill, saipenPy);

  return {
    "tool.execute.before": async (input, output) => {
      // A running host keeps its imported module after an on-disk overwrite.
      // Report that generation mismatch before any fast-path or guard call.
      let installedSha256;
      try { installedSha256 = sha256(fs.readFileSync(MODULE_PATH)); } catch (_error) {
        installedSha256 = "missing";
      }
      if (installedSha256 !== LOADED_SHA256) {
        throw new Error(
          `SAIPEN_GUARD_REFUSAL: PLUGIN_RESTART_REQUIRED: loaded build=${BUILD_ID} ` +
            `sha256=${LOADED_SHA256}; installed sha256=${installedSha256}; ` +
            `restart OpenCode; the host tool did not execute`,
        );
      }
      // Tool name comes from the real hook INPUT; arguments come from the
      // real mutable hook OUTPUT. No adapter-local alternative schema.
      const toolName =
        input && typeof input.tool === "string" && input.tool.trim() ? input.tool : "unknown";
      if (isBuiltinReadOnly(toolName)) return;

      const args = output ? output.args : undefined;
      if (!args || typeof args !== "object" || Array.isArray(args)) {
        // A hook payload we cannot read is not evidence of a safe call.
        throw new Error(
          `SAIPEN_GUARD_PAYLOAD_INVALID: tool.execute.before supplied no readable ` +
            `output.args for tool '${toolName}'; refusing rather than guessing the effect`,
        );
      }

      if (!guardInstalled) {
        throw new Error(
          `SAIPEN_GUARD_UNINSTALLED: no saipen guard at '${saipenPy}'; ` +
            `the saipen guard could not be consulted for tool '${toolName}' ` +
            `(consequential mutations fail closed)`,
        );
      }
      if (!pythonBin) {
        throw new Error(
          `SAIPEN_GUARD_UNREACHABLE: no Python runtime found; ` +
            `the saipen guard could not be consulted for tool '${toolName}' ` +
            `(consequential mutations fail closed)`,
        );
      }

      const payload = JSON.stringify(
        buildEvent(context, toolName, args, {
          actor: launchActor,
          sessionId: input && input.sessionID,
        }),
      );
      if (Buffer.byteLength(payload, "utf8") > MAX_EVENT_BYTES) {
        throw new Error("SAIPEN_GUARD_EVENT_OVERFLOW: tool input exceeds the bounded guard event size");
      }
      const result = await runGuard(
        pythonBin, saipenPy, payload,
        (context && (context.directory || context.worktree)) || process.cwd(),
      );
      const verdict = decide(result);
      if (verdict.block) {
        throw new Error(
          `SAIPEN_GUARD_REFUSAL: ${verdict.code}: the saipen guard refused tool '${toolName}'; ` +
            `the host tool did not execute` +
            (verdict.diagnostic ? ` (${verdict.diagnostic})` : ""),
        );
      }
    },
  };
};

export default SaipenGuard;
// OpenCode invokes every module export as a plugin factory. Helpers MUST
// remain private; exporting buildEvent installs an invalid event handler.
