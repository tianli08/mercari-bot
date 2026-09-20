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
  are stable and cancel earlier reads of the same collection. They return true
  only for a successful current read. Destination refreshes are blocked while
  a destination mutation holds the shared gate.
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

`DiscordConnectionPanel` and `useDiscordConnection` implement 4.4.3. The panel
uses the owner's metadata, token and access callbacks. It enables writes only
after the complete destination collection loads successfully. Each explicit
save, replacement or test acquires `beginDestinationMutation()` and calls its
returned release callback in `finally`. A synchronous gate prevents duplicate
clicks before React rerenders. All destination writes are serialized, including
writes to different IDs, so an ambiguous write's collection reconciliation
cannot overwrite another pending mutation. Watchlist reads remain independent.

`destinationMutationPending` disables destination refresh and conflicting
controls. `reconcileDestinations()` is reserved for the active mutation: it may
read while the gate is held. Ambiguous create/update responses trigger that read
without retrying the write. A failed reconciliation leaves the collection in an
error state; the user must successfully refresh before another write. Refreshed
metadata cannot prove which secret was stored, and the UI says so.

Webhook URLs exist only in temporary form/request state. Inputs are masked,
never prefilled from metadata, and cleared after successful or ambiguous saves.
Cancel/unmount discards form state. API responses are projected to public
metadata; feature errors use fixed copy rather than server details. No browser
request goes to Discord, and mount/refresh/save never sends a test automatically.
Tests use the backend verification endpoint once per explicit click and keep
the latest action result separate from historical `verified_at`. Successful
replacement clears the prior URL's test result and adopts returned metadata.
All mutation responses are ignored after panel unmount or account-access loss.

The dashboard still adds no monitoring controls, polling, health claims, or
onboarding state. Saved destination IDs are ready for 4.4.4 watchlist creation.
