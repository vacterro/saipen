/**
 * Freebuff — Electron main process (the shell side of the
 * Electron-shell + Bun-orchestrator split described in the README).
 *
 * Electron's main process runs Node, not Bun. To honor "Bun main process"
 * (reuse sdk/ + agent-runtime, which export Bun-targeted TS) the shell spawns
 * the Bun orchestrator as a child process and talks to it over local HTTP/SSE
 * on 127.0.0.1. The renderer is the existing self-contained UI the Bun server
 * serves, so there is no separate renderer build step.
 *
 * Two run modes, see resolveOrchestrator():
 *   - dev: spawn a system `bun` on the TS source (src/server/main.ts).
 *   - packaged: spawn the Bun binary shipped in app resources on the pre-bundled
 *     orchestrator.js (scripts/fetch-bun.ts + scripts/build-orchestrator.ts,
 *     wired into the app via the electron-builder extraResources config). The
 *     user needs no system Bun.
 *
 *   bun --cwd freebuff-desktop run app        # launch from source (dev)
 */

const { app, BrowserWindow, Menu, nativeTheme, shell, dialog, ipcMain, webContents, clipboard, safeStorage, net: electronNet } = require('electron')
const { execFileSync, spawn } = require('node:child_process')
const { randomUUID } = require('node:crypto')
const fs = require('node:fs')
const path = require('node:path')
const http = require('node:http')
const net = require('node:net')
const updater = require('./updater.cjs')
const {
  binaryIdentity,
  bunLaunchArgs,
  bunRuntimeCandidates,
  chooseBunRuntime,
  createRuntimeMemory,
  probeBunRuns,
  retryOnBaseline,
} = require('./bun-runtime.cjs')
const { createCdpBridge } = require('./cdp-bridge.cjs')
const { createMcpConsentBridge } = require('./mcp-consent-bridge.cjs')
const { withBoundedBoot } = require('./boot-step.cjs')
const { loadAppURL } = require('./app-load.cjs')
const { createSecretStore } = require('./mcp-secret-store.cjs')
const { createMemorySafeStorage } = require('./memory-safe-storage.cjs')
const { createConsentWindow } = require('./consent-window.cjs')
const { createShellLifetimeServer } = require('./shell-lifetime.cjs')
const { surfaceWindow } = require('./surface-window.cjs')
const { installFileNavigation } = require('./file-navigation.cjs')
const { installNeedsYouNotifications } = require('./needs-you-notification.cjs')
const { clearWindowAttention, requestWindowAttention } = require('./window-attention.cjs')
const { resolveRevealTarget } = require('./reveal-path.cjs')
const { keepTransientFile, saveClipboardImage } = require('./kept-attachments.cjs')
const { readImage } = require('./attachment-preview.cjs')
const { downloadThreadFile } = require('./file-download.cjs')
const { detectOpenTargets, launchArgs, launchCwd, resolveOpenTarget } = require('./open-in.cjs')
const {
  createAdContextReader,
  createResumeClock,
  installMethodOf,
  installedEditorDetector,
} = require('./ad-context.cjs')
const { createBusySignal } = require('./busy.cjs')
const { splashHtml } = require('./splash.cjs')
const { describeFailure } = require('./orchestrator-failure.cjs')
const {
  crashRecord,
  readAnalyticsId,
  shipCrashRecord,
} = require('./orchestrator-crash-telemetry.cjs')
const { createBootTelemetry } = require('./boot-telemetry.cjs')
const { createDesktopAcquisition } = require('./desktop-acquisition.cjs')
const { fixPath } = require('./shell-path.cjs')
const { detectSigning } = require('./signing.cjs')
const { appMenuTemplate, createMenuRouter, updateMenuShortcuts } = require('./app-menu.cjs')
const { createInterfaceZoom } = require('./interface-zoom.cjs')
const { attachmentDialogProperties } = require('./attachment-dialog.cjs')
const { announceUpdateRestart, postMutation, setLaunchCookie } = require('./orchestrator-request.cjs')
const { LAUNCH_SECRET_ENV_KEYS, launchBootstrapLine, redactLaunchId } = require('./launch-bootstrap.cjs')
const { watchRenderer } = require('./renderer-health.cjs')
const { createWindowLoads } = require('./window-loads.cjs')
const { apiTokenReply, isTrustedAppSender } = require('./ipc-sender.cjs')
const { attachTextContextMenu, installTextEditing } = require('./text-context-menu.cjs')
const { FREEBUFF_DISCORD_CLIENT_ID, createDiscordPresence, discordIpcPaths } = require('./discord-presence.cjs')
const { resolveStatePath, sourceUserDataDir } = require('./desktop-profile.cjs')
const rendererHealth = new WeakMap()
// Why each window's page loaded; the renderer reports it when a boot was not a plain launch.
const windowLoads = createWindowLoads()
const {
  planRelaunch,
  resolveRelaunchExecPath,
  describeSandboxFailure,
  NO_SANDBOX,
} = require('./linux-launch.cjs')

// Keep the last ~3000 chars of orchestrator stderr for the failure dialog.
const STDERR_TAIL_CHARS = 3000
function appendTail(tail, text) {
  return (tail + text).slice(-STDERR_TAIL_CHARS)
}

// `close` is what builds a startup diagnostic, because it fires only once stdio has drained into
// the log and the excerpt. But it waits for every pipe to be closed, and a grandchild that
// inherited them can hold one open for as long as it likes — while `exit` has already told the
// startup timer the process is gone, so the timer declines to report anything. That combination
// settles nothing: no dialog, no quit, a window on the splash forever, which is the exact
// undiagnosable shape boot-step.cjs exists to prevent elsewhere. So an exit whose `close` does not
// follow within this long gets reported from the exit instead.
const CLOSE_AFTER_EXIT_GRACE_MS = 3000


// Launched from Finder/Dock, launchd gives us a minimal PATH with no Homebrew and
// no ~/.bun/bin, and every child inherits it — so the orchestrator and its agent
// harnesses can't find `bun`, `codex`, or anything else the user installed. Repair
// PATH from the login shell HERE, at module load, before a single child is spawned.
//
// Runs before `app` is ready (so no log dir yet): buffer the one-line diagnostic
// and flush it into the orchestrator log once createStderrCapture establishes the
// dir. This is the SECOND silent "Codex not found only in the packaged build" PATH
// bug — the breadcrumb makes any third one a log read, not a repro hunt.
let pathRepairDiag = ''
fixPath({
  log: (line) => {
    pathRepairDiag = line
    console.error(line)
  },
})

// In-app update checker (see updater.cjs). Wired up once boot succeeds; the
// "Check for Updates…" menu item calls through this handle. Null until boot.
/** @type {{ checkNow: (mode?: 'launch' | 'session' | 'interactive' | 'settings') => Promise<unknown>, restartingForUpdate: () => boolean } | null} */
let updateChecker = null

function checkForUpdatesInteractive() {
  void updateChecker?.checkNow('interactive')
}

// Is the app in the middle of something? Answered by the renderer's `update:busy`
// heartbeat, which the updater listens for; both it and the quit guard read this one
// instance rather than each keeping its own idea of what the app is doing.
const busySignal = createBusySignal()

const PKG_DIR = path.join(__dirname, '..')
// The packaged app's Info.plist / .ico / .png bundle the right icon, but in dev
// the OS would otherwise show Electron's default icon. Point at our PNG so dev
// looks the same as packaged. The file is generated by scripts/build-icon.ts.
const APP_ICON_PATH = path.join(PKG_DIR, 'build', 'icon.png')

/** @type {import('node:child_process').ChildProcess | null} */
let serverProc = null
/** @type {Promise<void> | null} */
let serverStopPromise = null
// Port the orchestrator listens on (set in boot); crash restarts reuse it so
// appUrl/appOrigin stay valid and the renderer just reconnects.
/** @type {number | null} */
let serverPort = null
/**
 * The launch secret this Electron process minted for the current orchestrator.
 *
 * It is the orchestrator's proof that an `/api/` request — any of them, reads,
 * the event stream and the terminal WebSocket included — came from OUR
 * renderer and not from something else on the machine: another process or
 * account, or a sponsored run's shell, for which `127.0.0.1:<port>` is one curl
 * away. The Origin checks cannot answer that question: they admit a request
 * with no `Origin` header by design, and a curl has none.
 *
 * It reaches the renderer over IPC (for the header its fetches carry) and as an
 * HttpOnly cookie planted in the app's own session (for the EventSource and
 * WebSocket, which cannot set headers; see `setLaunchCookie`), and NEVER
 * through argv, a file, or a response body. Argv is readable with `ps` by anything running as the same
 * user, which on macOS includes a sandboxed run (the seatbelt profile allows
 * `sysctl-read`, which is how `ps` enumerates). IPC is reachable only by a
 * window this process created.
 */
let apiLaunchToken = null
// Crash-restart budget: up to 3 respawns; refreshed after 60s of uptime.
let restartAttempts = 0
let lastSpawnAt = 0
// loopback cdp bridge (cdp-bridge.cjs): the only channel through which the orchestrator can
// drive a preview <webview>, since webContents.debugger is a main-process api
let cdpBridge = null
// the orchestrator cannot be the authority for running a third-party program: /api/ authenticates the
// renderer, which displays untrusted output, not the user's intent. It asks here, and a human answers.
let mcpConsentBridge = null

// The orchestrator owns one authenticated client connection. A shell crash closes the server side,
// which is a reliable parent-death signal on Windows without inherited anonymous-pipe handles.
let shellLifetime = null
/** @type {BrowserWindow | null} */
let mainWindow = null
// How this copy is signed (signing.cjs) — probed once in boot(), ships to the
// orchestrator via env so it rides the launch analytics event.
/** @type {{ state: string, team?: string } | null} */
let signing = null
let shuttingDown = false
let quitting = false

/**
 * Whether windows are closing because the app is going away: a quit, or the
 * updater's install restart. The second matters because Electron closes every
 * window BEFORE emitting `before-quit` when `quitAndInstall` runs, so `quitting`
 * is still false then; a close guard that cancelled those closes left the
 * install stuck on "Installing Freebuff <version>" (2026-10-12).
 */
function appIsLeaving() {
  return quitting || !!updateChecker?.restartingForUpdate()
}
// The single trusted origin the renderer is allowed to live at (set in boot()
// once the orchestrator port is known). Navigation / new-window requests to any
// other origin are denied and handed to the system browser, so the preload
// bridge never rides along to an untrusted document.
/** @type {string | null} */
let appOrigin = null
// The URL the renderer loads (orchestrator origin, or the Vite dev server). Held
// at module scope so a macOS dock re-activate can reattach to the live
// orchestrator instead of spawning a second one.
/** @type {string | null} */
let appUrl = null

const SHELL_THEMES = {
  dark: {
    background: '#292b2a',
    overlay: '#292b2a',
    overlaySymbol: '#dedfdd',
    // the renderer's --surface-2 / --brand-dim: the splash bar and the one the app holds after it
    // are the same bar, and a colour change between them would show as a flicker
    splashTrack: '#282a29',
    splashBar: '#9db58b',
  },
  light: {
    background: '#e3e7e4',
    overlay: '#e3e7e4',
    overlaySymbol: '#232b26',
    splashTrack: '#e9ede8',
    splashBar: '#5e774e',
  },
}
// The user's PREFERENCE — 'dark', 'light', or 'system' — not the colour on screen. Anything that
// paints goes through resolvedTheme(), because 'system' has no colour of its own.
let themePref = 'dark'
let titleBarColors = null

function shellColors() {
  const colors = SHELL_THEMES[resolvedTheme()]
  return titleBarColors
    ? { ...colors, overlay: titleBarColors.color, overlaySymbol: titleBarColors.symbolColor }
    : colors
}

// What to actually paint. Under 'system' the answer is Electron's, which tracks the OS and moves on
// its own when macOS switches appearance at sunset. Only called after app-ready, where
// nativeTheme is live and themeSource has been pointed at the preference.
function resolvedTheme() {
  if (themePref !== 'system') return themePref
  return nativeTheme.shouldUseDarkColors ? 'dark' : 'light'
}

