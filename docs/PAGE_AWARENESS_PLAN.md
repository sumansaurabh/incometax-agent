# Page-Awareness & Live Context Plan

Date: 2026-04-23
Owner: extension + backend
Status: draft — supersedes the "portal awareness" slice of `docs/IMPLEMENTATION_30_POINT_PLAN.md` items 6–10 and fleshes out use cases B5–B10 + G-class "live help" cases in `docs/USE_CASES.md`.

## 1. The incident this plan is closing

User screenshot (2026-04-23, 12:47 PM IST):

- URL: `https://eportal.incometax.gov.in/iec/foservices/#/dashboard/fileIncomeTaxReturn`
- Page: **File Income Tax Return** with **Select Assessment year = 2025-26** and the **Select Filing Type** dropdown open and focused.
- User asks: *"what should I select in the dropdown?"*
- Agent reply: *"I can see the portal page but it is showing as 'unknown' — the extension hasn't detected a specific form page yet, so I can't see which dropdown you are referring to."*

This is a competence failure. The agent has network access, a content script in the page, an LLM, and an adapter catalog — but none of the three layers admits it can **look at the screen the user is staring at**. That is the minimum bar for any copilot.

## 2. Why it currently fails

Tracing `content → background → sidepanel → backend`:

| # | File | Behaviour |
|---|---|---|
| 1 | `apps/extension/src/content/index.ts:152` | Content script calls `buildPageContext()` **once** at inject time. |
| 2 | `apps/extension/src/content/page-detector.ts:9` | `detectPage` → `detectAdapter(doc)`; if no adapter scores ≥ `MIN_ADAPTER_SCORE` (`packages/portal-adapters/src/base.ts:29` = 8), returns `{ page: "unknown", fields: [], validationErrors: [] }`. |
| 3 | `packages/portal-adapters/src/catalog.ts:38-47` | `file-return-start` adapter is the one that *should* match this screen, but its DOM signatures are `select[name='assessment_year']`, `select[name='filing_type']`, `select[name='filing_mode']`. The SPA does not use those `name` attributes, so the score never reaches 8. |
| 4 | `apps/extension/src/content/index.ts:157-161` | Re-detection only happens on a full-document load. The portal is a hash-routed SPA; navigating from `/dashboard` → `/dashboard/fileIncomeTaxReturn` does **not** re-run detection. |
| 5 | `apps/extension/src/sidepanel/App.tsx:519-521` | Sidepanel attaches `pageContext?.page ?? "unknown"` and `pageContext?.portalState ?? null` to every chat message. No refresh is triggered by "user is about to send a message". |
| 6 | `apps/backend/src/itx_backend/services/portal_context.py` | The server keeps only the latest snapshot per thread and expects the extension to push it. It does not itself observe the DOM. |
| 7 | `apps/backend/src/itx_backend/agent/tools/portal_context.py` | `get_portal_context` tool exists and is well-shaped, but it can only return what step 1 captured — so when the adapter returns `unknown`, the tool returns `page_type: unknown` and no fields, and the LLM has nothing to reason from. It does not include dropdown option text, focused field, or a DOM mini-snapshot. |

Summary: page awareness lives entirely in **step 2 pattern-matching a static adapter at inject time**. Any SPA navigation, any adapter miss, any late-rendered dropdown, any focused-element question — all of them collapse into the same `unknown` sinkhole. The LLM never gets to see the screen.

## 3. Design targets

A good copilot passes these five tests simultaneously. All five must be green.

1. **Always-fresh context.** The agent always has a snapshot that is ≤ 1 s old at the moment the user sends a message — regardless of SPA navigation or dynamic rendering.
2. **Focus-aware.** The snapshot identifies the element the user is looking at: the focused field, the open dropdown, and the option labels currently visible.
3. **Graceful degradation.** When no adapter matches, the agent still has `url`, `page_title`, the visible H1, the primary form's field labels, and any open dropdown's options to reason over. `unknown` stops being a dead end.
4. **Re-detection on every turn.** A chat-send triggers a fresh snapshot request; the agent sees the page at the moment of the question, not at the moment of page load.
5. **Self-repair.** When detection fails, the extension records the URL + DOM signature and the backend can ship a new adapter without requiring a release.

