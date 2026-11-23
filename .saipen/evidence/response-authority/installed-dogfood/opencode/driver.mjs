
import fs from "node:fs";
import { pathToFileURL } from "node:url";

const [pluginPath, requestPath] = process.argv.slice(2);
const request = JSON.parse(fs.readFileSync(requestPath, "utf8"));
const module = await import(pathToFileURL(pluginPath).href);
const factory = module.SaipenGuard || module.default;
const results = [];

for (const item of request.cases) {
  const saved = {};
  for (const [key, value] of Object.entries(item.env || {})) {
    saved[key] = process.env[key];
    if (value === null) delete process.env[key];
    else process.env[key] = String(value);
  }
  const record = { id: item.id, outcome: "allowed", message: "", hooks: [], system: [] };
  record.exports = Object.keys(module);
  try {
    const context = {
      worktree: item.context_worktree || item.project,
      directory: item.context_directory || item.project,
    };
    const plugin = await factory(context);
    record.hooks = Object.keys(plugin || {});
    const systemHook = plugin ? plugin["experimental.chat.system.transform"] : undefined;
    if (typeof systemHook === "function") {
      const systemOutput = { system: [] };
      await systemHook({ sessionID: item.input && item.input.sessionID }, systemOutput);
      record.system = systemOutput.system;
    }
    // T-1568: `text_complete` drives the FINAL-RESPONSE hook instead of the
    // tool gate, on the same real module and the same fixtures. Absent, the
    // case keeps its original tool-gate meaning.
    if (typeof item.text_complete === "string") {
      const sessionID = item.session_id || (item.input && item.input.sessionID);
      if (item.user_request && typeof plugin["chat.message"] === "function") {
        await plugin["chat.message"]({ sessionID, messageID: item.id },
          { parts: [{ type: "text", text: item.user_request }] });
      }
      if (item.operational_command) {
        await plugin["tool.execute.before"]({ tool: "bash", sessionID },
          { args: { command: item.operational_command } });
      }
      const textHook = plugin ? plugin["experimental.text.complete"] : undefined;
      if (typeof textHook !== "function") {
        record.outcome = "no_hook";
        record.message = "experimental.text.complete is not callable";
      } else {
        const textOutput = { text: item.text_complete };
        await textHook({ sessionID }, textOutput);
        record.delivered = textOutput.text;
      }
    } else {
      const hook = plugin ? plugin["tool.execute.before"] : undefined;
      if (typeof hook !== "function") {
        record.outcome = "no_hook";
        record.message = "tool.execute.before is not callable";
      } else {
        await hook(item.input, item.output);
      }
    }
    if (record.outcome === "allowed" && item.simulate_effect) {
      fs.writeFileSync(item.simulate_effect.path, item.simulate_effect.contents);
    }
  } catch (error) {
    record.outcome = "blocked";
    record.message = String((error && error.message) || error);
  }
  for (const [key, value] of Object.entries(saved)) {
    if (value === undefined) delete process.env[key];
    else process.env[key] = value;
  }
  results.push(record);
}
process.stdout.write(JSON.stringify(results));