// Override package.json's "@codebuff/freebuff-desktop" name — that string leaks
// into the macOS app menu, About panel, and Windows taskbar/AppUserModelId.
app.setName('Freebuff')
app.setAppUserModelId('com.freebuff.desktop')
if (process.platform === 'darwin' && app.setAboutPanelOptions) {
  app.setAboutPanelOptions({ name: 'Freebuff' })
}

// The profile, before the first userData read below: a source build gets its own state file and its own
// Electron profile beside it, so it runs alongside the installed app instead of losing the
// single-instance lock to it (desktop-profile.cjs). An explicit --user-data-dir (drive, dev:staging,
// the packaged e2e) is Electron's to apply and is left alone. Logs follow userData: macOS keys them on
// the app NAME, so without this both apps would recreate one orchestrator-stderr.log at each launch.
const profile = resolveStatePath({ override: process.env.FREEBUFF_DESKTOP_STATE_PATH, packaged: app.isPackaged })
if (profile.refused) {
  console.warn(`[profile] ${profile.refused} is the installed app's profile; this source build uses ${profile.statePath}`)
}
// The shell's own /api/logs rows go through Chromium's network stack: unlike Node's fetch, it uses the
// OS's certificates and proxy settings, so the rows still arrive from a machine whose antivirus or
// corporate proxy intercepts HTTPS.
const shipShellRecord = (record) => shipCrashRecord(electronNet.fetch, record)
// Startup telemetry, made before anything can create the state file it checks (boot-telemetry.cjs).
const bootTelemetry = createBootTelemetry({
  isPackaged: app.isPackaged,
  statePath: profile.statePath,
  version: app.getVersion(),
  resourcesPath: process.resourcesPath,
  bootCompleted: () => bootCompleted,
  ship: shipShellRecord,
})
const desktopAcquisition = createDesktopAcquisition({
  isPackaged: app.isPackaged,
  statePath: profile.statePath,
  fetchImpl: electronNet.fetch.bind(electronNet),
})
app.on('will-quit', () => desktopAcquisition.dispose())
if (!app.isPackaged) {
  if (!app.commandLine.hasSwitch('user-data-dir')) app.setPath('userData', sourceUserDataDir(profile.statePath))
  app.setAppLogsPath(path.join(app.getPath('userData'), 'logs'))
}

const themeFile = path.join(app.getPath('userData'), 'theme')
const interfaceZoom = createInterfaceZoom({
  file: path.join(app.getPath('userData'), 'interface-zoom'), fs, isAppUrl,
})
try {
  const saved = fs.readFileSync(themeFile, 'utf8').trim()
  if (saved === 'light' || saved === 'system') themePref = saved
} catch {}

// Discord Rich Presence (discord-presence.cjs). The env override is for trying an application
// before its id is committed; with neither, the feature is absent rather than off.
const discordClientId = process.env.FREEBUFF_DISCORD_CLIENT_ID?.trim() || FREEBUFF_DISCORD_CLIENT_ID
// On unless the user turned it off: main owns this preference, not the renderer, because the
// renderer's origin (and so its localStorage) changes with the loopback port on every launch.
const discordPrefFile = path.join(app.getPath('userData'), 'discord-presence')
let discordEnabled = true
try {
  if (fs.readFileSync(discordPrefFile, 'utf8').trim() === 'off') discordEnabled = false
} catch {}
/** @type {ReturnType<typeof createDiscordPresence> | null} */
let discordPresence = null

// The Bun child and native reveal action must agree even when a diagnostic launch supplies a
// relative override and the packaged orchestrator runs from a different cwd.
function desktopStatePath() {
  return profile.statePath
}

// Desktop's session token, encrypted with safeStorage, one entry per API host. Beside state.json
// rather than in userData so it follows FREEBUFF_DESKTOP_STATE_PATH: a test or throwaway profile
// never reads the real user's login, and the real profile never loses it to one. The orchestrator
// reads the same path (`authSecretsPath` in src/server/repo/auth-store.ts) — keep them equal.
function authSecretsPath() {
  return `${desktopStatePath()}.auth-secrets.json`
}

// The OS keychain, except in an unpackaged dev launch that asks for a per-process in-memory key
// (`bun run drive` does): a dev Electron binary is not the signed app, so on macOS every access to
// the shared "Freebuff Safe Storage" item raises a keychain prompt. Never honoured when packaged.
function authSafeStorage() {
  return !app.isPackaged && process.env.FREEBUFF_DESKTOP_SAFE_STORAGE === 'memory'
    ? createMemorySafeStorage()
    : safeStorage
}

// Chromium sandbox preflight (linux-launch.cjs). No-op off Linux; on Linux it
// decides whether this process can sandbox at all. Acted on at the bottom of
// this file, next to the single-instance lock, because the remedy is to re-exec.
const linuxLaunch = planRelaunch()
if (linuxLaunch.diagnostic) console.error(linuxLaunch.diagnostic)
// Set once the first window has loaded: after that a subprocess launch failure
// is a mid-session fault, not a failed startup (see the child-process-gone
// handler, which only speaks up during the bootstrap window).
let bootCompleted = false

function resolveOrchestrator() {
  if (app.isPackaged) {
    const res = process.resourcesPath
    const orchDir = path.join(res, 'orchestrator')
    return {
      // FREEBUFF_BUN_PATH overrides the bundled binary in tests and diagnostics.
      bun: process.env.FREEBUFF_BUN_PATH || packagedBunRuntime().bun,
      args: bunLaunchArgs(path.join(orchDir, 'orchestrator.js')),
      cwd: orchDir,
      uiDir: path.join(orchDir, 'ui'),
      wasmDir: path.join(orchDir, 'wasm'),
      packaged: true,
    }
  }
  // No --watch by default. Bun's watch mode re-executes the entry IN THE SAME PROCESS and
  // delivers no signal on the way, which defeats three things at once: the SIGTERM handler in
  // main.ts never runs, so beginShutdown() cannot stop the harness children cleanly; the orphan reaper
  // skips every harness CLI the previous incarnation spawned, because they carry
  // FREEBUFF_ORCHESTRATOR_PID equal to the pid still running (orphan-reaper.ts reads them as our
  // own live children), so each reload leaks a claude/codex process; and the close handler below
  // never fires, so Electron's crash-restart budget cannot see any of it. boot() then auto-resumes
  // the interrupted turn while the leaked CLI is still editing the same files.
  // Restarting the app is the recovery precisely because a new pid makes the orphans visible again.
  // FREEBUFF_DEV_WATCH=1 opts back in for sessions that only touch pure modules with no turn running.
  const watch = process.env.FREEBUFF_DEV_WATCH === '1' ? ['--watch', '--no-clear-screen'] : []
  return {
    bun: process.env.FREEBUFF_BUN_PATH || 'bun',
    args: bunLaunchArgs(path.join(PKG_DIR, 'src', 'server', 'main.ts'), watch),
    cwd: PKG_DIR,
    // In dev the built dist-ui/ may exist (after `ui:build`); the server falls
    // back to it. When FREEBUFF_DEV_UI is set, the Vite dev server serves the UI.
    uiDir: undefined,
    wasmDir: undefined,
    packaged: false,
  }
}

// Poll the orchestrator's /healthz until it answers (or we give up). Using the
// trivial liveness probe instead of /api/state keeps readiness from depending on
// the full engine snapshot serializing.
function waitForServer(port, launchId, pid, timeoutMs = 30000, shouldStop = () => false) {
  const start = Date.now()
  return new Promise((resolve, reject) => {
    const retry = () => {
      if (shouldStop()) {
        reject(new Error('orchestrator stopped before becoming ready'))
      } else if (Date.now() - start >= timeoutMs) {
        reject(new Error(`orchestrator did not come up within ${timeoutMs}ms`))
      } else {
        setTimeout(attempt, 300)
      }
    }
    const attempt = () => {
      if (shouldStop() || Date.now() - start >= timeoutMs) {
        retry()
        return
      }
      let attemptSettled = false
      const retryAttempt = () => {
        if (attemptSettled) return
        attemptSettled = true
        retry()
      }
      const req = http.get(
        {
          host: '127.0.0.1',
          port,
          path: '/healthz',
          timeout: 1500,
          headers: { 'x-freebuff-launch-id': launchId },
        },
        (res) => {
          let body = ''
          res.setEncoding('utf8')
          res.on('data', (chunk) => {
            body += chunk
          })
          res.on('end', () => {
            if (res.statusCode !== 200) {
              retryAttempt()
              return
            }
            try {
              const health = JSON.parse(body)
              if (
                health.ok === true &&
                health.launchId === launchId &&
                health.pid === pid &&
                health.port === port
              ) {
                attemptSettled = true
                resolve()
                return
              }
            } catch {}
            retryAttempt()
          })
        },
      )
      req.on('error', retryAttempt)
      req.on('timeout', () => req.destroy())
    }
    attempt()
  })
}

function waitForProcessClose(proc, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const timeout = setTimeout(() => resolve(false), timeoutMs)
    proc.once('close', () => {
      clearTimeout(timeout)
      resolve(true)
    })
  })
}

function createStderrCapture(bun, args) {
  let logPath = null
  let stderrTail = ''
  let writable = true
  try {
    const logDir = app.getPath('logs')
    fs.mkdirSync(logDir, { recursive: true })
    logPath = path.join(logDir, 'orchestrator-stderr.log')
    const header =
      `[${new Date().toISOString()}] Starting Freebuff orchestrator\n` +
      `Runtime: ${bun}\nArguments: ${args.join(' ')}\n` +
      (pathRepairDiag ? `${pathRepairDiag}\n` : '') +
      (linuxLaunch.diagnostic ? `${linuxLaunch.diagnostic}\n` : '') +
      `\n`
    if (restartAttempts > 0) {
      // Crash restart: append with a marker so the crashed instance's log survives.
      fs.appendFileSync(logPath, `\n[restart ${restartAttempts}] ${header}`)
    } else {
      // Recreate the file so a permissive mode from an older app version cannot
      // survive the mode passed to writeFileSync (which only applies on create).
      fs.rmSync(logPath, { force: true })
      fs.writeFileSync(logPath, header, { mode: 0o600 })
    }
  } catch (err) {
    writable = false
    logPath = null
    console.error('[orchestrator] could not create stderr log:', err?.message ?? err)
  }

  return {
    get logPath() {
      return logPath
    },
    get stderrTail() {
      return stderrTail
    },
    write(chunk) {
      const text = Buffer.isBuffer(chunk) ? chunk.toString('utf8') : String(chunk)
      stderrTail = appendTail(stderrTail, text)
      if (!writable || !logPath) return
      try {
        fs.appendFileSync(logPath, text)
      } catch (err) {
        writable = false
        console.error('[orchestrator] could not append to stderr log:', err?.message ?? err)
      }
    },
  }
}

/** A modal box, tolerating a parent that has already gone away — an unparented dialog is
 *  still better than none, and both callers run at moments when a window may be closing. */
function askSync(parent, options) {
  const usable = parent && !parent.isDestroyed() ? parent : null
  return usable ? dialog.showMessageBoxSync(usable, options) : dialog.showMessageBoxSync(options)
}

// The packaged Bun binary this launch runs the orchestrator on, chosen once (bun-runtime.cjs).
// Reset only by switchToBaselineRuntime, which is how the second choice differs from the first.
let bunRuntimeChoice = null

function bunRuntimeMemory() {
  return createRuntimeMemory({ file: path.join(app.getPath('userData'), 'bun-runtime.json'), fs })
}

