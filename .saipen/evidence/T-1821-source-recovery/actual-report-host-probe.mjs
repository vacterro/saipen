// Observe the exact stored T-301 report with the installed Markdown component.
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
const stored = JSON.parse(readFileSync(resolve(evidence, "actual-t301-stored-report.json"), "utf8"));
const canonical = readFileSync(resolve(evidence, "current-render-probe.txt"), "utf8").replaceAll("\r\n", "\n");
function observe(text) {
  const html = renderToStaticMarkup(React.createElement(Streamdown, { mode: "static" }, text));
  return { html, breaks: (html.match(/<br\s*\/?\s*>/g) || []).length,
    paragraphs: (html.match(/<p>/g) || []).length };
}
const original = observe(stored.text);
const normalized = observe(stored.text.replaceAll("\n", "  \n"));
const correctedCanonical = observe(canonical);
assert.equal(original.breaks, 0);
assert.equal(original.paragraphs, 1);
assert.equal(normalized.breaks, 19);
assert.equal(correctedCanonical.breaks, 4);
const result = {
  observedUtc: new Date().toISOString(),
  scope: "Actual stored T-301 report and installed Streamdown SSR; no separate pre-transport stream, UI screenshot or physical input observation",
  storedPart: stored.part_id, storedSha256: stored.sha256,
  engine, engineSha256: createHash("sha256").update(readFileSync(engine)).digest("hex"),
  original, normalizedDiagnosticOnly: normalized, correctedCanonical,
  note: "The 20-field normalization is a diagnostic, not an authorized canonical output or a relaxed response budget.",
};
writeFileSync(resolve(evidence, "actual-report-host-result.json"), JSON.stringify(result, null, 2) + "\n");
console.log(JSON.stringify({ originalParagraphs: original.paragraphs, originalBreaks: original.breaks,
  normalizedDiagnosticBreaks: normalized.breaks, correctedCanonicalBreaks: correctedCanonical.breaks }));
