// Read-only integration probe of the host's actual installed Markdown component.
// This does not claim a running desktop, physical input, or lifecycle PASS.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { readFileSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const evidence = dirname(fileURLToPath(import.meta.url));
const host = "V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_ZAICODE/zcode";
const requireHost = createRequire(pathToFileURL(resolve(host, "package.json")));
const React = requireHost("react");
const { renderToStaticMarkup } = requireHost("react-dom/server");
const engine = resolve(host, "node_modules/streamdown/dist/index.js");
const { Streamdown } = await import(pathToFileURL(engine));
const packageInfo = JSON.parse(readFileSync(resolve(host, "node_modules/streamdown/package.json"), "utf8"));
const current = readFileSync(resolve(evidence, "current-render-probe.txt"), "utf8").replaceAll("\r\n", "\n");
const before = current.replaceAll("  \n", "\n");
const fields = current.split("\n").filter((line) => line.trim()).length;

function observe(markdown) {
  const html = renderToStaticMarkup(React.createElement(Streamdown, { mode: "static" }, markdown));
  return { html, hardBreaks: (html.match(/<br\s*\/?\s*>/g) || []).length };
}

const oldResult = observe(before);
const newResult = observe(current);
writeFileSync(resolve(evidence, "markdown-host-observations.json"), JSON.stringify({
  scope: "Observed HTML before assertions; not a PASS certificate", fields,
  before: oldResult, after: newResult,
}, null, 2) + "\n");
assert.equal(oldResult.hardBreaks, 0, "Known-bad soft newline no longer reproduces the host boundary");
assert.equal(newResult.hardBreaks, fields - 1, "Actual host component lost a required field break");
for (const label of ["STATUS", "RESULT", "BLOCKER", "NEXT EXACT ACTION", "VALIDATION"]) {
  assert.ok(newResult.html.includes(label + ":"));
}
const report = {
  status: "PASS", scope: "Actual installed Streamdown component, server-rendered HTML; no desktop/input claim",
  streamdownVersion: packageInfo.version, reactVersion: React.version,
  engine, engineSha256: createHash("sha256").update(readFileSync(engine)).digest("hex"),
  fields, before: oldResult, after: newResult,
};
writeFileSync(resolve(evidence, "markdown-host-current.json"), JSON.stringify(report, null, 2) + "\n");
console.log(JSON.stringify({ status: report.status, streamdownVersion: packageInfo.version,
  fields, oldBreaks: oldResult.hardBreaks, newBreaks: newResult.hardBreaks, scope: report.scope }));