function packagedBunRuntime() {
  if (bunRuntimeChoice) return bunRuntimeChoice
  const candidates = bunRuntimeCandidates(process.resourcesPath, process.platform, fs.existsSync)
  const identity = candidates.standard ? binaryIdentity(candidates.standard, fs.statSync) : null
  const choice = chooseBunRuntime({
    candidates,
    probe: (exe) => probeBunRuns(exe, execFileSync),
    memory: bunRuntimeMemory(),
    identity,
  })
  if (!choice.bun) {
    // neither binary is there: keep the standard path so the spawn failure names what is missing
    const exe = process.platform === 'win32' ? '.exe' : ''
    choice.bun = path.join(process.resourcesPath, 'bun', `bun${exe}`)
  }
  bunRuntimeChoice = {
    ...choice,
    identity,
    baselineBundled: Boolean(candidates.standard && candidates.baseline),
  }
  console.error(`[orchestrator] bun runtime: ${choice.runtimeFlavor} (${choice.reason})`)
  return bunRuntimeChoice
}

/**
 * The standard runtime died before the app was up and the baseline one is bundled: remember
 * that verdict for this bun.exe and make the next startOrchestrator use the baseline. Returns
 * whether there is anything to retry with. The verdict is only kept if the retry works
 * (see boot()), so a crash that has nothing to do with the CPU does not pin the slower binary.
 */
function switchToBaselineRuntime(failure) {
  if (!app.isPackaged || process.env.FREEBUFF_BUN_PATH) return false
  const choice = bunRuntimeChoice
  if (!retryOnBaseline(failure, choice)) return false
  if (choice.identity) bunRuntimeMemory().write(choice.identity, 'baseline')
  bunRuntimeChoice = null
  console.error('[orchestrator] the standard runtime crashed before ready; retrying on the baseline runtime')
  return true
}

/**
 * Which of the two Windows x64 installers this is. The update channel follows the installer,
 * not the binary chosen at launch: the standard package carries both binaries now.
 */
function releaseFlavor() {
  return app.isPackaged ? packagedBunRuntime().installerFlavor : 'standard'
}

/**
 * Post a runtime crash's signature from the shell, because the process that normally ships
 * diagnostics is the one that died. Called once per exit diagnostic: on the close that produced
 * it (so a crash the restart budget recovers from is still counted) and again, idempotently, by
 * the fatal dialog, which awaits it so the row is out before Quit. Bounded and best-effort.
 */
function reportBunCrash(failure) {
  if (failure.crashReport) return failure.crashReport
  const { bunCrash } = describeFailure(failure)
  if (!bunCrash) return Promise.resolve(false)
  failure.crashReport = shipShellRecord(
    crashRecord({
      crash: bunCrash,
      failure,
      version: app.getVersion(),
      platform: process.platform,
      arch: process.arch,
      releaseFlavor: failure.releaseFlavor,
      runtimeFlavor: failure.runtimeFlavor,
      clientSessionId: readAnalyticsId(desktopStatePath(), fs),
    }),
  )
  return failure.crashReport
}

async function showOrchestratorFailure(failure, parent = mainWindow) {
  const { title, type, message, detail, compatibilityBuildUrl } = describeFailure(failure)
  // the dialog is what the user is owed, so the row gets a few seconds at most (see the shipper)
  await reportBunCrash(failure)
  const buttons = []
  const actions = []
  if (compatibilityBuildUrl) {
    buttons.push('Get Compatibility Build')
    actions.push(() => shell.openExternal(compatibilityBuildUrl))
  }
  if (failure.logPath) {
    buttons.push('Show Log')
    actions.push(() => shell.showItemInFolder(failure.logPath))
  }
  buttons.push('Quit')
  actions.push(() => {})

  const options = {
    type,
    title,
    message,
    detail,
    buttons,
    defaultId: 0,
    cancelId: buttons.length - 1,
    noLink: true,
  }
  const response = askSync(parent, options)
  try {
    await actions[response]?.()
  } catch (err) {
    console.error('[orchestrator] diagnostic action failed:', err?.message ?? err)
  }
}

