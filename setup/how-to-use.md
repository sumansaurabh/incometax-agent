# How To Use It Locally

This is the shortest realistic local flow once the backend and extension are running.

## Fastest end-to-end path

1. Start backend, Postgres, Redis, and dashboard using [backend-dashboard.md](./backend-dashboard.md)
2. Build and load the extension using [chrome-extension.md](./chrome-extension.md)
3. Open `https://www.incometax.gov.in/`
4. Open the extension side panel
5. Sign in with an email address

At that point the extension binds the device, authenticates with the local backend, and bootstraps a filing thread.

## What to do in the extension

The extension side panel is the main taxpayer workflow.

Typical local usage:

1. Sign in on the device
2. Grant the onboarding consents you want to allow for that thread
3. Let the extension detect the current portal page and fields
4. Review detected details, validation issues, and regime preview
5. Prepare page actions
6. Approve or reject pending actions
7. Execute approved actions
8. Generate a submission summary
9. Prepare submission approval and e-verify handoff if you want to walk the whole path

The side panel also exposes post-filing helpers such as year-over-year comparison, next-AY checklist, notice preparation, and refund status capture.

## What to do in the web dashboard

Open `http://localhost:4173`.

The dashboard is the reviewer or CA view.

Typical local usage:

1. Enter the backend URL, usually `http://localhost:8000`
2. Sign in with an email address
3. Review client queue state, blocking issues, mismatches, and support mode
4. Use `Refresh dashboard` to pull the latest queue state
5. Use `Run replay pipeline` to execute the replay regression batch against stored snapshots

## Useful local endpoints

1. `GET /health`: backend startup and runtime checks
2. `POST /api/auth/login`: local login for extension or dashboard
3. `GET /api/ca/dashboard`: aggregated reviewer dashboard data
4. `POST /api/replay/pipeline`: replay regression batch run

## What is not fully local-productized yet

These are the main limitations you should expect when running locally:

1. The `workers` container is still a readiness stub, not a long-running production worker service
2. The extension assumes the backend is on `http://localhost:8000`
3. The dashboard is useful for operations and replay visibility, but it is still an early-stage ops surface rather than a full multi-user product
4. Some portal coverage and replay coverage are still partial, so not every real-world filing path is production-complete yet

## Sanity checklist

Before you start debugging the app, confirm these first:

1. `http://localhost:8000/health` returns an `ok` or at least non-failing response
2. Postgres is reachable on `localhost:5432`
3. Redis is reachable on `localhost:6379`
4. The extension is loaded from `apps/extension/dist`
5. The portal tab is on `https://www.incometax.gov.in/`
6. The side panel can sign in successfully