## 4. Architecture — the four new primitives

### 4.1 `PageObserver` (content script)

Replaces the one-shot `buildPageContext()` call.

- Runs a `MutationObserver` on `document.body` with `subtree: true, childList: true, attributes: true`, debounced to 250 ms.
- Listens to `hashchange`, `popstate`, `pushState` / `replaceState` (monkey-patched) for SPA navigation.
- Listens to `focusin`, `focusout`, `click` on `select`, `[role=combobox]`, `[role=listbox]`, and ARIA-expanded triggers — so the focused field and its open dropdown are always known.
- Maintains a single in-memory `currentSnapshot`; any change re-runs `detectPage` + `captureFocus` + `captureVisibleDropdown`.
- Exposes two messages: (a) `page_context_updated` pushed to background whenever the snapshot changes (debounced), (b) `snapshot_page_context` request-response for on-demand capture.

### 4.2 Richer snapshot shape

Today's snapshot (`apps/extension/src/content/index.ts:111`) has `{page, title, url, fields, validationErrors, portalState}`. The new shape adds five things the LLM actually needs:

```ts
type PageSnapshot = {
  page: string;                 // adapter key or "unknown"
  pageDetection: {              // NEW
    score: number;
    runnerUp?: { key: string; score: number };
    matchedSignals: string[];   // which DOM signatures / keywords fired
  };
  title: string;
  url: string;
  route: string;                // NEW — hash or path segment normalized
  headings: string[];           // NEW — H1 / H2 / step-indicator text
  focusedField: {               // NEW
    selector: string;
    tag: "input" | "select" | "textarea" | "button" | "other";
    label: string | null;
    value: string | null;
    role: string | null;
    ariaExpanded: boolean;
  } | null;
  openDropdown: {               // NEW — survives even when the <select> is an ARIA listbox
    triggerSelector: string;
    label: string | null;
    options: Array<{ value: string | null; label: string; selected: boolean }>;
  } | null;
  fields: FieldSchema[];        // existing adapter-driven field list
  portalState: {...};           // existing; now includes `openDropdown`
  validationErrors: ValidationError[];
  capturedAt: string;           // NEW — ISO timestamp, used for freshness checks
};
```

### 4.3 `page_detector` v2

Two layers:

1. **Adapter match** — unchanged in principle, but with three fixes: (a) URL-path matching (not just substring of normalized URL), (b) per-adapter `urlPatterns: RegExp[]` with a heavy score weight, (c) lowering `MIN_ADAPTER_SCORE` is not the answer — instead, a match is confirmed by *any one of* `urlPattern`, two `domSignatures`, or two `textClues`.
2. **Fallback detector** — when adapters miss, synthesize a "generic" snapshot from: the `<h1>` text, the active step-indicator text (portal uses numbered breadcrumbs), the first `<form>`'s field labels, and any open dropdown. The page key becomes `generic:<slugified-heading>`; the agent can still answer "what should I select".

### 4.4 Backend tool upgrades

- `get_portal_context` (`apps/backend/src/itx_backend/agent/tools/portal_context.py`) already exists and is correctly named. Extend its summarizer to surface `focused_field`, `open_dropdown`, and `headings`. Drop the `available: false` sink when `page_type == "unknown"` but `fields` or `open_dropdown` is non-empty — that's a usable context.
- Add `refresh_portal_context` tool that requests a live snapshot from the extension before answering. The extension side is already wired via `snapshot_active_page` in `apps/extension/src/background/router.ts:250`.
- The agent's system prompt must instruct: *"before answering any question that refers to 'this page', 'the dropdown', 'this field', 'the form', or 'this button', call `get_portal_context` first; if `captured_at` is older than 5 seconds call `refresh_portal_context`."*