function startOrchestrator(requestedPort = 0) {
  return new Promise((resolve, reject) => {
    const { bun, args, cwd, uiDir, wasmDir, packaged } = resolveOrchestrator()
    const capture = createStderrCapture(bun, args)
    const launchId = randomUUID()
    // Published to the renderer only once the orchestrator holding it is the
    // one being started; a crash restart mints a new one and the renderer
    // re-reads it on its next call.
    apiLaunchToken = launchId
    let exited = false
    let ready = false
    let startupSettled = false
    let suppressCloseFailure = false
    let stdoutBuffer = ''
    let readinessStarted = false
    let startupTimer
    let closeAfterExitTimer
    // When the spawn happened, and how much the child actually said. Both are only knowable here,
    // and for a child that dies or hangs without printing they are the only evidence that exists.
    // Counted from the child's own streams rather than from capture.stderrTail, which is a bounded
    // tail the launcher also writes its own lines into.
    let spawnedAt = 0
    let childStdoutBytes = 0
    let childStderrBytes = 0

    const failure = (kind, fields = {}) => ({
      kind,
      bunPath: bun,
      // Path-free, for the dialog: the full command is the log's first three lines.
      spawnTarget: {
        runtime: path.basename(bun),
        entry: path.basename(args[args.length - 1] ?? ''),
        packaged,
      },
      childOutput: { stdout: childStdoutBytes, stderr: childStderrBytes },
      waitedMs: spawnedAt ? Date.now() - spawnedAt : undefined,
      platform: process.platform,
      arch: process.arch,
      releaseFlavor: releaseFlavor(),
      runtimeFlavor: packaged ? packagedBunRuntime().runtimeFlavor : 'standard',
      baselineBundled: packaged ? packagedBunRuntime().baselineBundled : false,
      restartAttempt: restartAttempts,
      logPath: capture.logPath,
      stderrTail: capture.stderrTail,
      ...fields,
    })
    const rejectStartup = (diagnostic) => {
      if (startupSettled) return
      startupSettled = true
      clearTimeout(startupTimer)
      clearTimeout(closeAfterExitTimer)
      const err = new Error(describeFailure(diagnostic).message)
      err.orchestratorFailure = diagnostic
      reject(err)
    }

    // extraResources can lose the executable bit when unpacked; restore it.
    if (packaged && process.platform !== 'win32') {
      try {
        fs.chmodSync(bun, 0o755)
      } catch {
        /* best-effort */
      }
    }

    if (!shellLifetime) {
      rejectStartup(failure('spawn', { errorMessage: 'The shell lifetime server is unavailable.' }))
      return
    }
    // No secret goes in `env`. Another process of the same user reads a child's STARTING environment
    // with `ps eww <pid>` (macOS) or `/proc/<pid>/environ` (Linux), whatever the child deletes later,
    // and published bridges read FREEBUFF_LAUNCH_ID exactly that way. The launch id and the bridge
    // tokens ride the stdin bootstrap line below instead (src/server/launch-bootstrap.ts); only
    // ports and non-secret settings stay here.
    const env = {
      ...process.env,
      PORT: String(requestedPort),
      FREEBUFF_SHELL_LIFETIME_PORT: String(shellLifetime.port),
      FREEBUFF_DESKTOP_STATE_PATH: desktopStatePath(),
      // An immediate relaunch can reach the profile before the old orchestrator finishes its normal
      // lifetime shutdown. Wait for that lock only in Electron-owned launches; hand-run servers stay fast.
      FREEBUFF_PROFILE_LOCK_WAIT_MS: '10000',
      // The Bun process owns telemetry, but only Electron knows the installed
      // package version. Pass it across so renderer crashes group by release.
      FREEBUFF_APP_VERSION: app.getVersion(),
    }
    if (uiDir) env.FREEBUFF_UI_DIR = uiDir
    // The orchestrator admits exactly its own origin. In dev-UI mode the renderer lives on Vite's,
    // which proxies /api/ with the page's Origin intact, so name it; otherwise never inherit one.
    if (process.env.FREEBUFF_DEV_UI) {
      env.FREEBUFF_DESKTOP_UI_ORIGIN = `http://127.0.0.1:${Number(process.env.FREEBUFF_DESKTOP_UI_PORT) || 5174}`
    } else {
      delete env.FREEBUFF_DESKTOP_UI_ORIGIN
    }
    if (wasmDir) {
      env.CODEBUFF_WASM_DIR = wasmDir
      env.CODEBUFF_TREE_SITTER_WASM_PATH = path.join(wasmDir, 'tree-sitter.wasm')
    }
    // Freebuff's own git (scripts/fetch-git.ts). The orchestrator runs it by path and never puts it
    // on PATH, so the user's and the agent's `git` stay theirs.
    if (packaged) {
      const gitDir = path.join(process.resourcesPath, 'git')
      if (fs.existsSync(gitDir)) env.FREEBUFF_GIT_DIR = gitDir
    }
    if (signing) {
      env.FREEBUFF_SIGNING_STATE = signing.state
      if (signing.team) env.FREEBUFF_SIGNING_TEAM = signing.team
    }
    // Never inherit a secret this shell was itself started with (a dev shell, a harness): the child
    // takes its secrets from stdin, and anything left here would be readable by other processes.
    for (const key of LAUNCH_SECRET_ENV_KEYS) delete env[key]
    // only this child ever learns the bridges' ports (here) and bearer tokens (on stdin)
    if (cdpBridge) env.FREEBUFF_CDP_BRIDGE_PORT = String(cdpBridge.port)
    if (mcpConsentBridge) env.FREEBUFF_MCP_CONSENT_PORT = String(mcpConsentBridge.port)

    lastSpawnAt = Date.now()
    spawnedAt = lastSpawnAt
    const proc = spawn(bun, args, {
      cwd,
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    serverProc = proc
    serverStopPromise = null
    // stdin only bootstraps this launch's secrets; lifetime detection uses the authenticated socket.
    // Parse a newline rather than waiting for EOF because Bun can retain a Windows pipe handle.
    proc.stdin.on('error', () => {})
    proc.stdin.end(
      `${launchBootstrapLine({
        shellLifetimeToken: shellLifetime.token,
        launchId,
        cdpBridgeToken: cdpBridge?.token,
        mcpConsentToken: mcpConsentBridge?.token,
      })}\n`,
    )

    proc.on('error', (err) => {
      exited = true
      capture.write(`[launcher] ${err.message}\n`)
      if (serverProc === proc) serverProc = null
      rejectStartup(
        failure('spawn', {
          // The errno, so the dialog can say what it means rather than only quoting it. A spawn
          // that fails this way must never be left to the startup timer: ENOENT at 30 seconds
          // reads as a slow machine, and it is a missing file.
          errorCode: err.code,
          errorMessage:
            `Failed to start the orchestrator with "${bun}": ${err.message}. ` +
            (packaged
              ? 'The bundled Bun runtime could not be launched.'
              : 'Make sure Bun is installed or set FREEBUFF_BUN_PATH.'),
        }),
      )
    })

    const beginReadiness = (line) => {
      const prefix = '[orchestrator-ready] '
      if (readinessStarted || !line.startsWith(prefix)) return
      let announcement
      try {
        announcement = JSON.parse(line.slice(prefix.length))
      } catch {
        return
      }
      if (
        announcement.launchId !== launchId ||
        announcement.pid !== proc.pid ||
        !Number.isInteger(announcement.port) ||
        announcement.port <= 0 ||
        announcement.port > 65535 ||
        (requestedPort !== 0 && announcement.port !== requestedPort)
      ) {
        return
      }
      readinessStarted = true
      waitForServer(announcement.port, launchId, proc.pid, 30000, () => exited).then(
        async () => {
          if (exited || startupSettled) return
          // Before any window can load against this orchestrator: it refuses every /api/ request
          // without the secret, and the renderer's event stream and terminals carry it only here.
          // A crash restart replaces the old launch's value under the same name.
          try {
            await setLaunchCookie(require('electron').session.defaultSession.cookies, announcement.port, launchId)
          } catch (err) {
            console.error('[orchestrator] could not set the launch cookie:', err?.message ?? err)
          }
          if (exited || startupSettled) return
          ready = true
          startupSettled = true
          clearTimeout(startupTimer)
          clearTimeout(closeAfterExitTimer)
          resolve(announcement.port)
        },
        () => {
          if (!exited) void timeOutStartup()
        },
      )
    }
    // The ready line carries the launch id. This shell's stdout is not private — a Linux desktop
    // session files it in the user's journal — so lines are echoed whole, with the id redacted,
    // unless a packaged-app harness that needs the id to call the API opts in. Whole lines, because
    // a chunk boundary inside the id would otherwise print it in two halves.
    const echoLaunchId = process.env.FREEBUFF_DESKTOP_ECHO_LAUNCH_ID === '1'
    const echo = (line) =>
      process.stdout.write(`[orchestrator] ${echoLaunchId ? line : redactLaunchId(line, launchId)}\n`)
    proc.stdout.on('data', (d) => {
      childStdoutBytes += d.length
      stdoutBuffer += d.toString('utf8')
      const lines = stdoutBuffer.split('\n')
      stdoutBuffer = lines.pop() ?? ''
      for (const line of lines) {
        echo(line)
        beginReadiness(line.trim())
      }
    })
    proc.stdout.once('end', () => {
      if (stdoutBuffer) echo(stdoutBuffer)
      stdoutBuffer = ''
    })
    proc.stderr.on('data', (d) => {
      childStderrBytes += d.length
      capture.write(d)
      process.stderr.write(`[orchestrator] ${d}`)
    })

    // `exit` can precede the final stderr chunks. Mark the process dead here so
    // readiness polling stops, but build diagnostics on `close`, after stdio is
    // fully drained into the excerpt and log file.
    proc.once('exit', (code, signal) => {
      exited = true
      // ...unless `close` never comes. See CLOSE_AFTER_EXIT_GRACE_MS: from here on the startup
      // timer will not report anything, so this is the last thing that can.
      if (ready || startupSettled || shuttingDown || suppressCloseFailure) return
      closeAfterExitTimer = setTimeout(() => {
        if (startupSettled || shuttingDown || suppressCloseFailure) return
        console.error(
          `[orchestrator] process ${proc.pid} exited (code ${code ?? 'none'}, signal ${signal ?? 'none'}) ` +
            'but its output streams stayed open; reporting the exit',
        )
        const diagnostic = failure('exit', { code, signal, stdioStillOpen: true })
        void reportBunCrash(diagnostic)
        rejectStartup(diagnostic)
      }, CLOSE_AFTER_EXIT_GRACE_MS)
    })

    proc.once('close', (code, signal) => {
      exited = true
      clearTimeout(closeAfterExitTimer)
      const pid = proc.pid
      if (serverProc === proc) serverProc = null
      if (shuttingDown || suppressCloseFailure) return
      console.error(`[orchestrator] process ${pid} ended (code ${code ?? 'none'}, signal ${signal ?? 'none'})`)
      const diagnostic = failure(ready ? 'runtime' : 'exit', { code, signal })
      // counted here, not only in the fatal dialog: a post-ready crash the restart budget absorbs
      // never reaches that dialog, and it is the same Bun bug
      void reportBunCrash(diagnostic)
      if (!ready) {
        rejectStartup(diagnostic)
      } else {
        void restartOrchestrator(diagnostic)
      }
    })

    const timeOutStartup = async () => {
      if (exited || startupSettled) return
      // The failed process must be gone before a retry. Otherwise it can keep the profile lock or
      // restart port and turn one timeout into OrchestratorAlreadyRunning or EADDRINUSE.
      suppressCloseFailure = true
      const closedProcess = waitForProcessClose(proc)
      proc.kill('SIGKILL')
      const closed = await closedProcess
      rejectStartup(
        closed
          ? failure('timeout')
          : failure('cleanup', {
              // Not "restart Windows": SIGKILL leaving a process whose pipes are still held is a
              // POSIX outcome too (see CLOSE_AFTER_EXIT_GRACE_MS), and this exact branch has been
              // telling Linux users to reboot an OS they are not running.
              errorMessage: 'The failed orchestrator could not be stopped. Restart your computer and try again.',
            }),
      )
    }
    startupTimer = setTimeout(() => void timeOutStartup(), 30000)
  })
}

// A post-ready orchestrator exit gets a respawn on the same port (appUrl/appOrigin
// stay valid, so the renderer's SSE client reconnects and resyncs on its own — no
// window reload). The fatal dialog is reserved for a genuine crash loop: 3 failed
// restarts without 60s of uptime in between.
async function restartOrchestrator(diagnostic) {
  while (!shuttingDown) {
    if (Date.now() - lastSpawnAt > 60_000) restartAttempts = 0 // stayed up → fresh budget
    if (restartAttempts >= 3) break
    restartAttempts++
    try {
      await startOrchestrator(serverPort)
      return
    } catch (err) {
      diagnostic = err?.orchestratorFailure ?? diagnostic
      if (diagnostic.kind === 'cleanup') break
    }
  }
  if (shuttingDown) return
  await showOrchestratorFailure(diagnostic)
  quitApp()
}

function stopOrchestrator() {
  shuttingDown = true
  if (shellLifetime) {
    void shellLifetime.close()
    shellLifetime = null
  }
  if (cdpBridge) {
    void cdpBridge.close()
    cdpBridge = null
  }
  if (mcpConsentBridge) {
    void mcpConsentBridge.close()
    mcpConsentBridge = null
  }
  const proc = serverProc
  if (!proc || proc.exitCode !== null || proc.signalCode !== null) {
    return Promise.resolve()
  }
  if (serverStopPromise) return serverStopPromise

  serverStopPromise = new Promise((resolve) => {
    let settled = false
    let hardStop
    let giveUp
    const finish = () => {
      if (settled) return
      settled = true
      clearTimeout(hardStop)
      clearTimeout(giveUp)
      resolve()
    }
    proc.once('close', finish)
    // Windows has no catchable SIGTERM: Node terminates the process immediately. Let the lifetime
    // disconnect drive Bun's normal shutdown there, then use the hard-stop timer as the fallback.
    if (process.platform !== 'win32' && !proc.killed) proc.kill('SIGTERM')
    // The Bun shutdown handler releases hosted sessions before exiting. Keep
    // Electron alive long enough for that DELETE to finish; an updater exit
    // that kills the process tree immediately otherwise leaves an invisible
    // one-tab holder behind for the rest of its server-side window.
    hardStop = setTimeout(() => {
      // ChildProcess.killed only means kill() was called; it becomes true before
      // the child actually exits, so it cannot tell us whether SIGTERM worked.
      if (proc.exitCode === null && proc.signalCode === null) proc.kill('SIGKILL')
    }, 3000)
    // Do not let a pathological child make Quit impossible even after SIGKILL.
    giveUp = setTimeout(finish, 3500)
  })
  return serverStopPromise
}

/** Post a renderer death to the orchestrator's diagnostics endpoint, which ships it
 *  like any other renderer crash. Best-effort by definition: if the orchestrator is
 *  the thing that is gone, the shell already surfaces that with its own dialog. */
function reportRendererDeath(name, message, health) {
  console.error(`[renderer] ${name}: ${message}`)
  if (!appUrl) return
  postMutation(fetch, new URL('api/diagnostics/renderer-error', appUrl), apiLaunchToken, {
    name,
    message,
    boundary: 'shell',
    health,
  }).catch(() => {})
}

function loadingPage() {
  // The held frame the renderer takes over unchanged (splash.cjs explains the match). Painted in
  // the theme main last saw — the mirror file read at startup — so the handoff isn't jarring.
  const theme = resolvedTheme()
  const html = splashHtml(SHELL_THEMES[theme], theme)
  return `data:text/html;charset=utf-8,${encodeURIComponent(html)}`
}

/** Whether `url` is same-origin with the trusted app origin (set in boot()).
 *  False before boot resolves the origin, or for an unparseable URL. */
function isAppUrl(url) {
  if (!appOrigin) return false
  try {
    return new URL(url).origin === appOrigin
  } catch {
    return false
  }
}

/** Hand an off-origin link to the system browser — but only http(s), so a
 *  malicious document can't get the OS to launch a file:/custom-scheme URL.
 *  Resolves false when the URL is unsafe or the OS rejects the open request. */
async function openExternal(url) {
  try {
    const parsed = new URL(url)
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false
    await shell.openExternal(parsed.toString())
    return true
  } catch {
    return false
  }
}


const browserNative = require('./browser-native.cjs').createBrowserNative({
  app, BrowserWindow, session: require('electron').session, dialog, ipcMain, shell, isAppUrl, getBun: () => resolveOrchestrator().bun,
})
browserNative.install()

// One shape for push ('window-state') and pull ('window:state'): mac's
// fullscreen traffic-light inset and the frameless maximize/restore glyph both
// render from it.
function windowState(win) {
  return { fullScreen: win.isFullScreen(), maximized: win.isMaximized() }
}

function buildWindow(sizeOpts = {}) {
  // Linux otherwise stacks three rows of chrome (WM title bar, Electron menu
  // bar, our tab bar): go frameless there and let the renderer draw the window
  // buttons. macOS uses its inset traffic lights. Windows keeps native caption
  // buttons (and therefore Snap Layouts), but overlays them on our tab bar so
  // the app no longer sits below a second, disconnected title bar.
  const frameless = process.platform === 'linux'
  const windowsTitleBar = process.platform === 'win32'
  const colors = shellColors()
  const winOpts = {
    width: 1440,
    height: 900,
    minWidth: 720,
    minHeight: 480,
    ...sizeOpts,
    backgroundColor: colors.background,
    title: 'Freebuff',
    frame: !frameless,
    // Off mac the menu isn't in the system bar — Electron draws it as a row
    // inside the window. Hide it everywhere (Alt reveals it, accelerators fire
    // either way): our tab bar is the top chrome, and that row rendered as a
    // light strip across a near-black app on any OS not themed dark.
    autoHideMenuBar: true,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : windowsTitleBar ? 'hidden' : 'default',
    // Native 14px traffic lights share the 48px tab row's centerline and have
    // equal space from the top and left window edges. Pop-outs use this too.
    ...(process.platform === 'darwin' ? { trafficLightPosition: { x: 17, y: 17 } } : {}),
    ...(windowsTitleBar
      ? {
          titleBarOverlay: {
            color: colors.overlay,
            symbolColor: colors.overlaySymbol,
            height: 48,
          },
        }
      : {}),
    webPreferences: {
      zoomFactor: interfaceZoom.get() / 100,
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      // The sandboxed preload can only require built-ins, so it learns whether
      // to draw a title bar from an argv flag derived from THIS window's frame
      // option — the two can't disagree.
      additionalArguments: [`--custom-title-bar=${frameless ? '1' : '0'}`],
      // The explorer panel's Preview tab embeds the thread's dev server in a
      // <webview> — its own webContents per preview (unprivileged; see the
      // will-attach-webview guard). Loading is confined to loopback servers.
      webviewTag: true,
    },
  }
  if (fs.existsSync(APP_ICON_PATH)) winOpts.icon = APP_ICON_PATH

  const win = new BrowserWindow(winOpts)
  interfaceZoom.attach(win)
  attachTextContextMenu(win.webContents)
  // Keep the native menu installed for accelerators, but never let Electron
  // insert the legacy File/Edit/View row between the integrated title bar and
  // the app. autoHideMenuBar covers startup; this also covers restored windows.
  if (process.platform !== 'darwin') win.setMenuBarVisibility(false)

  const sendWindowState = () => {
    if (win.isDestroyed() || win.webContents.isDestroyed()) return
    win.webContents.send('window-state', windowState(win))
  }
  win.on('enter-full-screen', sendWindowState)
  win.on('leave-full-screen', sendWindowState)
  // The maximize/restore glyph follows the WINDOW, not the click — WM-side
  // tiles, snaps, and drag-region double-clicks must update it too.
  win.on('maximize', sendWindowState)
  win.on('unmaximize', sendWindowState)
  win.webContents.on('did-finish-load', sendWindowState)

  // The window can end up blank in ways no page script can report, because no page
  // script is left running: the document fails to load, or the renderer process is
  // killed outright (out of memory, a GPU fault). Both leave the user staring at a
  // white window; neither reaches the in-page hooks in index.html. Report them from
  // here, where the process that died isn't the one doing the reporting.
  win.webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
    // -3 is ABORTED — a navigation superseded by another one, not a failure
    if (!isMainFrame || errorCode === -3) return
    reportRendererDeath('DidFailLoad', `${errorDescription} (${errorCode}) loading ${validatedURL}`)
  })
  rendererHealth.set(win.webContents, watchRenderer(win, {
    app, dialog, isQuitting: () => quitting, isTrusted: isAppUrl,
    reportCrash: (message, health) => reportRendererDeath('RenderProcessGone', message, health),
    reportHealth: (health) => {
      if (appUrl) postMutation(fetch, new URL('api/diagnostics/renderer-health', appUrl), apiLaunchToken, health).catch(() => {})
    },
    beforeReload: () => windowLoads.initiating(win.webContents, 'crash-dialog-reload'),
  }))
  // Counts the app's own page only: the splash is a data: URL, and a reload is a navigation too.
  win.webContents.on('did-start-navigation', (_event, url, inPlace, mainFrame) => {
    if (mainFrame && !inPlace && isAppUrl(url)) windowLoads.appNavigationStarted(win.webContents)
  })

  // New windows: only the trusted app origin may open in-app (with the preload
  // bridge attached); every other URL is denied and opened in the system browser.
  // A broad "any localhost" allow would let a malicious preview link load another
  // local service in a privileged window. http(s) only — never hand the OS a
  // file:/custom-scheme URL.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (isAppUrl(url)) return { action: 'allow' }
    void openExternal(url)
    return { action: 'deny' }
  })

  // Top-level navigation: keep the renderer pinned to the app origin so the
  // preload surface can't travel to an untrusted document. Off-origin link
  // clicks are cancelled and sent to the system browser instead.
  win.webContents.on('will-navigate', (event, url) => {
    if (isAppUrl(url)) return
    event.preventDefault()
    void openExternal(url)
  })

  return win
}

