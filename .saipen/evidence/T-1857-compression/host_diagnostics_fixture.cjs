// Diagnostic-only scratch experiment. Never installs an issuer or changes a project.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const crypto = require("node:crypto");
const zcode = "V:/___VAC/__K/__CODE/_AI_STUFF_AGENTIC/_ZAICODE/zcode";
const out = __dirname;
const ts = require(path.join(zcode, "node_modules/typescript"));
const relative = "apps/zcode-cli/packages/bootstrap/src/zcode-protocol-v4/commands/continue-diagnostics.ts";
const sharedRelative = "packages/shared/src/zaicode-operator-ingress.ts";
const uiRelative = "packages/ui/src/v4/queueActionOutcome.ts";
const read = p => fs.readFileSync(path.join(zcode,p),"utf8").replace(/\r\n/g,"\n");
const original = read(relative);
const sharedSource = read(sharedRelative);
const uiSource = read(uiRelative);
const sha = s => crypto.createHash("sha256").update(s).digest("hex");
function load(source, imports = {}) {
  const result = ts.transpileModule(source, {
    compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022},
    reportDiagnostics:true
  });
  const errors = (result.diagnostics || []).filter(d => d.category === ts.DiagnosticCategory.Error);
  if(errors.length) throw Error("scratch transpilation failed");
  const module = {exports:{}};
  vm.runInNewContext(result.outputText, {
    module, exports:module.exports,
    require(name){if(Object.hasOwn(imports,name))return imports[name];throw Error("unexpected import "+name);}
  }, {timeout:3000});
  return module.exports;
}
const shared = load(sharedSource);
const ui = load(uiSource);
const start = original.indexOf("export function saipenRefusalCode(");
const body = original.indexOf("{", start);
const end = original.indexOf("\n}\n", body);
if(start < 0 || body < 0 || end < 0) throw Error("source boundary changed");
const replacement = [
  "  // 缺失可信入口是基础设施故障，不能被预算暂停误报成“再输入 cc”。",
  "  if (!answer.ingressDelivered) {",
  "    switch (answer.ingressState) {",
  "      case \"trusted-ingress-unavailable\":",
  "        return \"guard.recognizedContinueTrustedIngressUnavailable\";",
  "      case \"broker-unhealthy\":",
  "        return \"guard.recognizedContinueBrokerUnhealthy\";",
  "      case \"runtime-stale\":",
  "        return \"guard.recognizedContinueRuntimeStale\";",
  "    }",
  "  }",
  "  if (answer.safetyValveTripped || answer.remediation === \"SAFETY_VALVE_TRIPPED\") {",
  "    return \"guard.recognizedContinueSaipenValve\";",
  "  }",
  "  if (answer.operatorActionDue || answer.remediation === \"OPERATOR_DECISION\") {",
  "    return \"guard.recognizedContinueSaipenOperator\";",
  "  }",
  "  if (!answer.ingressDelivered && answer.ingressState === \"operator-authorization-required\") {",
  "    return \"guard.recognizedContinueOperatorAuthorizationRequired\";",
  "  }",
  "  return \"guard.recognizedContinueSaipenRefused\";"
].join("\n");
let candidate = original.slice(0,body+1)+"\n"+replacement+original.slice(end);
candidate = "import { describeZaicodeOperatorIngressState } from \"@zcode/shared/zaicode-operator-ingress\";\n"+candidate;
const describeStart = candidate.indexOf("export function describeSaipenRefusal");
const injectAt = candidate.indexOf("  if (answer.safetyValveTripped) {", describeStart);
if(injectAt < 0) throw Error("description boundary changed");
const description = [
  "  // 保留内核拒绝事实，同时先说明本次请求的可信传输缺口。",
  "  const ingress = !answer.ingressDelivered ? answer.ingressState : null;",
  "  if (ingress === \"trusted-ingress-unavailable\" || ingress === \"broker-unhealthy\" || ingress === \"runtime-stale\") {",
  "    return describeZaicodeOperatorIngressState(",
  "      ingress,",
  "      (answer.ingressDetail ? answer.ingressDetail + \" \" : \"\") +",
  "        \"SAIPEN refusal: \" + detail + codeHint,",
  "    );",
  "  }",
  ""
].join("\n");
candidate = candidate.slice(0,injectAt)+description+candidate.slice(injectAt);
const before = load(original);
const after = load(candidate, {"@zcode/shared/zaicode-operator-ingress":shared});
const infra = {
  "trusted-ingress-unavailable":"guard.recognizedContinueTrustedIngressUnavailable",
  "broker-unhealthy":"guard.recognizedContinueBrokerUnhealthy",
  "runtime-stale":"guard.recognizedContinueRuntimeStale"
};
function matrix(subject) {
  const results = [];
  for(const [state,expected] of Object.entries(infra)){
    for(const boundary of [{operatorActionDue:true},{safetyValveTripped:true}]){
      const input = {
        status:"REFUSED", code:"RECONCILE_REAUTH_REQUIRED",
        detail:"WAIT: safety valve reached -- run cc to continue",
        ingressDelivered:false, ingressState:state, ingressDetail:"native fixture: missing trust",
        ...boundary
      };
      const unchanged = JSON.stringify(input);
      const actual = subject.saipenRefusalCode(input);
      const message = subject.describeSaipenRefusal(input);
      results.push({state,boundary,expected,actual,
        pass:actual===expected && ui.saipenContinueOutcome(actual,message)===state &&
             !message.includes("only the operator can clear it") &&
             JSON.stringify(input)===unchanged});
    }
  }
  for(const [input,expected] of [
    [{operatorActionDue:true,ingressDelivered:true,ingressState:"runtime-stale"},
     "guard.recognizedContinueSaipenOperator"],
    [{safetyValveTripped:true,ingressDelivered:true},"guard.recognizedContinueSaipenValve"],
    [{operatorActionDue:true},"guard.recognizedContinueSaipenOperator"],
    [{},"guard.recognizedContinueSaipenRefused"]
  ]){
    results.push({case:"existing refusal preserved",expected,
                  actual:subject.saipenRefusalCode(input),
                  pass:subject.saipenRefusalCode(input)===expected});
  }
  return results;
}
const red = matrix(before);
const green = matrix(after);
if(red.filter(x=>!x.pass).length!==6)throw Error("red control did not reproduce six masked infrastructure cases");
if(green.some(x=>!x.pass))throw Error("candidate diagnostic control failed");
fs.writeFileSync(path.join(out,"ZAICODE-continue-diagnostics.candidate.ts"),candidate);
fs.writeFileSync(path.join(out,"ZAICODE-continue-diagnostics.original.ts"),original);
fs.writeFileSync(path.join(out,"ZAICODE-diagnostics-test.json"),JSON.stringify({
  scope:"Scratch VM executes original and candidate pure classifiers and actual existing shared/UI projections",
  native_issuer_installed:false, foreign_source_applied:false,
  typecheck_and_lint_of_foreign_repo:"not executed for an unapplied patch",
  node_version:process.version, typescript_version:ts.version,
  sources:{[relative]:sha(original),[sharedRelative]:sha(sharedSource),[uiRelative]:sha(uiSource)},
  red_failures:red.filter(x=>!x.pass).length, green_cases:green.length,
  red,green
},null,2)+"\n");
console.log(JSON.stringify({red_failures:6,green_cases:green.length,native_issuer_installed:false,
  foreign_source_applied:false,node:process.version,typescript:ts.version}));

