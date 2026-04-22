# Chrome Extension

This guide explains how to build and load the local Chrome extension.

## What the extension expects

1. A backend running on `http://localhost:8000`
2. Chrome or Chromium with Developer Mode enabled
3. The real income tax portal open at `https://www.incometax.gov.in/`

The extension already has host permissions for:

1. `https://www.incometax.gov.in/*`
2. `http://localhost:8000/*`
3. `http://127.0.0.1:8000/*`

The backend URL is hard-coded in the extension source today as `http://localhost:8000`, so run the backend on that port unless you also change the extension code.

## Build the extension

From the repo root:

```bash
pnpm --dir apps/extension build
```

This creates the unpacked extension bundle in:

```text
apps/extension/dist
```

If you are actively editing the extension, you can also run typecheck separately:

```bash
pnpm --dir apps/extension exec tsc --noEmit
```

## Load the unpacked extension in Chrome

1. Open `chrome://extensions`
2. Turn on Developer Mode
3. Click `Load unpacked`
4. Select the folder `apps/extension/dist`

## Open the side panel

The extension is a Manifest V3 side panel app.

Use it like this:

1. Open `https://www.incometax.gov.in/`
2. Click the extension icon in Chrome
3. Open the side panel for `IncomeTax Agent`

If Chrome does not pin the action automatically, pin the extension from the toolbar first.

## Sign in locally

The extension sign-in flow is local and lightweight:

1. Enter an email address in the side panel
2. Click `Sign in on this device`
3. The extension calls `POST /api/auth/login` on the local backend
4. A filing thread is created or resumed for that browser device

There is no extra frontend env file for the extension right now. The only hard dependency is that the backend is reachable on `http://localhost:8000`.

## Common local issues

1. `authorization_required` or login failures usually mean the backend is not running on `localhost:8000`
2. Empty side panel state usually means you are not on `https://www.incometax.gov.in/`
3. If you rebuild the extension, click `Reload` on `chrome://extensions`