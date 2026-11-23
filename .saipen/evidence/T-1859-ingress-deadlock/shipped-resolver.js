// Extracted verbatim from resources/glm/zcode.cjs (the running 0.0.3 bundle).
// Only the minified identifiers' imports are supplied; the resolver body is untouched.
const { existsSync } = require("node:fs");
const { homedir } = require("node:os");
const { join } = require("node:path");
const aPn = { existsSync }, mZo = { homedir }, cPn = { join };
const wQa = join(".zcode","hooks","saipen-guard.py");
const kQa = "SAIPEN_INGRESS_HOOK";
function CQa(e=process.env){let t=e[kQa]?.trim();if(t)return(0,aPn.existsSync)(t)?t:null;let n=e.ZAICODE_HOME?.trim()||(0,mZo.homedir)(),o=(0,cPn.join)(n,wQa);return(0,aPn.existsSync)(o)?o:null}
module.exports = CQa;
