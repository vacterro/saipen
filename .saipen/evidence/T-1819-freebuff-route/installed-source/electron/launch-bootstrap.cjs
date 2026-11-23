'use strict'

// Electron main's half of the orchestrator's launch bootstrap (src/server/launch-bootstrap.ts is
// the other). The launch id and the bridge bearer tokens reach the orchestrator as ONE JSON line on
// its stdin, never in its environment: `ps eww <pid>` (macOS) and `/proc/<pid>/environ` (Linux)
// show a process's starting environment to any other process of the same user, and published
// bridges read FREEBUFF_LAUNCH_ID from there to drive the local API from outside the app.

/**
 * Environment keys that must never reach the orchestrator from this shell. Electron no longer sets
 * them; they are also stripped from whatever environment the shell itself inherited.
 */
const LAUNCH_SECRET_ENV_KEYS = Object.freeze([
  'FREEBUFF_LAUNCH_ID',
  'FREEBUFF_CDP_BRIDGE_TOKEN',
  'FREEBUFF_MCP_CONSENT_TOKEN',
])

/** The single stdin line: shell-lifetime token plus this launch's secrets. No newline inside. */
function launchBootstrapLine({ shellLifetimeToken, launchId, cdpBridgeToken, mcpConsentToken }) {
  const line = { shellLifetimeToken }
  if (launchId) line.launchId = launchId
  if (cdpBridgeToken) line.cdpBridgeToken = cdpBridgeToken
  if (mcpConsentToken) line.mcpConsentToken = mcpConsentToken
  return JSON.stringify(line)
}

/** `line` with every occurrence of the launch id replaced, for echoing the child's stdout. */
function redactLaunchId(line, launchId) {
  if (!launchId || !line.includes(launchId)) return line
  return line.split(launchId).join('[redacted]')
}

module.exports = { LAUNCH_SECRET_ENV_KEYS, launchBootstrapLine, redactLaunchId }
