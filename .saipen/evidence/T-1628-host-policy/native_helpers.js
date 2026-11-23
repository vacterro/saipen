// The native policy reader mirrors host_authority_client.policy: a missing
// file uses the product default; unreadable bytes or an unknown mode use
// STRICT. Only the canonical generated table decides whether a gap degrades.
function admissionPolicy() {
  const policyPath = path.join(os.homedir(), ".saipen", "authority.json");
  const invalid = { mode: HOST_INTEGRATION_POLICY.strict_mode, source: "invalid" };
  let bytes;
  try { bytes = fs.readFileSync(policyPath); } catch (error) {
    return error && error.code === "ENOENT"
      ? { mode: HOST_INTEGRATION_POLICY.default_mode, source: "default" }
      : invalid;
  }
  try {
    const payload = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
    const spelling = payload && typeof payload.mode === "string"
      ? payload.mode.trim().toLowerCase().replaceAll(" ", "_") : "";
    const mode = HOST_INTEGRATION_POLICY.aliases[spelling];
    return typeof mode === "string" ? { mode, source: "operator" } : invalid;
  } catch (_error) { return invalid; }
}

function integrationDecision(adapterCode, bindingConflict = null) {
  const policy = admissionPolicy();
  const code = bindingConflict ? "BINDING_CONFLICT" : HOST_INTEGRATION_POLICY.gap_codes[adapterCode];
  const row = HOST_INTEGRATION_POLICY.failures[code];
  const actionRow = policy.source === "invalid"
    ? HOST_INTEGRATION_POLICY.failures.POLICY_INVALID : row;
  return {
    status: "UNVERIFIED",
    adapter_code: adapterCode,
    binding_conflict: bindingConflict,
    failure_code: code || "UNCLASSIFIED",
    decision: row ? row.decisions[policy.mode] : "BLOCK",
    policy: HOST_INTEGRATION_POLICY.labels[policy.mode],
    policy_source: policy.source,
    operator_action: actionRow ? actionRow.operator_action : "saipen host doctor",
  };
}

function integrationSystemMessage(gap) {
  return `SAIPEN_HOST_INTEGRATION ${JSON.stringify(gap)}\n` +
    (gap.decision === "ALLOW_DEGRADED"
      ? "Ordinary work may proceed under the selected host policy. SAIPEN could not " +
        "verify consequential tools; retain the UNVERIFIED status and claim no validation."
      : "The selected host policy blocks consequential tools while this integration " +
        "gap remains. Exact built-in diagnostic tools remain available.");
}

const TERMINAL_GUARD_CODES = new Set([
  "PROTECTED_CANONICAL_NAMESPACE", "PATH_ESCAPES_PROJECT", "TARGET_UNRESOLVED",
  "PROJECT_BINDING_INVALID", "PROJECT_LINEAGE_MISMATCH", "PROJECT_BINDING_AMBIGUOUS",
  "OWNERSHIP_CONFLICT",
]);

// A negative observation only, never a resolver or an admission. During an
// interpreter gap the host may still present two mechanically contradictory
// identities. Read only a direct canonical, bounded, ordinary identity file;
// unknown/changed/link bytes prove nothing and confer no project authority.
// The recognized canonical byte grammar comes from paths.identity_file_content.
function observedLineage(root) {
  if (typeof root !== "string" || !path.isAbsolute(root)) return null;
  const spec = HOST_INTEGRATION_POLICY.identity_observation;
  const memory = path.join(root, spec.memory_dir);
  const identity = path.join(memory, spec.identity_file);
  let descriptor;
  const same = (left, right) => left.dev === right.dev && left.ino === right.ino &&
    left.size === right.size && left.mtimeMs === right.mtimeMs;
  try {
    const directoryBefore = fs.lstatSync(memory);
    const before = fs.lstatSync(identity);
    if (!directoryBefore.isDirectory() || directoryBefore.isSymbolicLink() ||
        !before.isFile() || before.isSymbolicLink() || before.size > spec.max_bytes) return null;
    descriptor = fs.openSync(identity, "r");
    if (!same(before, fs.fstatSync(descriptor))) return null;
    const bytes = fs.readFileSync(descriptor);
    const after = fs.lstatSync(identity);
    const directoryAfter = fs.lstatSync(memory);
    if (bytes.length > spec.max_bytes || !same(before, after) ||
        !same(directoryBefore, directoryAfter) || after.isSymbolicLink() ||
        directoryAfter.isSymbolicLink() || bytes.subarray(0, 3).equals(Buffer.from([239, 187, 191]))) {
      return null;
    }
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    const match = new RegExp(spec.canonical_pattern).exec(text);
    return match ? match[1] : null;
  } catch (_error) { return null; }
  finally {
    if (descriptor !== undefined) {
      try { fs.closeSync(descriptor); } catch (_error) { /* observation only */ }
    }
  }
}

function observedBindingConflict(context) {
  const spec = HOST_INTEGRATION_POLICY.identity_observation;
  const root = process.env[spec.root_env];
  const expected = process.env[spec.lineage_env];
  const asserted = observedLineage(root);
  if (asserted && expected && asserted !== expected.trim()) return "PROJECT_LINEAGE_MISMATCH";
  for (const candidate of contextCandidates(context)) {
    const local = observedLineage(candidate);
    if (!local) continue;
    if (asserted && asserted !== local) return "PROJECT_BINDING_AMBIGUOUS";
    if (!root && expected && local !== expected.trim()) return "PROJECT_LINEAGE_MISMATCH";
    break;
  }
  return null;
}