/** @param {'main' | 'main-reopened'} kind 'main-reopened' when the Dock brings back a closed main window */
function createWindow(kind = 'main') {
  menuRouter.mainWindowCreated()
  mainWindow = buildWindow()
  windowLoads.track(mainWindow.webContents, kind)
  mainWindow.loadURL(loadingPage())
  // Off mac, closing the main window quits (see the 'closed' handler below), so the guard
  // belongs here — by 'before-quit' the window is already gone, and a cancelled quit would
  // leave the app running with nothing on screen. On mac the window close is not a quit:
  // the app stays in the dock and turns keep running. Keep its renderer alive while
  // hidden so a later Dock Quit still knows about work across every project.
  guardMainWindowClose(mainWindow, {
    platform: process.platform,
    isQuitting: appIsLeaving,
    requestQuit,
  })
  const win = mainWindow
  mainWindow.on('closed', () => {
    mainWindow = null
    if (!appIsLeaving()) windowLoads.mainClosed(win.closeRequestedByApp ? 'app' : 'native')
    // off mac there is no dock to bring the main window back, so pop-outs must not outlive it;
    // quitting (not closing) keeps their threads in the workspace for the next launch
    if (process.platform !== 'darwin' && !appIsLeaving()) quitApp()
  })
  return mainWindow
}

// A link is only an invitation to review. Fetch through the signed-in host, then
// require native consent and a folder before starting any model or command.
const { parseLabLink } = require('./agentic-lab-link.cjs')
let pendingLabLink = process.argv.find((arg) => parseLabLink(arg)) ?? null
let openingLabTest = false
async function openLabTestLink(value) {
  const ref = parseLabLink(value)
  if (!ref) return
  if (!appUrl) { pendingLabLink = value; return }
  if (openingLabTest) return
  openingLabTest = true
  try {
    const call = async (body) => {
      const response = await postMutation(fetch, new URL('api/agentic-lab/test', appUrl), apiLaunchToken, body)
      const data = await response.json()
      if (!response.ok) throw new Error(data.error || 'Could not open this Lab test.')
      return data
    }
    const preview = await call({ ref, preview: true })
    const confirm = createConsentWindow({ BrowserWindow, ipcMain, theme: resolvedTheme, fallback: (_parent, options) => dialog.showMessageBox(options) })
    const explanation = `This runs on your computer using your Freebuff session. It can install the declared CLI, change files in the folder you choose, and open a login browser. The advertiser is not charged and no campaign is published. Choose a disposable test checkout.\n\n${ref.sha256}`
    const answer = await confirm(mainWindow, { type: 'question',
      title: 'Test agentic skill in Desktop', message: preview.title,
      detail: explanation,
      explanation,
      specText: preview.procedure,
      buttons: ['Cancel', 'Choose test folder'], defaultId: 0, cancelId: 0,
    })
    if (answer.response !== 1) return
    const folder = await dialog.showOpenDialog({ title: 'Choose a disposable test project', properties: ['openDirectory', 'createDirectory'] })
    if (folder.canceled || !folder.filePaths[0]) return
    const started = await call({ ref, projectPath: folder.filePaths[0], accepted: true })
    openThreadWindow(started.threadId, started.projectPath, true)
  } catch (error) {
    await dialog.showMessageBox({ type: 'error', title: 'Desktop Lab test', message: error.message || String(error) })
  } finally { openingLabTest = false }
}
app.on('open-url', (event, value) => { event.preventDefault(); void openLabTestLink(value) })

const threadWindows = new Map()

function threadWindowUrl(threadId, projectPath) {
  const url = new URL(appUrl)
  url.searchParams.set('thread', threadId)
  url.searchParams.set('project', projectPath)
  return url.toString()
}

function openThreadWindow(threadId, projectPath, focus) {
  if (!appUrl) return
  const existing = threadWindows.get(threadId)
  if (existing && !existing.isDestroyed()) {
    if (focus) {
      if (existing.isMinimized()) existing.restore()
      existing.focus()
    }
    return
  }
  // show:false + showInactive so restoring saved pop-outs at launch cannot steal
  // focus from the main window; only an explicit gesture (focus=true) foregrounds it
  const win = buildWindow({ width: 1200, height: 800, show: false })
  windowLoads.track(win.webContents, 'thread')
  threadWindows.set(threadId, win)
  win.once('ready-to-show', () => {
    if (focus) win.show()
    else win.showInactive()
  })
  win.on('close', (event) => {
    if (appIsLeaving() || shuttingDown || win.rendererClosedThread) return
    event.preventDefault()
    closeGuard.request(win, 'chat', () => {
      // The renderer already used closeTab, including its guard and server-side close.
      win.rendererClosedThread = true
      win.close()
    }, () => {
      // A failed/loading renderer cannot host a custom dialog. Keep this path usable,
      // with a native warning since its thread's activity is unknown.
      if (askSync(win, {
        type: 'question', title: 'Close this chat?', message: 'Close this chat?',
        detail: 'Any agent still working in this chat will be interrupted.',
        buttons: ['Keep open', 'Close chat'], defaultId: 0, cancelId: 0, noLink: true,
      }) !== 1) return false
      closeThreadOnServer(threadId)
      return true
    })
  })
  win.on('closed', () => {
    threadWindows.delete(threadId)
    // rendererClosedThread: the renderer already closed the thread itself (⌘W path),
    // so a second server-side close would just churn the closed thread again
    if (!appIsLeaving() && !shuttingDown && !win.rendererClosedThread) closeThreadOnServer(threadId)
  })
  void win.loadURL(threadWindowUrl(threadId, projectPath))
}

function closeThreadOnServer(threadId) {
  if (!appUrl) return
  postMutation(
    fetch,
    new URL(`api/thread/${encodeURIComponent(threadId)}/close`, appUrl),
    apiLaunchToken,
    {},
  ).catch(() => {})
}

// ------------------------------------------------------------------ quit guard
//
// Quitting stops the orchestrator, and every turn in flight with it. The reported
// failure mode is a window closed by reflex: the user meant "get this off my screen"
// (other apps minimise to a tray), came back an hour later, and the agent had been dead
// the whole time. So a quit that would abandon live work asks first. A quit with nothing
// running must still cost exactly one click, which is why this is gated on the busy
// signal rather than shown unconditionally.
//
// Native fallback only: healthy renderers use the same squircle dialog as tab closes.

/** the native dialog pumps the event loop, so a second gesture can arrive while it is open */
let asking = false

/** True when the quit may proceed. */
function confirmQuit(parent) {
  if (!busySignal.busy(Date.now())) return true
  if (asking) return false
  asking = true
  try {
    const response = askSync(parent, {
      type: 'question',
      title: 'Quit Freebuff?',
      message: 'Freebuff is still working.',
      // The old process stops, but each harness checkpoints provider state while it works. Relaunch
      // resumes that state and advances from the latest durable step rather than resending the request.
      detail:
        'Quitting stops the agents now. The next time you open Freebuff, interrupted turns ' +
        'continue automatically from their latest saved step. Completed steps, conversation ' +
        'context, and changes already written to your files are kept.',
      buttons: ['Cancel', 'Quit anyway'],
      // a stray Return keeps the agents alive
      defaultId: 0,
      cancelId: 0,
      noLink: true,
    })
    return response === 1
  } finally {
    asking = false
  }
}

const { createCloseGuard, guardMainWindowClose } = require('./close-guard.cjs')
const closeGuard = createCloseGuard({
  ipcMain,
  isTrusted: event => isTrustedAppSender(event, isAppUrl),
})

// Internal shutdowns and approved quits bypass the user-gesture guard. Updates and
// fatal startup failures must still be able to exit without a renderer to answer.
function quitApp() {
  quitting = true
  app.quit()
}

function requestQuit(parent = BrowserWindow.getFocusedWindow() ?? mainWindow) {
  closeGuard.request(parent, 'quit', quitApp, () => confirmQuit(parent))
}

// Menu commands go to the renderer; app-menu.cjs explains which window each one targets.
const menuRouter = createMenuRouter({
  getMainWindow: () => mainWindow,
  getFocusedWindow: () => BrowserWindow.getFocusedWindow(),
  boot: () => boot(),
})
ipcMain.on('menu:ready', (event) => menuRouter.onMenuReady(event))
ipcMain.on('menu:recording', (event, recording) => {
  if (isTrustedAppSender(event, isAppUrl) && typeof recording === 'boolean')
    event.sender.setIgnoreMenuShortcuts(recording)
})
ipcMain.on('menu:shortcuts', (event, bindings) => {
  if (isTrustedAppSender(event, isAppUrl)) updateMenuShortcuts(Menu.getApplicationMenu(), bindings)
})

// Paperclip → native open dialog. Allows files and/or folders (multi-select), and
// stats each pick so the renderer can label folders vs. files. Returns [] when the
// user cancels.
// The renderer's authorization for state-changing `/api/` calls. See
// `apiLaunchToken`. Synchronous because the renderer reads it on the way into
// every fetch and must not have to await first. Only the app's own top-level
// document gets it; anything else gets null (see ipc-sender.cjs).
ipcMain.on('freebuff:apiToken', (event) => {
  event.returnValue = apiTokenReply(event, isAppUrl, apiLaunchToken)
})

ipcMain.on('renderer:history', (event, counts) => {
  if (!isTrustedAppSender(event, isAppUrl)) return
  rendererHealth.get(event.sender)?.history(counts)
})

// Main's half of a page boot (window-loads.cjs), read once by src/ui/boot-report.ts.
ipcMain.handle('renderer:boot-info', (event) => {
  if (!isTrustedAppSender(event, isAppUrl)) return null
  const info = windowLoads.info(event.sender)
  let systemFreeKb
  try {
    systemFreeKb = process.getSystemMemoryInfo?.().free
  } catch {
    // diagnostics only: unknown is absent
  }
  return {
    ...(info ?? {}),
    appUptimeSeconds: Math.round(process.uptime()),
    ...(typeof systemFreeKb === 'number' ? { systemFreeKb } : {}),
  }
})

