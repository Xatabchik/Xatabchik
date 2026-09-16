/* Mini App API client boundary.
 *
 * Runtime implementations are installed on `window` by the <head> bootstrap
 * in app.html so `?token=` is stripped before first paint:
 *   setAuthToken, getAuthToken, removeAuthToken, getTgInitData,
 *   authHeaders, apiFetch
 *
 * This file documents that boundary. Do not change URLs, HTTP methods, or
 * request/response shapes. Later Stage 2 PRs can turn these into exports
 * without rewriting the client.
 */
