function postMutation(fetchImpl, url, launchId, body) {
  return fetchImpl(url, {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      ...(launchId ? { 'x-freebuff-launch-id': launchId } : {}),
    },
    body: JSON.stringify(body),
  })
}

/** Must equal `launchCookieName` in src/server/http/origin-guard.ts (asserted by the test). */
function launchCookieName(port) {
  return `freebuff_launch_${port}`
}

/**
 * Hand this launch's secret to the app's own windows as a cookie, so the requests the renderer
 * cannot put a header on — its `/api/events` EventSource and the terminal WebSocket — carry it
 * too. The orchestrator requires it on every `/api/` request.
 *
 * Planted by main, into the session only the app's windows use (browser and preview guests get
 * their own partitions), rather than set by the server on a document load: any local process can
 * load the document, so a cookie the server handed out would authenticate nothing.
 *
 * HttpOnly, so no page script — including one injected into the renderer — can read it back;
 * SameSite=Strict and scoped to `/api`; no expiry, so it dies with the session. The name carries
 * the port, since cookies ignore ports and a second instance must not overwrite this one's.
 */
function setLaunchCookie(cookies, port, launchId) {
  return cookies.set({
    url: `http://127.0.0.1:${port}/api/`,
    name: launchCookieName(port),
    value: launchId,
    path: '/api',
    httpOnly: true,
    secure: false,
    sameSite: 'strict',
  })
}

/** Must equal the route in src/server/http/misc.controller.ts. */
const UPDATE_RESTART_PATH = 'api/app/restarting-for-update'
// The quit waits on this before the orchestrator is asked to stop, and Electron only gives that
// ~3s in all, so a slow or dead orchestrator costs the quit this much and no more.
const UPDATE_RESTART_TIMEOUT_MS = 1000

/**
 * Tell the orchestrator that the quit under way is the updater's restart, which relaunches at
 * once, so its shutdown holds every hosted session for the relaunch to adopt instead of ending it.
 * An end retires the rest of the paid hour, and the relaunch would buy it again.
 *
 * Resolves true only when the orchestrator acknowledged it; never rejects, and never outlasts the
 * timeout. Unacknowledged, the quit proceeds as an ordinary one.
 */
function announceUpdateRestart(fetchImpl, appUrl, launchId, timeoutMs = UPDATE_RESTART_TIMEOUT_MS) {
  if (!appUrl) return Promise.resolve(false)
  let timer
  const timeout = new Promise((resolve) => {
    timer = setTimeout(() => resolve(false), timeoutMs)
  })
  const sent = Promise.resolve()
    .then(() => postMutation(fetchImpl, new URL(UPDATE_RESTART_PATH, appUrl), launchId, {}))
    .then((response) => response?.ok === true, () => false)
  return Promise.race([sent, timeout]).finally(() => clearTimeout(timer))
}

module.exports = {
  postMutation,
  launchCookieName,
  setLaunchCookie,
  announceUpdateRestart,
  UPDATE_RESTART_PATH,
}