ipcMain.handle('dialog:pickAttachments', async (event, kind) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win) return []
  const res = await dialog.showOpenDialog(win, {
    title: 'Attach files or folders',
    buttonLabel: 'Attach',
    properties: attachmentDialogProperties(kind),
  })
  if (res.canceled) return []
  return res.filePaths.map((p) => {
    let isDirectory = false
    try {
      isDirectory = fs.statSync(p).isDirectory()
    } catch {
      /* unreadable — treat as a file */
    }
    return { path: p, name: path.basename(p), isDirectory }
  })
})

// Image button → native open dialog filtered to images. Deliberately narrower
// than the paperclip above: files only (no folders), and images first. The
// default filter is the set the attachment pipeline can inline for a model to
// actually SEE (services/attachments.ts VISION_MEDIA_TYPES); the wider group
// behind it still opens the formats that are only ever referenced by path, so
// nothing that used to be attachable stops being attachable. Returns [] on
// cancel.
const VIEWABLE_IMAGE_EXTENSIONS = ['png', 'jpg', 'jpeg', 'gif', 'webp']
const OTHER_IMAGE_EXTENSIONS = ['bmp', 'svg', 'avif', 'heic', 'heif', 'tif', 'tiff']

ipcMain.handle('dialog:pickImages', async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win) return []
  const res = await dialog.showOpenDialog(win, {
    title: 'Attach images',
    buttonLabel: 'Attach',
    properties: ['openFile', 'multiSelections'],
    filters: [
      { name: 'Images', extensions: VIEWABLE_IMAGE_EXTENSIONS },
      {
        name: 'All Images',
        extensions: [...VIEWABLE_IMAGE_EXTENSIONS, ...OTHER_IMAGE_EXTENSIONS],
      },
    ],
  })
  if (res.canceled) return []
  // isDirectory is always false here — the dialog cannot return one — but the
  // shape stays identical to pickAttachments so the renderer has one code path.
  return res.filePaths.map((p) => ({ path: p, name: path.basename(p), isDirectory: false }))
})

// Project picker → native folder chooser. Lets the user jump anywhere (home,
// favorites, type a path) instead of drilling the in-app browser from wherever
// it happens to start. Returns the chosen absolute path, or null on cancel.
ipcMain.handle('dialog:pickDirectory', async (event) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win) return null
  const res = await dialog.showOpenDialog(win, {
    title: 'Open a project folder',
    buttonLabel: 'Open',
    properties: ['openDirectory', 'createDirectory'],
  })
  return res.canceled || res.filePaths.length === 0 ? null : res.filePaths[0]
})

ipcMain.handle('file:download', async (event, request) => {
  if (!isTrustedAppSender(event, isAppUrl)) return { ok: false, error: 'Untrusted sender' }
  try {
    if (!request || typeof request !== 'object') throw new Error('Invalid file download')
    const result = await downloadThreadFile(request, {
      appUrl, token: apiLaunchToken, downloads: app.getPath('downloads'),
    })
    return { ok: true, ...result }
  } catch (error) {
    return { ok: false, error: error?.message || 'Could not download file' }
  }
})

ipcMain.handle('dialog:saveMarkdown', async (event, { filename, content }) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win) return false
  if (typeof filename !== 'string' || typeof content !== 'string') {
    throw new Error('Invalid Markdown export')
  }
  const result = await dialog.showSaveDialog(win, {
    title: 'Export thread as Markdown',
    defaultPath: path.basename(filename),
    filters: [{ name: 'Markdown', extensions: ['md'] }],
    properties: ['createDirectory', 'showOverwriteConfirmation'],
  })
  if (result.canceled || !result.filePath) return false
  await fs.promises.writeFile(result.filePath, content, 'utf8')
  return true
})

// Paste-to-attach and drop-to-attach: bytes with no path, and temp-dir files the OS is about to
// delete, are both kept by kept-attachments.cjs so the agent can still read them later.
ipcMain.handle('clipboard:saveImage', async (_e, { bytes, ext }) => saveClipboardImage(bytes, ext))
ipcMain.handle('attachment:keepTransient', async (_e, filePath) => keepTransientFile(filePath))

// Pre-send image previews use the same local path the agent receives, but the
// renderer cannot safely load arbitrary file:// URLs under context isolation.
// Keep this deliberately narrow: known image extensions, regular files, and a
// bounded payload returned as a data URL.
ipcMain.handle('attachment:readImage', async (_event, filePath) => readImage(filePath))

// Recovery flows (e.g. the "Claude Code is signed out" card) hand the user off
// to a real terminal they can type `claude /login` into. mac-only (stock
// Terminal.app, at its modern path with the pre-Catalina one as fallback);
// other platforms resolve false and the renderer hides the button — the
// copyable command is the whole flow there. shell.openPath resolves '' on
// success and an error string on failure, so the renderer can show feedback.
ipcMain.handle('shell:openTerminal', async () => {
  if (process.platform !== 'darwin') return false
  for (const terminalApp of [
    '/System/Applications/Utilities/Terminal.app',
    '/Applications/Utilities/Terminal.app',
  ]) {
    if ((await shell.openPath(terminalApp)) === '') return true
  }
  return false
})

// Open a web URL directly through Electron instead of renderer `window.open`.
// Sign-in obtains its URL asynchronously, after Chromium's popup activation
// window may have elapsed; this IPC path remains reliable and keeps the same
// http(s)-only boundary as link navigation above.
ipcMain.handle('shell:openExternal', (_event, url) => openExternal(url))

ipcMain.handle('shell:revealChange', async (event, { root, relativePath }) => {
  // openPath launches what it is given (a `.app` folder runs): app document only.
  if (!isTrustedAppSender(event, isAppUrl)) return false
  try {
    const target = resolveRevealTarget(root, relativePath)
    if (!target) return false
    if (target.directoryOnly) return (await shell.openPath(target.path)) === ''
    shell.showItemInFolder(target.path)
    return true
  } catch {
    return false
  }
})

ipcMain.handle('shell:revealAppData', async () => {
  try {
    // Reveal only project databases, not state.json beside them: that file contains auth sessions.
    return (await shell.openPath(path.join(path.dirname(desktopStatePath()), 'projects'))) === ''
  } catch {
    return false
  }
})

ipcMain.handle('shell:detectOpenTargets', () =>
  detectOpenTargets().map(({ id, label, kind }) => ({ id, label, kind })),
)

ipcMain.handle('shell:openIn', async (event, request) => {
  if (!isTrustedAppSender(event, isAppUrl)) return { ok: false, error: 'Untrusted sender' }
  try {
    if (!request || typeof request !== 'object' || Array.isArray(request)) {
      return { ok: false, error: 'Invalid open request' }
    }
    const { targetId, root, relativePath, line } = request
    if (typeof targetId !== 'string') return { ok: false, error: 'Invalid open target' }
    if (line !== undefined && (!Number.isInteger(line) || line < 1 || line > 10_000_000)) {
      return { ok: false, error: 'Invalid line number' }
    }
    const target = detectOpenTargets().find((candidate) => candidate.id === targetId)
    if (!target) return { ok: false, error: 'That application is not available' }
    const resolved = resolveOpenTarget(root, relativePath)
    if (!resolved) return { ok: false, error: 'The workspace path is unavailable' }

    if (target.id === 'copy-path') {
      clipboard.writeText(resolved.requested)
    } else if (target.id === 'file-manager') {
      if (resolved.fallback || fs.statSync(resolved.opened).isDirectory()) {
        const error = await shell.openPath(resolved.opened)
        if (error) return { ok: false, error }
      } else {
        shell.showItemInFolder(resolved.opened)
      }
    } else {
      const args = launchArgs(target, resolved, line)
      if (!args || !target.executable) return { ok: false, error: 'That application cannot open this path' }
      await new Promise((resolve, reject) => {
        const child = spawn(target.executable, args, {
          cwd: launchCwd(target, resolved),
          detached: true,
          stdio: 'ignore',
          windowsHide: target.kind !== 'terminal',
        })
        child.once('spawn', () => {
          child.unref()
          resolve()
        })
        child.once('error', reject)
      })
    }
    return { ok: true, path: resolved.requested, openedPath: resolved.opened, fallback: resolved.fallback }
  } catch (error) {
    return { ok: false, error: error instanceof Error ? error.message : 'Could not open that path' }
  }
})

ipcMain.handle('window:state', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  return win ? windowState(win) : { fullScreen: false, maximized: false }
})

// Raw attention/power state for the ad request's clientContext. The renderer
// buckets it (common/src/types/ad-client-context.ts) so only buckets leave the
// machine. Every field is optional and the reply never rejects (ad-context.cjs).
// Built on first use: `screen` and `powerMonitor` cannot be touched before
// ready. Untrusted senders get {} rather than the user's idle time.
let adContextReader = null
// Wave 2: installed at boot (after ready) so a sleep before the first ad request still counts.
let adResumeClock = null
// Built at boot (warmAdContextReader) so the first ad request of a launch does
// not pay construction, editor detection and the GPU query inside the
// renderer's 50ms IPC budget (AD_CONTEXT_IPC_TIMEOUT_MS) -- on a cold start that
// cost lost every Electron field on the launch's first impression. The handler
// still builds it lazily if boot has not yet run.
function ensureAdContextReader() {
  if (!adContextReader) {
    const { screen, powerMonitor, nativeTheme } = require('electron')
    adContextReader = createAdContextReader({
      screen,
      powerMonitor,
      detectEditors: installedEditorDetector({ detectOpenTargets }),
      getGpuInfo: () => app.getGPUInfo('basic'),
      getLoginItemSettings: () => app.getLoginItemSettings(),
      processUptime: () => process.uptime(),
      // read through the binding: the clock is installed at boot, possibly after this reader
      resumeClock: { secondsAgo: () => (adResumeClock ? adResumeClock.secondsAgo() : undefined) },
      nativeTheme,
      appFacts: {
        channel: app.isPackaged ? 'stable' : 'dev',
        installMethod: installMethodOf({
          isPackaged: app.isPackaged,
          platform: process.platform,
          env: process.env,
          resourcesPath: process.resourcesPath,
        }),
        electronVersion: process.versions.electron,
        // Desktop has no tray or menu-bar mode: it always lives in the dock / taskbar.
        tray: false,
      },
    })
  }
  return adContextReader
}

function warmAdContextReader() {
  try {
    // A window-less read starts the editor and GPU caches; its result is discarded.
    ensureAdContextReader().read(null)
  } catch {
    // Warming is best effort; the handler builds the reader on demand.
  }
}

ipcMain.handle('ads:context', (event) => {
  try {
    if (!isTrustedAppSender(event, isAppUrl)) return {}
    return ensureAdContextReader().read(BrowserWindow.fromWebContents(event.sender))
  } catch {
    return {}
  }
})

// Frameless (Linux) title-bar buttons. Preview content can't reach these — a
// <webview> gets no preload at all (see will-attach-webview), so it has no
// ipcRenderer; acting on the sender's window is just belt-and-braces. Results
// come back on 'window-state' like any WM-driven change.
ipcMain.handle('window:minimize', (event) => {
  BrowserWindow.fromWebContents(event.sender)?.minimize()
})

ipcMain.handle('window:toggleMaximize', (event) => {
  const win = BrowserWindow.fromWebContents(event.sender)
  if (win?.isMaximized()) win.unmaximize()
  else win?.maximize()
})

// close(), not destroy(), so shutdown runs the same as a native close.
ipcMain.handle('window:close', (event, rendererClosedThread) => {
  if (!isTrustedAppSender(event, isAppUrl)) return
  const win = BrowserWindow.fromWebContents(event.sender)
  if (!win) return
  // Cmd+W closes the thread before its now-empty renderer asks to close the window. The custom
  // title-bar x does not, so its native close must still post the server request below.
  if (rendererClosedThread === true) win.rendererClosedThread = true
  // the boot report of a main window reopened later says which kind of close preceded it
  win.closeRequestedByApp = true
  win.close()
})

ipcMain.handle('window:openThread', (_event, { threadId, projectPath, focus }) => {
  if (typeof threadId !== 'string' || !threadId) return
  if (typeof projectPath !== 'string' || !projectPath) return
  openThreadWindow(threadId, projectPath, focus !== false)
})

