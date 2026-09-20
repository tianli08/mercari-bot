# Dashboard state handoff

`DashboardShell` waits for Clerk readiness. With a blank/missing application
API URL it mounts only the unavailable notice and `AccountHome` profile/logout
controls, without requesting a token. `AccountHome` never calls `/auth/me`.

With an API URL, `ApplicationDashboard` owns the single `useDashboardState`
instance. Its React key contains the Clerk user ID, session ID, and explicit
account-retry attempt. A switch, logout, or access retry unmounts the previous
owner, clears its records/selection, and aborts its requests. Resource responses
also check their request scope, so ignored cancellation cannot restore old data.
The existing route layout and proxy still enforce Clerk protection.

The hook checks `/auth/me` before starting the two independent reads. Each
resource distinguishes initial loading (`data: null`), confirmed empty (`[]`),
loaded records, and failure. Refresh failures retain the last successful data
with an error. Selection starts at the lexicographically smallest watchlist ID,
retains a valid selected ID across refreshes, and falls back or clears when the
selected record disappears. Selection is local to the mounted account session.

Later feature components should receive only the props they need from this
owner, rather than instantiate another hook or resource cache:

- `destinations`, `watchlists`, `selectedWatchlist`, and `selectWatchlist(id)`.
- `retryDestinations()` / `retryWatchlists()` for fresh reads. These callbacks
  are stable and cancel earlier reads of the same collection.
- `replaceDestination(saved)` / `replaceWatchlist(saved)` to adopt full
  server-returned records, inserting new IDs and replacing existing IDs.
  They cancel older collection reads. A save does not turn an incomplete or
  failed collection into a successful full read; retry that collection too.
- `getCurrentToken()` for each protected operation. No bearer token is stored.
- `reportAccessFailure(error)` in protected-operation error handlers. It returns
  true for a handled 401/403 or `account_conflict`, clears all tenant records,
  and aborts `accessSignal`. A missing token follows the same session-loss path.
  Other failures belong to the feature/section and must remain visible there.
- `accessSignal` while access is ready. Pass it to child fetches (combine with
  component-specific cancellation when necessary), stop timers on abort, and
  ignore responses after abort/unmount. Mount protected features only while
  `access.status === "ready"`. Do not persist callbacks across owner remounts.

Plans 4.4.4 and 4.4.5 must coordinate keyword edits and monitoring changes in
this same owner with one pending mutation per watchlist ID, shared by both
features. Hold that gate from request start through adopting the server response
and any necessary reconciliation read. A full watchlist response is not safe
against another concurrent full-record response: timestamps and completion
order alone are not a version protocol. The replace callbacks cancel old reads;
they do **not** serialize future mutations. Add the shared gate when the first
mutation feature arrives, and disable conflicting actions while it is held.
Do the same for overlapping destination save/test operations in 4.4.3.

This shell deliberately adds no write endpoints, monitoring controls, polling,
health claims, connection form, or onboarding state.
