Static Archive fullstack app.

Searches Mercari for archive fashion listings (Carol Christian Poell, Boris Bidjan Saberi, Margiela, etc.) and posts matches to Discord. Each user signs up on the dashboard, sets up watchlists of keywords, and gets alerts sent to their own Discord webhooks.

Everything runs with [uv](https://docs.astral.sh/uv/) from `backend/`:

```bash
# scraper worker
uv run python -m src.main

# API, dev mode with reload
uv run uvicorn src.api.app:app --reload

# API, host/port from settings
uv run python -m src.api_main
```

The web app lives in `web/` (Node 22, npm). API-dependent behavior expects the backend running above. The public landing page lives in `web/src/app/(marketing)/`.

```bash
cd web
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL; default is the local API
npm install
npm run dev                  # http://localhost:3000
npm run build                # production build
```

## Currently INFRA is being developed.

https://www.archivestatic.com/

## Authentication

Clerk handles sign up, login, email verification, password recovery, and sessions.
The login page is `/login`, signup is `/signup`, and the protected account page
is `/dashboard`. Use the profile menu to manage passwords and signed-in devices.
MongoDB stores application accounts, watchlists, destinations, and alerts.

For local setup, authenticate the Clerk CLI and link the same development app
in both services:

```bash
clerk auth login
cd web
clerk env pull --app <application-id> --instance dev
cd ../backend
clerk env pull --app <application-id> --instance dev --file .env.clerk
```

The frontend needs `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY`.
Set `NEXT_PUBLIC_API_BASE_URL` (normally `http://localhost:8000/api/v1`) when the
application backend is available. Without it, Clerk sign-in and profile management
work independently; no application API requests or MongoDB provisioning occur.
The backend reads `CLERK_PUBLISHABLE_KEY` and `CLERK_SECRET_KEY` from its ignored
`.env.clerk` file or the process environment. Its existing MongoDB and worker
configuration is still required. Restart the API after changing configuration.

The browser sends the short-lived Clerk session token as an `Authorization:
Bearer` header. The backend verifies its signature, issuer, expiry, session
status, and authorized origin before resolving the application account. Keep
`CLERK_AUTHORIZED_PARTIES` and `API_CORS_ORIGINS` set to explicit frontend
origins (JSON arrays; locally `["http://localhost:3000"]`). Never expose a
secret key in a `NEXT_PUBLIC_` variable. An optional `CLERK_JWT_KEY` can provide
the signing public key; otherwise the SDK fetches and caches Clerk's keys.

Existing users must sign up with Clerk using their existing email. The first
verified Clerk session links an unlinked MongoDB account without changing its
ID or saved data. Subsequent requests resolve by Clerk user ID; an email match
cannot transfer an already-linked account. Suspended accounts remain blocked.
Existing password hashes are preserved but no longer read, and new accounts
store no password. Old session cookies and recovery links no longer work.
Authentication email is sent by Clerk; the backend has no email-provider or
password configuration.

Before deploying, configure a Clerk production instance and matching keys in
both services. Set `API_ENVIRONMENT=production` and both origin lists to the
actual HTTPS frontend origins, such as `https://www.archivestatic.com`. Include
`https://archivestatic.com` only if the frontend is also served there. Local
setup uses development keys and does not configure or deploy production.

Frontend builds require both Clerk keys in the hosting environment. Vercel
production builds require production Clerk keys. The optional API URL must use
HTTPS and point to a deployed server in production. These checks stop an unconfigured build
before it replaces the live site; a successful build alone does not verify the
runtime configuration, DNS, or external services. Run the deployment checks with
`cd web && node --test tests/deployment-config.test.mjs`.

Complete Clerk production DNS, certificates, and Google OAuth credentials before
promoting a deployment. Use separate development and production application
databases, or explicitly migrate existing Clerk account mappings: users have
different Clerk IDs in each instance. Check the public homepage and login page
after deployment, then verify a complete sign-in. Once the backend is deployed,
set its URL in the frontend environment and verify account provisioning through it.
