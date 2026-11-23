// Executed control: the resolver body extracted verbatim from the RUNNING
// bundle (resources/glm/zcode.cjs, build 2026-10-23T07:09Z), called with the
// environment the live host actually has.
//
// RED  = today, no SAIPEN_INGRESS_HOOK override.
// GREEN = same resolver, same ZAICODE_HOME, override present.
const { existsSync } = require("node:fs");

const resolve = require("./shipped-resolver.js");

const ZAICODE_HOME = String.raw`V:\___VAC\__K\__CODE\_AI_STUFF_AGENTIC\_ZAICODE\.zaicode\home`;
const HOOK = String.raw`C:\Users\vac34\.zcode\hooks\saipen-guard.py`;

const without = resolve({ ZAICODE_HOME });
const withVar = resolve({ ZAICODE_HOME, SAIPEN_INGRESS_HOOK: HOOK });

console.log("ZAICODE_HOME           :", ZAICODE_HOME);
console.log("canonical hook exists  :", existsSync(HOOK));
console.log("");
console.log("RED   (no override)     ->", JSON.stringify(without));
console.log("GREEN (with override)   ->", JSON.stringify(withVar));
console.log("");
const expectedRed = without === null;
const expectedGreen = withVar === HOOK;
console.log("RED reproduces the report :", expectedRed ? "PASS" : "FAIL");
console.log("GREEN resolves the hook   :", expectedGreen ? "PASS" : "FAIL");
console.log("");
console.log(
  expectedRed && expectedGreen
    ? "CONTROL HOLDS: the shipped resolver cannot find the hook, and the documented "
      + "override makes it find the canonical one."
    : "CONTROL BROKEN: the explanation above is wrong."
);