installFileNavigation({
  ipcMain,
  getMainWindow: () => mainWindow,
  openMainWindow: boot,
  focusApp: () => app.focus({ steal: true }),
})

// A sponsored run waiting on the user (COD-828), while the app is in the background.
installNeedsYouNotifications({
  ipcMain,
  Notification: require('electron').Notification,
  getMainWindow: () => mainWindow,
  openMainWindow: boot,
  focusApp: () => app.focus({ steal: true }),
  appFocused: () => BrowserWindow.getFocusedWindow() !== null,
})

ipcMain.on('window:requestAttention', (event) => {
  requestWindowAttention(
    BrowserWindow.fromWebContents(event.sender),
    BrowserWindow.getFocusedWindow() !== null,
  )
})

ipcMain.on('window:clearAttention', (event) => {
  clearWindowAttention(BrowserWindow.fromWebContents(event.sender))
})

// The end of a sign-in the user left the app to finish. Their browser is showing "you're signed
// in" and the thing they wanted is behind it, so the app comes back to them rather than waiting to
// be found — the same courtesy `second-instance` already extends to a re-launch.
//
// Which window, and the platform handling, live in surface-window.cjs so they can be tested without
// Electron. Focusing one window several times is a no-op, so the several windows that each report
// the same sign-in need no de-duplication here.
ipcMain.on('window:signInCompleted', () => {
  surfaceWindow({ mainWindow, threadWindows, focusApp: () => app.focus({ steal: true }) })
})

// The window frame Electron draws is ours to colour; the page inside re-tones itself.
function paintWindows() {
  const colors = shellColors()
  for (const win of BrowserWindow.getAllWindows()) {
    win.setBackgroundColor(colors.background)
    if (process.platform === 'win32') {
      win.setTitleBarOverlay({ color: colors.overlay, symbolColor: colors.overlaySymbol })
    }
  }
}

ipcMain.on('theme:set', (event, theme, colors) => {
  if (!interfaceZoom.trusted(event)) return
  if (theme !== 'dark' && theme !== 'light' && theme !== 'system') return
  // Presets can share dark/light while painting entirely different title bars. Only pass
  // palette hex colors to Electron; system mode must keep following nativeTheme updates.
  const hex = /^#[\da-f]{6}$/i
  titleBarColors = theme !== 'system' && colors
    && typeof colors.color === 'string' && hex.test(colors.color)
    && typeof colors.symbolColor === 'string' && hex.test(colors.symbolColor)
    ? { color: colors.color, symbolColor: colors.symbolColor }
    : null
  if (theme === themePref) {
    paintWindows()
    return
  }
  themePref = theme
  try {
    // the preference, unresolved: this mirror is what paints the splash on the next launch, and
    // storing 'dark' for a user who chose 'system' would silently pin them to it
    fs.writeFileSync(themeFile, theme)
  } catch {}
  // 'system' is a themeSource Electron understands, and it is also what makes `prefers-color-scheme`
  // in every renderer report the real OS setting rather than the theme we last forced
  nativeTheme.themeSource = theme
  paintWindows()
  for (const win of BrowserWindow.getAllWindows()) {
    // the preference travels between windows, not the colour — each renderer resolves it, so a
    // second window left on 'system' keeps following the OS instead of freezing at today's answer
    if (win.webContents.id !== event.sender.id && !win.webContents.isDestroyed()) {
      win.webContents.send('theme', theme)
    }
  }
})

ipcMain.handle('interface-zoom:get', (event) => {
  if (!interfaceZoom.trusted(event)) throw new Error('Untrusted interface size request')
  return interfaceZoom.get()
})
ipcMain.handle('interface-zoom:set', (event, value) => {
  if (!interfaceZoom.trusted(event)) throw new Error('Untrusted interface size request')
  return interfaceZoom.set(value)
})

// null when this build has no Discord application: the renderer hides the setting entirely
ipcMain.handle('discord:enabled', () => (discordClientId ? discordEnabled : null))
ipcMain.handle('discord:setEnabled', (_event, value) => {
  if (!discordClientId) return null
  discordEnabled = value === true
  try {
    fs.writeFileSync(discordPrefFile, discordEnabled ? 'on' : 'off')
  } catch {}
  discordPresence?.setEnabled(discordEnabled)
  return discordEnabled
})
// A second listener on the renderer's busy heartbeat (updater.cjs owns the first): the activity
// says whether an agent is working. Repeats of the same answer are dropped in discord-presence.
ipcMain.on('update:busy', (_event, value) => discordPresence?.setBusy(!!value))

// The OS changed appearance — macOS switching at sunset, or the user flipping it. Renderers learn
// this themselves through `prefers-color-scheme`, so this only repaints the native chrome around
// them. A pinned theme ignores it: themeSource is holding Chromium to our choice either way.
nativeTheme.on('updated', () => {
  if (themePref !== 'system') return
  paintWindows()
})

installTextEditing(ipcMain, (event) => isTrustedAppSender(event, isAppUrl))

ipcMain.handle('menu:tabContext', (event) => {
  return new Promise((resolve) => {
    let settled = false
    const done = (action) => {
      if (settled) return
      settled = true
      resolve(action)
    }
    const menu = Menu.buildFromTemplate([
      { label: 'Rename Tab', click: () => done('rename') },
      { label: 'Export as Markdown…', click: () => done('export-markdown') },
      { label: 'Move to New Window', click: () => done('move-to-window') },
      { label: 'Close Tab', click: () => done('close') },
    ])
    menu.popup({
      window: BrowserWindow.fromWebContents(event.sender) ?? undefined,
      // the callback fires on dismissal AND before a click lands; give the click a beat
      callback: () => setTimeout(() => done(null), 100),
    })
  })
})