## 5. The 30 use cases

Each case describes a user utterance, the minimum page-awareness primitive required, the current outcome, and the target outcome. The grouping mirrors the architecture above — cases 1–10 establish the snapshot pipeline, 11–20 cover the conversational surface, 21–30 cover recovery, learning, and SPA edge cases.

> **Coverage rule.** After this plan lands, every one of these 30 utterances must produce a **useful, page-specific** answer. Anything still producing a generic "I can't see which page you are on" answer is a bug and must be triaged under the same plan.

### A. The snapshot pipeline (1–10)

1. **"What should I select in this dropdown?"** — user has a `<select>` open on the Filing Type page. *Primitive: `openDropdown` + focused field.* Today: `unknown`. Target: agent reads the 3 visible options, recommends `139(8A) - Updated Return` only if the user's assessment-year window and ITR-U reason-code warrant it; otherwise asks the one clarifying question that distinguishes them.
2. **"Which assessment year applies to me?"** — user is on the same page with AY dropdown present. *Primitive: field list + current values.* Target: agent cross-references the filing date and user's latest completed FY.
3. **"Why is Continue disabled?"** — *Primitive: form field completeness + validation errors + focused-field.* Target: agent names the field(s) still empty or invalid, by label.
4. **"What does this error mean?"** — *Primitive: `validationErrors` + nearest field.* Target: plain-English rewrite + the exact user action that clears it.
5. **"Am I on the right page to file ITR-U?"** — *Primitive: page_type or, when `unknown`, the fallback heading detector.* Target: yes/no with the adapter key and the route the user should be on if no.
6. **"What fields are required here?"** — *Primitive: adapter's required-flag field list.* Target: checklist of every required field with current fill state.
7. **"I don't understand 'Residential Status'."** — *Primitive: focused field label → glossary.* Target: per-field explainer keyed off the field's `key` in the adapter schema.
8. **"What did I just select?"** — user changed a dropdown and is unsure. *Primitive: `openDropdown.selectedOption` + field history.* Target: echo the current value and what it implies.
9. **"Read the page to me."** — accessibility/screen-reader style. *Primitive: headings + labels + values.* Target: ordered summary of the form state.
10. **"Is this the last step?"** — *Primitive: step indicator from `headings` + page adapter meta.* Target: progress ("step 2 of 5") with the remaining steps named.

### B. Conversational surface (11–20)

11. **"Select '139(8A) - Updated Return' for me."** — *Primitive: openDropdown option labels + action DSL.* Target: propose a single `select` action with the option's actual value, route through approval as with any other action.
12. **"Fill everything you already know."** — *Primitive: page fields + tax-facts + fill-plan.* Target: standard `propose_fill`, but the page-awareness layer supplies `page_type` rather than relying on the stale inject-time value.
13. **"What's the difference between these two options?"** — user hovering a dropdown with ambiguous labels. *Primitive: openDropdown options + external knowledge.* Target: option-by-option comparison with decision criteria specific to the user.
14. **"Was this field prefilled?"** — *Primitive: field value + fill-plan provenance.* Target: "Yes, from Form 16 uploaded 2026-04-21" or "No, the portal prefilled it".
15. **"Undo my last change on this page."** — *Primitive: portal_state_before/after on last action.* Target: restore the prior value via the existing action DSL.
16. **"Is this page safe to submit?"** — *Primitive: required-field completeness + validation errors + rule checks.* Target: green-light or the exact blocker(s).
17. **"Explain what this page does."** — *Primitive: adapter key + canonical copy.* Target: one-paragraph explainer tied to the detected adapter.
18. **"Where is the 80C field?"** — user on a different page. *Primitive: adapter catalog + navigation.* Target: tell them the correct page and offer to navigate.
19. **"What happens if I leave this blank?"** — *Primitive: focused field's `required` flag + downstream rule dependencies.* Target: concrete consequence (validation error on next step, wrong tax calc, etc.).
20. **"Why is this value different from my Form 16?"** — *Primitive: field value + tax-facts + reconciliation service.* Target: diff reasoning.

