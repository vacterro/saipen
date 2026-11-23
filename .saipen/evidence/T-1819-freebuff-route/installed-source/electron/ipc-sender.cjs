'use strict'

/**
 * Is this IPC message from the app's own top-level document?
 *
 * A handler that hands out a secret or acts on the renderer's behalf has to
 * ask, because the preload is not the only way into ipcMain: a subframe, or a
 * window that ended up on another origin, can send on the same channel. Both
 * are already prevented elsewhere (off-origin navigation is denied, webviews
 * and subframes get no preload). This check keeps a gap in either of those
 * from becoming a handed-over secret.
 *
 * @param {{ senderFrame?: { url?: string } | null, sender?: { mainFrame?: unknown } | null }} event
 * @param {(url: string) => boolean} isAppUrl
 */
function isTrustedAppSender(event, isAppUrl) {
  const frame = event?.senderFrame
  if (!frame || frame !== event?.sender?.mainFrame) return false
  return typeof frame.url === 'string' && isAppUrl(frame.url)
}

/**
 * The value a `sendSync` request for the API launch token gets back: the
 * token for the app's own document, `null` for anything else. Always a
 * value — a synchronous IPC with no `returnValue` leaves the sender hanging.
 *
 * @param {Parameters<typeof isTrustedAppSender>[0]} event
 * @param {(url: string) => boolean} isAppUrl
 * @param {string | null | undefined} token
 */
function apiTokenReply(event, isAppUrl, token) {
  return isTrustedAppSender(event, isAppUrl) ? (token ?? null) : null
}

module.exports = { apiTokenReply, isTrustedAppSender }