function buildMenu(reloadApp) {
  const template = appMenuTemplate({
    platform: process.platform,
    appName: app.name,
    sendMenuCommand: (name) => menuRouter.sendMenuCommand(name),
    checkForUpdates: () => checkForUpdatesInteractive(),
    requestQuit: () => requestQuit(),
    reloadApp,
    zoomCommand: (action) => interfaceZoom.command(action),
  })
  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

// macOS shows the Dock / Cmd+Tab icon from the running .app bundle, NOT from a
// BrowserWindow's `icon` option (that one is ignored on macOS). In the packaged
// app the bundled icon.icns covers this, but in dev the running bundle is
// Electron's own, so without this the switcher shows the Electron logo. Setting
// the dock icon at runtime fixes both Dock and Cmd+Tab in dev. (The Cmd+Tab
// *name* comes from the bundle's CFBundleName, which has no runtime API — see
// scripts/brand-dev-electron.ts for the dev-only fix.)
function applyDockIcon() {
  if (process.platform !== 'darwin' || !app.dock) return
  try {
    if (fs.existsSync(APP_ICON_PATH)) app.dock.setIcon(APP_ICON_PATH)
  } catch {
    /* best-effort — a bad icon shouldn't stop the app booting */
  }
}

async function boot() {
  // The chrome Electron draws around the UI — the revealed menu bar, the native
  // title bar, context menus, file dialogs — follows the OS theme, so a
  // light-themed OS framed the dark app in white. Pin it to the app's theme
  // instead: the mirror file read at startup, confirmed by the renderer over
  // 'theme:set' once its saved pref arrives. A preference of 'system' hands that
  // pinning back to the OS, which is the whole point of it.
  // (Widgets *inside* the page are a separate opt-in: `color-scheme` in app.css.)
  nativeTheme.themeSource = themePref
  applyDockIcon()
  // Reattach, don't respawn: on a macOS dock re-activate the window may have been
  // closed while the orchestrator stayed alive. Spawning another would overwrite
  // serverProc and leak the first. Reuse the live one and just open a window.
  if (serverProc && appUrl) {
    const win = createWindow('main-reopened')
    await loadAppURL(win, appUrl)
    // Drop the startup splash from history, just as on a fresh boot below.
    win.webContents.navigationHistory.clear()
    bootCompleted = true
    return
  }
  // Persist the receipt's first-launch moment before Bun can create state.json. Network delivery
  // runs independently and is retried from disk if this launch is offline or the runtime fails.
  desktopAcquisition.started()
  bootTelemetry.started()
  const win = createWindow()
  try {
    // Dev-UI mode: Vite serves the renderer, so the orchestrator must listen on exactly
    // the port Vite proxies to. scripts/dev.ts picks both and passes them here; the
    // 5174/8787 fallbacks cover a hand-rolled `FREEBUFF_DEV_UI=1 electron .`.
    // Otherwise the Bun server serves the built SPA and any free port will do.
    const devUi = !!process.env.FREEBUFF_DEV_UI
    const devUiPort = Number(process.env.FREEBUFF_DESKTOP_UI_PORT) || 5174
    const devApiPort = Number(process.env.FREEBUFF_DESKTOP_API_PORT) || 8787
    const requestedPort = devUi ? devApiPort : 0
    shellLifetime = await createShellLifetimeServer((error) => {
      console.error(`[shell-lifetime] worker failed: ${error.message}`)
      shellLifetime = null
      shuttingDown = true
      quitApp()
    })
    // must exist before the spawn: its port rides the orchestrator's env, its token the stdin bootstrap
    cdpBridge = await createCdpBridge({
      getWebContents: (id) => webContents.fromId(id),
      browserNative,
    })
    // must also exist before the spawn: its port rides the orchestrator's env, its token the stdin bootstrap.
    //
    // Wrapped, because this sits on the path that gates spawning the orchestrator and every user
    // executes it whether or not they have a single connector. A throw or a hang here is not a
    // degraded feature, it is an app that never finishes starting — which is exactly what happened
    // when the keychain probe blocked boot on a machine whose login keychain was locked. So: bounded,
    // caught, and left null. Both places that read it already guard for null, so the app comes up
    // and only MCP approval is unavailable — the correct thing to lose. The encrypted sign-in store
    // rides this bridge too, so without it the orchestrator falls back to the plaintext token in
    // state.json for that launch (an already-encrypted one stays unread, not deleted) — see
    // src/server/repo/auth-store.ts.
    // The kill switch covers boot too, not only `toolsForTurn` — otherwise disabling MCP still
    // leaves every user executing its startup path.
    mcpConsentBridge = process.env.FREEBUFF_MCP_DISABLED === '1' ? null : await withBoundedBoot('mcp-consent-bridge', () =>
      createMcpConsentBridge({
      // Unavailable on a host with no keychain — a Linux box with no keyring, say. `/secret` then reports
      // that it cannot store anything, which is the right answer: the fallback is not a plaintext
      // file of refresh tokens, it is asking the user to sign in again after a restart.
      secrets: createSecretStore({
        safeStorage,
        file: path.join(app.getPath('userData'), 'mcp-secrets.json'),
      }),
      // The sign-in token. Constructing it touches nothing (same lazy probe), and the orchestrator
      // only asks when it has a plaintext token to migrate or an encrypted one to read, so a fresh
      // profile — a CI runner with a locked keychain — never reaches the keychain at all.
      // `basic_text` is refused: Chromium's no-keyring fallback uses a hardcoded key, and a token
      // there stays honestly in state.json instead (see src/server/repo/auth-store.ts).
      authSecrets: createSecretStore({
        safeStorage: authSafeStorage(),
        file: authSecretsPath(),
        refuseBackends: ['basic_text'],
      }),
      // Freebuff's own window rather than the OS message box — but still drawn by MAIN, which is
      // the part that matters: the app's renderer displays untrusted agent and MCP output, so an
      // approval sharing that DOM would be one XSS away from approving itself. This window is a
      // separate process with its own origin that the transcript cannot reach.
      confirm: createConsentWindow({
        BrowserWindow,
        ipcMain,
        theme: resolvedTheme,
        // A host that cannot open a window must still be able to ask a human; it must never
        // degrade to assuming yes.
        fallback: (parent, options) =>
          parent && !parent.isDestroyed()
            ? dialog.showMessageBox(parent, options)
            : dialog.showMessageBox(options),
      }),
      // On macOS a message box parented to a hidden or minimized window becomes a sheet nobody can
      // see, and this prompt can arrive without the user having asked for anything — so it must be
      // findable. Prefer a visible window; otherwise go unparented, which floats free. Same
      // reasoning as askSync's tolerance of a parent that has gone away.
      getWindow: () => {
        const focused = BrowserWindow.getFocusedWindow()
        if (focused && !focused.isDestroyed() && focused.isVisible()) return focused
        const visible = BrowserWindow.getAllWindows().find(
          (w) => !w.isDestroyed() && w.isVisible() && !w.isMinimized(),
        )
        return visible ?? null
      },
      }),
    )
    // bounded and non-throwing (see signing.cjs), so awaiting it can't stall boot
    signing = await detectSigning({
      platform: process.platform,
      isPackaged: app.isPackaged,
      execPath: process.execPath,
    })
    let port
    try {
      port = await startOrchestrator(requestedPort)
    } catch (error) {
      const orchestratorFailure = error?.orchestratorFailure
      if (orchestratorFailure?.kind === 'timeout') {
        console.error('[orchestrator] startup timed out; retrying once with a clean process')
        port = await startOrchestrator(requestedPort)
      } else if (orchestratorFailure && switchToBaselineRuntime(orchestratorFailure)) {
        try {
          port = await startOrchestrator(requestedPort)
        } catch (retryError) {
          // not the CPU after all: do not pin the baseline on a machine the standard binary runs on
          bunRuntimeMemory().forget()
          throw retryError
        }
      } else {
        throw error
      }
    }
    serverPort = port
    appUrl = devUi ? `http://127.0.0.1:${devUiPort}/` : `http://127.0.0.1:${port}/`
    // Pin the navigation/window-open guards to this exact origin.
    appOrigin = new URL(appUrl).origin
    await loadAppURL(win, appUrl)
    // Native mouse Back bypasses will-navigate and can return to the inert splash.
    win.webContents.navigationHistory.clear()
  } catch (err) {
    // before the dialog, which stalls this process's network
    await bootTelemetry.failed(err)
    if (err?.orchestratorFailure) {
      await showOrchestratorFailure(err.orchestratorFailure, win)
    } else {
      dialog.showErrorBox('Freebuff failed to start', String(err?.message ?? err))
    }
    quitApp()
    return
  }
  // The renderer is up: from here a subprocess launch failure is a mid-session
  // fault, not a failed startup.
  bootCompleted = true
  buildMenu(() => {
    const focused = BrowserWindow.getFocusedWindow()
    if (focused && [...threadWindows.values()].includes(focused)) {
      windowLoads.initiating(focused.webContents, 'menu-reload')
      void focused.loadURL(focused.webContents.getURL())
      return
    }
    if (mainWindow) windowLoads.initiating(mainWindow.webContents, 'menu-reload')
    void mainWindow?.loadURL(appUrl)
  })

  // Ad context wave 2 (COD-757): time since the last wake from sleep. Once per process.
  if (!adResumeClock) {
    try {
      adResumeClock = createResumeClock({ powerMonitor: require('electron').powerMonitor })
    } catch {
      adResumeClock = null
    }
  }
  warmAdContextReader()

  // Start checking for new releases (no-op in dev; see updater.cjs). init() is
  // idempotent, so a macOS dock re-activate that re-runs boot() won't double it.
  updateChecker = updater.init({
    currentVersion: app.getVersion(),
    isPackaged: app.isPackaged,
    releaseFlavor: releaseFlavor(),
    getWindow: () => mainWindow,
    busy: busySignal,
  })

  // after the window, not before: presence is garnish, and boot() re-runs on a dock re-activate
  if (discordClientId && !discordPresence) {
    discordPresence = createDiscordPresence({
      clientId: discordClientId,
      paths: discordIpcPaths(process.platform, process.env),
      connect: (socketPath) => net.createConnection(socketPath),
      enabled: discordEnabled,
      log: (line) => console.error(`[discord] ${line}`),
    })
  }
}

// This machine cannot sandbox, so re-exec with --no-sandbox on the real command
// line — appending the switch from JS is too late to matter (see linux-launch.cjs).
// Checked BEFORE the single-instance lock so this short-lived process never takes
// the lock the replacement is about to need. app.relaunch only records the intent;
// app.exit performs it, skipping before-quit/will-quit — correct here, since
// nothing has been started yet for those handlers to tear down.
if (linuxLaunch.relaunchArgs && linuxLaunch.relaunchExecPath) {
  // execPath is resolved in linux-launch.cjs: $APPIMAGE, not process.execPath,
  // because the latter points inside the /tmp squashfs mount that unmounts the
  // moment we exit — the relaunch would never come back.
  app.relaunch({ execPath: linuxLaunch.relaunchExecPath, args: linuxLaunch.relaunchArgs })
  app.exit(0)
} else if (linuxLaunch.relaunchArgs) {
  // We need to re-exec but have nowhere to re-exec FROM — the AppImage was moved,
  // deleted, or half-replaced by an interrupted update. Relaunching anyway would
  // exit into nothing and the app would vanish without a word, so say it instead.
  // showErrorBox is the one dialog usable before `ready`.
  const { message, detail } = describeSandboxFailure({
    sandbox: linuxLaunch.sandbox,
    sandboxOff: false,
    canRelaunch: false,
  })
  dialog.showErrorBox(message, detail)
  app.exit(1)
}
// Single-instance lock — a second launch focuses the existing window.
else if (!app.requestSingleInstanceLock()) {
  quitApp()
} else {
  app.on('second-instance', (_event, argv) => {
    const labLink = argv.find((arg) => parseLabLink(arg))
    if (labLink) void openLabTestLink(labLink)
    const win =
      mainWindow ?? [...threadWindows.values()].find((w) => !w.isDestroyed())
    if (win) {
      if (win.isMinimized()) win.restore()
      win.focus()
    }
  })

  app.whenReady().then(async () => {
    // A source build must not steal the installed app's OS protocol registration.
    if (app.isPackaged) app.setAsDefaultProtocolClient('freebuff')
    await boot()
    if (pendingLabLink) {
      const value = pendingLabLink
      pendingLabLink = null
      void openLabTestLink(value)
    }
  })

  // A Chromium subprocess that fails to LAUNCH (as opposed to crashing later) is
  // the sandbox symptom this file's preflight exists to prevent: the zygote can't
  // fork, so the GPU process, the network service, and every renderer die in turn
  // and the user gets a dead window with the explanation only on stderr — which a
  // GUI launch throws away. Catch it here and say something.
  //
  // Best-effort by nature: when Chromium decides the GPU process is unusable it
  // aborts the browser process outright ("Goodbye"), and no handler runs at all.
  // The preflight is the actual fix; this is the net under it, and it also covers
  // the machines whose sandbox breaks in a way the sysctl probes don't predict.
  //
  // Scoped to the bootstrap window on purpose. `child-process-gone` covers GPU,
  // Zygote and Utility children for the WHOLE session, and a utility process can
  // fail to fork mid-run for reasons that have nothing to do with the sandbox —
  // memory pressure being the obvious one, in an app that also runs preview
  // <webview>s. Firing this two hours in would put a modal titled "Freebuff
  // failed to start" over a working session, with both buttons ending it. Once
  // the first window has loaded, a launch failure is not a startup failure, so
  // it goes to the log instead.
  let sandboxDialogShown = false
  app.on('child-process-gone', (_event, details) => {
    if (process.platform !== 'linux' || details.reason !== 'launch-failed') return
    if (sandboxDialogShown) return
    if (bootCompleted) {
      console.error(
        `[linux-launch] ${details.type} process failed to launch after startup: ${details.reason}`,
      )
      return
    }
    sandboxDialogShown = true

    // Resolved fresh, not reused from startup: the AppImage can be moved or
    // replaced by an update while the app is running, and a retry button that
    // exits into nothing is worse than no button at all.
    const relaunchExecPath = resolveRelaunchExecPath()
    const { message, detail, canRetryWithoutSandbox } = describeSandboxFailure({
      sandbox: linuxLaunch.sandbox,
      sandboxOff: linuxLaunch.sandboxOff,
      canRelaunch: !!relaunchExecPath,
    })
    const buttons = canRetryWithoutSandbox
      ? ['Relaunch Without Sandbox', 'Quit']
      : ['Show Log', 'Quit']
    const body = `${detail}\n\n(${details.type} process: ${details.reason})`
    // A launch failure this early can land before `ready`, where the dialog
    // module throws — and an exception here would replace the message we came to
    // show with a silent crash, which is the exact failure being fixed.
    // showErrorBox is the one dialog documented as safe before ready; it has no
    // buttons, so the pre-ready path explains and quits rather than offering the
    // retry. Nothing is running yet, so there is nothing to tear down.
    if (!app.isReady()) {
      dialog.showErrorBox('Freebuff failed to start', body)
      app.exit(1)
      return
    }
    let response
    try {
      response = dialog.showMessageBoxSync({
        type: 'error',
        title: 'Freebuff failed to start',
        message,
        detail: body,
        buttons,
        defaultId: 0,
        cancelId: 1,
        noLink: true,
      })
    } catch (err) {
      console.error('[linux-launch] could not show the failure dialog:', err?.message ?? err)
      // quit(), not exit(): same orchestrator-orphaning reason as the retry below.
      quitApp()
      return
    }
    if (response !== 0) {
      quitApp()
      return
    }
    if (canRetryWithoutSandbox) {
      // Re-exec with the switch on argv rather than persisting a "sandbox off"
      // flag: the retry lasts exactly one run, so a single odd failure can never
      // leave this install permanently unsandboxed. A machine that is genuinely
      // broken gets caught by the preflight on the next launch instead.
      // canRetryWithoutSandbox is only true when relaunchExecPath resolved, so
      // this cannot relaunch into a path that no longer exists.
      //
      // quit(), NOT exit(): unlike the startup branch, this handler can run after
      // boot() has spawned the Bun orchestrator, and app.exit skips before-quit —
      // the only place stopOrchestrator() runs. That would strand a live
      // orchestrator on 127.0.0.1 holding its sessions, and the replacement picks
      // a fresh port so nothing would ever collide to make the leak visible.
      // app.relaunch only records the intent, so it still fires after a clean quit.
      app.relaunch({
        execPath: relaunchExecPath,
        args: [...process.argv.slice(1), NO_SANDBOX],
      })
      quitApp()
      return
    }
    try {
      shell.showItemInFolder(path.join(app.getPath('logs'), 'orchestrator-stderr.log'))
    } catch {
      /* the log may not exist yet — the dialog was still the point */
    }
    quitApp()
  })

  app.on('activate', () => {
    if (!mainWindow) boot()
    else {
      if (mainWindow.isMinimized()) mainWindow.restore()
      mainWindow.show()
      mainWindow.focus()
    }
  })

  app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') quitApp()
  })

  let orchestratorStoppedForQuit = false
  let waitingToQuit = false
  app.on('before-quit', (event) => {
    // Includes Quit from the macOS Dock, which bypasses the application menu.
    if (!quitting && !updateChecker?.restartingForUpdate()) {
      event.preventDefault()
      requestQuit()
      return
    }
    quitting = true
    if (orchestratorStoppedForQuit) return
    event.preventDefault()
    if (waitingToQuit) return
    waitingToQuit = true
    // The updater's restart relaunches at once: the orchestrator keeps every paid hour held for the
    // relaunch to adopt, as after a crash, instead of ending it (docs/crash-safety.md). Asked before
    // the stop, which is what starts its shutdown.
    const announced = updateChecker?.restartingForUpdate()
      ? announceUpdateRestart(fetch, appUrl, apiLaunchToken)
      : Promise.resolve(false)
    const stopped = announced.then(() => stopOrchestrator())
    // quitting before the app came up is a launch that never did: a slow (scanned) or stuck start
    void Promise.allSettled([browserNative.close(), stopped, bootTelemetry.failed()]).finally(() => {
      orchestratorStoppedForQuit = true
      quitApp()
    })
  })
  app.on('will-quit', () => {
    discordPresence?.stop()
    void stopOrchestrator()
  })
}