### C. Recovery, learning, and SPA edge cases (21–30)

21. **SPA route change after inject-time** — user navigates `/dashboard → /dashboard/fileIncomeTaxReturn`. *Primitive: `PageObserver` hashchange + pushState hooks.* Target: snapshot updates within 500 ms; agent never sees a stale page_type.
22. **Dropdown opens after inject-time** — the user clicks a `<select>` that was off-screen during inject. *Primitive: MutationObserver + focus capture.* Target: `openDropdown` populated before the next chat turn.
23. **Adapter miss on a known page (the screenshot case)** — the `file-return-start` adapter's DOM signatures don't match the real portal. *Primitive: adapter self-scoring + drift reporter.* Target: the fallback detector yields a usable generic snapshot **and** the miss is logged to `selector_drift` with the current DOM signatures so the adapter can be updated without a release.
24. **Adapter ambiguity** — two adapters score close together. *Primitive: `pageDetection.runnerUp`.* Target: agent picks top adapter but mentions the ambiguity when asked "what page am I on?".
25. **New portal route we've never seen** — e.g., a new Grievances sub-page. *Primitive: fallback detector + `generic:<heading>` key.* Target: agent can still answer "what is this page for" from headings + visible labels; route is queued for adapter authoring.
26. **Selector drift mid-session** — a field that was previously fillable stops matching. *Primitive: action-runner reports selector failure → recovery node (`apps/backend/src/itx_backend/agent/nodes/recovery.py`).* Target: the observer supplies the new DOM around the field label, recovery node proposes a remap, user confirms.
27. **Stale snapshot** — user keeps the side panel open while idling, then sends a message after 10 minutes. *Primitive: `capturedAt` freshness check.* Target: sidepanel or backend triggers `refresh_portal_context` before answering if `capturedAt` is > 5 s old.
28. **Modal / overlay pages** — portal opens a modal (e.g., session-expiry warning). *Primitive: topmost-interactive-element detector.* Target: snapshot reflects the modal, agent warns the user before proposing any action on the obscured page.
29. **Iframe-embedded sub-pages** — some portal steps are rendered in iframes. *Primitive: content script match across all iframes via `all_frames: true` in the manifest + frame-aware snapshot.* Target: snapshot merges same-origin iframe fields under a `frame_context` entry.
30. **Cross-tab switches** — user has two portal tabs open and switches between them. *Primitive: background listens to `chrome.tabs.onActivated` and re-requests snapshot from the newly active trusted tab.* Target: the sidepanel's pageContext always reflects the tab currently in front.

## 6. Implementation phases

Phase boundaries are conservative so each phase is shippable and testable.

### Phase 1 — Observer + fresher snapshots (cases 21, 22, 27, 30)

- Replace the one-shot `buildPageContext()` call with `PageObserver` inside `apps/extension/src/content/index.ts`.
- Add focus + dropdown capture helpers (new file `apps/extension/src/content/observer.ts`).
- Hook SPA navigation (hash / pushState).
- Extend `PageSnapshot` shape; update `apps/extension/src/sidepanel/backend.ts` and `apps/backend/src/itx_backend/services/portal_context.py` to accept the new fields.
- Add `capturedAt` freshness check in `App.tsx:handleSend` — if > 5 s old, call `refresh_portal_context` before sending.

### Phase 2 — Fallback detector + headings (cases 3, 4, 5, 17, 23, 25)

- Add `apps/extension/src/content/fallback-detector.ts` that walks the DOM when no adapter matches.
- Extend `get_portal_context` tool summarizer to include `headings` and `open_dropdown`; drop the `available: false` shortcut when those are present.
- Update the agent's system prompt with the "always check portal context" rule.

### Phase 3 — Dropdown understanding (cases 1, 2, 8, 11, 13)

- Add a Action DSL verb `select_option_by_label` and expose it via `propose_fill` when the agent knows only the label but not the value.
- Verify `openDropdown.options` are captured for native `<select>` **and** ARIA `role="listbox"` (common in Angular Material and the portal's custom components).

### Phase 4 — Drift telemetry + self-repair (cases 23, 26)

- When `pageDetection.score < MIN_ADAPTER_SCORE` but URL matches a known portal route, push a `selector_drift_report` to the backend with the normalized DOM structure (first 4 KB of the primary form).
- Backend writes to the existing `selector_drift` table (or equivalent) so the team can auto-generate adapter patches.

### Phase 5 — Iframes + ambiguity + modals (cases 24, 28, 29)

- Enable `all_frames: true` in the manifest; merge same-origin iframe snapshots.
- Add top-most-modal detection (z-index + pointer-events sampling).
- Surface `pageDetection.runnerUp` in the `get_portal_context` output.

## 7. Acceptance tests

Each of these must pass before we close this plan.

- **AT-1 (screenshot case):** On `/dashboard/fileIncomeTaxReturn` with the Filing Type dropdown open, `get_portal_context` returns `page_type ∈ {file-return-start, generic:file-income-tax-return}`, `open_dropdown.options` has ≥ 3 entries including `139(8A) - Updated Return`, and the agent's reply names the dropdown and recommends or clarifies without asking "which page are you on".
- **AT-2 (SPA navigation):** Navigate dashboard → File ITR → back, without reloading; the snapshot's `url` and `page_type` update within 500 ms of `hashchange` for each transition.
- **AT-3 (focus capture):** Click the PAN field on the login page; within 250 ms, `focused_field.selector` resolves to the PAN input and `focused_field.label` is "PAN / Aadhaar".
- **AT-4 (fallback):** Force-disable all adapters; on any portal page with a visible `<h1>` and a `<form>`, the snapshot still yields a non-empty `headings` array and at least one field label.
- **AT-5 (freshness):** Open the side panel, wait 10 minutes, then ask "what's on this page" — the answer is based on a snapshot with `capturedAt` newer than the user's message timestamp.
- **AT-6 (drift):** Rename one `select[name]` in a dev build of the portal; observe a `selector_drift_report` emitted with the new attribute and the old adapter key.

## 8. Out of scope (intentionally)

- Visual screenshots of the page. (The DOM is sufficient; screenshots add OCR cost and privacy surface.)
- LLM-driven adapter authoring. (Phase 4 only reports drift; adapter patches remain human-reviewed.)
- Cross-origin iframes. (The portal uses same-origin frames; cross-origin is blocked by the web platform regardless.)
- Keystroke-level capture. (We capture focus and values, not every keystroke. Consent scope already covers this.)

## 9. Cross-references

- `docs/USE_CASES.md` — cases B5–B10 are upgraded by this plan; cases 1–10 above should be added to the file under a new "Live page help" section.
- `docs/IMPLEMENTATION_30_POINT_PLAN.md` items 6–10 — this plan is the detailed execution of those five.
- `apps/extension/src/content/index.ts:152` — primary edit site for Phase 1.
- `apps/extension/src/content/page-detector.ts:9` — primary edit site for Phase 2.
- `packages/portal-adapters/src/catalog.ts` — needs URL-pattern fields for every adapter as part of Phase 2.
- `apps/backend/src/itx_backend/agent/tools/portal_context.py` — summarizer extension for Phase 1 + Phase 3.
- `apps/backend/src/itx_backend/services/portal_context.py` — accept and persist the enriched snapshot shape for Phase 1.

## 10. Screenshot fallback (Phase 6)

The DOM pipeline above is the primary channel — it covers ~28 of the 30 use cases. Two classes of question genuinely need pixels, and for those we add an **agent-invoked screenshot tool** with strict gating.

### 10.1 When screenshots are the right answer

- A user asks about something that is **rendered but not in the DOM as text** — an embedded PDF preview, a chart, a captcha image, a rendered ITR-V seal.
- The **adapter miss is total** — no H1, no form, the fallback detector also yielded nothing useful. Pixels let the LLM at least read off-screen labels.
- The user explicitly refers to visual layout: "the red box at the top", "where is the button that looks like X".

### 10.2 Architecture

- **Transport:** `chrome.tabs.captureVisibleTab({ format: "jpeg", quality: 70 })` in the background service worker. Viewport only — no `chrome.debugger` banners, no full-page stitching.
- **Trust gate:** capture is allowed only when the active tab passes the existing `classifyTrust()` check in `apps/extension/src/background/router.ts:28` (i.e. a verified `*.incometax.gov.in` host). A `lookalike` or `unsupported` tab short-circuits with an error.
- **Consent gate:** new consent purpose `screen_capture`, copy-approved and hashed like every other purpose in the catalog. The agent must see a granted consent for this purpose before the tool is callable.
- **Size budget:** max 1600 px on the long edge, JPEG quality 70, single image per tool call. The tool rejects calls that would exceed ~400 KB of base64.
- **Freshness:** the screenshot is **not** pushed proactively on every turn. It is only captured when the LLM calls `capture_viewport`.

### 10.3 Tool contract

Backend registers a tool `capture_viewport`:

```
name: capture_viewport
description:
  Capture a JPEG screenshot of the visible portion of the user's e-Filing portal tab.
  Use ONLY when: (a) the DOM snapshot from get_portal_context is insufficient
  (empty or irrelevant), or (b) the user is asking about a visual element
  (chart, image, rendered PDF, captcha, visual layout). Do NOT call this for
  form field, dropdown, or text questions — get_portal_context already has those.
  Returns { image: { media_type, data (base64) }, captured_at, viewport: {width, height} }.
input_schema:
  type: object
  properties:
    reason: { type: string, description: "why a screenshot is needed (one sentence)" }
  required: [reason]
```

The agent's system prompt gains one line: *"Default to `get_portal_context`. Only call `capture_viewport` when the DOM context is insufficient for a visual question, and include a `reason` that names the visual element you need to see."*

### 10.4 Pipeline

1. LLM calls `capture_viewport(reason=...)`.
2. Backend tool handler looks up the thread's device/session, posts a `capture_screenshot` request down the existing websocket connector (`apps/extension/src/background/connector.ts`) — same channel that carries `run_actions`.
3. Background service worker receives the request, runs the trust check, runs `chrome.tabs.captureVisibleTab()`, and returns the data URL.
4. Backend wraps the bytes as an Anthropic-compatible image content block and returns it as the tool result.
5. LLM sees the image alongside its other tool results and answers the user.

### 10.5 Redaction

The portal header strip shows the user's name and PAN. We do **not** attempt server-side redaction in Phase 6 — the image is the user's own screen, shown to their own agent, under explicit `screen_capture` consent. If a reviewer ever needs the screenshot, it stays in the thread's encrypted audit trail under the same retention rules as parsed documents.

### 10.6 Acceptance tests (additions)

- **AT-7 (fallback fires):** With adapters disabled and `get_portal_context` returning an empty DOM snapshot, asking "what's on this page" triggers the LLM to call `capture_viewport` once; the image returns within 1.5 s.
- **AT-8 (trust gate):** Switching the active tab to `google.com` and invoking the tool returns a `trust_denied` error without firing `captureVisibleTab`.
- **AT-9 (consent gate):** A user who has not granted `screen_capture` receives a tool error telling the agent to request consent before retrying.
- **AT-10 (no over-fire):** On the screenshot case from §1 (DOM snapshot already has `openDropdown` populated), the LLM does NOT call `capture_viewport` — the DOM answer is sufficient. This is enforced by evals, not just by prompt.
