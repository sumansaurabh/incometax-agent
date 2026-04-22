# IncomeTax Agent — Sidepanel Redesign & Infrastructure Plan

> **Created:** 2026-04-22  
> **Status:** Draft  
> **Goal:** Transform the extension sidepanel from a broken, form-heavy consent screen into a chat-first conversational UI, add document ingestion via embeddings (Qdrant + MinIO + OpenAI), and make the product feel like a polished pilot.

---

## Current State Assessment

### What Exists Today
1. **Extension sidepanel (`App.tsx`)** — 1,480-line monolith component with 40+ state variables. After login, the first thing a user sees is the `ConsentOnboardingPane` — a wall of checkboxes with categories, scopes, `depends_on` metadata, and consent legalese. Below it: `DetectedDetailsPane`, `SupportPane`, `ChatPane`, `PendingActionsPane`, `SubmissionPane`, `PostFilingPane`, `EvidencePane` — all dumped vertically with no navigation, no visual hierarchy.
2. **ChatPane** — 31 lines. A bare `<input>` + `<button>` + dump of `messages[]` as `<p>` tags. No chat bubbles, no timestamps, no typing indicator, no message types (user vs. agent vs. system), no markdown rendering.
3. **ConsentOnboardingPane** — Lists every consent item with raw JSON scope output like `documents: ["ais","tis","form16","proofs"]`. Required consents are pre-checked but still displayed as a form the user must manually submit.
4. **Backend** — FastAPI with PostgreSQL, Redis, document parsers (Form 16, AIS, TIS, etc.), an agent graph (LangGraph-style), and a document pipeline. **No vector database, no embeddings, no semantic search.**
5. **docker-compose.yml** — PostgreSQL, Redis, backend, workers, web-dashboard. **No Qdrant, no MinIO.**
6. **Document storage** — Local filesystem (`LocalDocumentStorage` class) with HMAC-signed uploads. No object storage.
7. **Web Dashboard** — CA (Chartered Accountant) operations dashboard. Vanilla TypeScript, no React. Shows client queue, replay pipeline, ops alerts.

### What's Broken / Missing
- The sidepanel opens to a consent form, not a chat — users see bureaucratic checkboxes instead of a "How can I help?" prompt.
- No chat-first UX — chat is buried below 5 other panes.
- No document upload from sidepanel — users can't drag-and-drop or upload PDFs.
- No embeddings / vector search — documents are parsed but not semantically indexed. Agent can't search across document content.
- No MinIO — documents stored on local filesystem, won't scale.
- No Qdrant — no vector database for embeddings.
- No OpenAI embeddings integration.
- The UI has zero styling — raw HTML elements, no design system, no spacing, no color palette.

---

## Part 1: UI Fixes — 40 Points to Make It a Chat Screen

### A. Chat-First Architecture (Points 1–10)

**1. Make chat the primary view after login**  
Remove `ConsentOnboardingPane` from the default view. After login, the user lands directly on a full-screen chat interface. The first message from the agent is: *"Hi! I'm your IncomeTax filing assistant. Type 'File my income tax return' to get started."*

**2. Auto-grant all consents silently for pilot**  
On thread creation, call `grantOnboardingConsents` with ALL required + optional purposes automatically. No consent UI during pilot. Store a `pilotMode: true` flag.

**3. Redesign ChatPane as the main container**  
ChatPane becomes the full-height, full-width primary surface. All other panes (evidence, actions, submission) become contextual cards that appear INSIDE the chat flow as rich message types.

**4. Add proper chat message types**  
Define message types: `user`, `agent`, `system`, `error`, `action-card`, `document-card`, `evidence-card`, `approval-card`. Each renders with distinct styling.

**5. Add chat bubbles with proper alignment**  
User messages: right-aligned, blue background. Agent messages: left-aligned, gray background. System messages: centered, muted text. Action cards: full-width with borders.

**6. Add timestamps to messages**  
Every message shows a relative timestamp ("just now", "2 min ago"). Group messages by date.

**7. Add typing indicator**  
When waiting for agent response, show animated dots ("Agent is thinking...") at the bottom of the chat.

**8. Add message input improvements**  
- Auto-growing textarea instead of single-line input
- Send on Enter, newline on Shift+Enter
- Send button with arrow icon
- Disabled state while agent is processing

**9. Add welcome message with quick actions**  
On new thread, show welcome card with buttons:
- "File my income tax return"
- "Upload documents"
- "Check my refund status"
- "Compare tax regimes"

**10. Persist chat history**  
Store messages in `chrome.storage.local` keyed by `threadId`. Restore on sidepanel reopen.

### B. Remove Clutter & Simplify Layout (Points 11–20)

**11. Remove ConsentOnboardingPane from visible UI**  
Delete the pane from the render tree. Consent is auto-granted in pilot mode. Keep the backend API for future use.

**12. Remove DetectedDetailsPane from default view**  
Portal field detection details are noise for the user. Show them only when the agent explicitly references them (as a chat card).

**13. Remove SupportPane from default view**  
CA handoff and quarantine controls belong in the CA dashboard, not the user's chat. Surface only via agent messages when relevant.

**14. Remove PendingActionsPane from default view**  
Fill plans, approvals, and executions should appear as interactive cards inside the chat, not as a permanent sidebar section.

**15. Remove SubmissionPane from default view**  
Submission summary, e-verification, and artifact downloads should be chat cards triggered by the agent workflow.

**16. Remove PostFilingPane from default view**  
Year-over-year, refund status, and notice preparation appear as chat responses, not always-visible panels.

**17. Remove EvidencePane from default view**  
Evidence/facts viewer becomes a modal or expandable card triggered from chat messages.

**18. Add a minimal header bar**  
Slim header with: app icon, "IncomeTax Agent" title, user email (truncated), and a settings gear icon (for sign-out, thread management).

**19. Add a settings drawer**  
Slide-out drawer from the gear icon containing: sign out, current thread ID, trust status, and (future) consent management.

**20. Add proper empty state**  
When no thread exists yet, show a clean onboarding screen with the app logo and "Sign in to start filing" — not the current cluttered form.

### C. Visual Design & Polish (Points 21–30)

**21. Add a CSS design system / tokens**  
Define CSS custom properties: `--color-primary`, `--color-bg`, `--color-surface`, `--color-text`, `--color-muted`, `--radius`, `--spacing-*`. Apply consistently.

**22. Use a professional color palette**  
Primary: `#1a73e8` (trust blue). Background: `#f8f9fa`. Surface: `#ffffff`. Text: `#202124`. Error: `#d93025`. Success: `#188038`.

**23. Add proper typography**  
Font: system font stack (`-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, ...`). Heading sizes: h1=20px, h2=16px, h3=14px. Body=13px. Muted=11px.

**24. Add proper spacing and padding**  
Messages have 12px padding, 8px gap. Chat container has 16px side padding. Cards have 12px internal padding with 1px border.

**25. Style the login form**  
Center the login form vertically. Add the app logo above it. Clean input styling with focus states. Proper error message styling.

**26. Add message animations**  
New messages slide in from bottom with a subtle fade. Typing indicator pulses.

**27. Add scroll behavior**  
Auto-scroll to bottom on new messages. Show "scroll to bottom" button when user scrolls up. Maintain scroll position when viewing history.

**28. Add proper loading states**  
Global loading spinner during initialization. Skeleton placeholders for chat while connecting. Button loading states with spinner.

**29. Add error message styling**  
Errors appear as red-bordered cards in chat with a retry button, not as plain text dumped into the message array.

**30. Add responsive layout for sidepanel width**  
Sidepanel width varies 300-500px. Ensure chat layout adapts. Use `min-width: 0` and `overflow-wrap: break-word` to prevent overflow.

### D. Chat Intelligence & Rich Messages (Points 31–40)

**31. Add document upload in chat**  
Paperclip/attach icon in message input bar. Opens file picker for PDF, images, CSV. Shows upload progress as a chat card. Triggers backend document pipeline.

**32. Add drag-and-drop file upload**  
Drop zone overlay on the entire chat area. Accepts PDF, PNG, JPG, CSV. Visual feedback during drag.

**33. Add rich agent response cards**  
Agent can send structured cards: tax summary card, regime comparison card, evidence fact card, approval request card — all rendered inside the chat flow.

**34. Add inline approval buttons**  
When agent requests approval (fill plan, submission), show approve/reject buttons directly in the chat card instead of a separate pane.

**35. Add clickable evidence links**  
When agent references a source document, show clickable chips that expand to show the evidence snippet and confidence score.

**36. Add markdown rendering in agent messages**  
Agent responses can include bold, lists, tables, code blocks. Use a lightweight markdown renderer.

**37. Add copy-to-clipboard on agent messages**  
Long-press or hover to show "Copy" button on any agent message.

**38. Add message status indicators**  
Sent (single check), delivered (double check), error (red exclamation). Shows under each user message.

**39. Add thread management**  
"New conversation" button in settings drawer to start a fresh filing thread. Shows list of past threads.

**40. Add real-time agent updates via WebSocket**  
Replace polling with WebSocket connection to `/api/ws` for live agent status updates, typing indicators, and push messages.

---

## Part 2: Infrastructure & Backend — Document Ingestion Pipeline

### Infrastructure Additions (docker-compose.yml)

**41. Add Qdrant to docker-compose**  
```yaml
qdrant:
  image: qdrant/qdrant:v1.13.2
  ports:
    - '6333:6333'
    - '6334:6334'
  volumes:
    - qdrant-data:/qdrant/storage
  healthcheck:
    test: ['CMD', 'curl', '-f', 'http://localhost:6333/healthz']
    interval: 10s
    timeout: 5s
    retries: 5
```

**42. Add MinIO to docker-compose**  
```yaml
minio:
  image: minio/minio:latest
  command: server /data --console-address ":9001"
  environment:
    MINIO_ROOT_USER: itxadmin
    MINIO_ROOT_PASSWORD: itxadmin123
  ports:
    - '9000:9000'
    - '9001:9001'
  volumes:
    - minio-data:/data
  healthcheck:
    test: ['CMD', 'curl', '-f', 'http://localhost:9000/minio/health/live']
    interval: 10s
    timeout: 5s
    retries: 5
```

**43. Add named volumes**  
```yaml
volumes:
  qdrant-data:
  minio-data:
```

**44. Update backend and workers to depend on Qdrant + MinIO**  
Add `depends_on` entries with health checks for both new services.

**45. Add new environment variables**  
```
ITX_QDRANT_URL=http://qdrant:6333
ITX_QDRANT_COLLECTION=tax_documents
ITX_MINIO_ENDPOINT=minio:9000
ITX_MINIO_ACCESS_KEY=itxadmin
ITX_MINIO_SECRET_KEY=itxadmin123
ITX_MINIO_BUCKET=itx-documents
ITX_OPENAI_API_KEY=${ITX_OPENAI_API_KEY:-}
ITX_EMBEDDING_MODEL=text-embedding-3-small
ITX_EMBEDDING_DIMENSIONS=1536
```

### MinIO Object Storage (Points 46–50)

**46. Create MinIO storage backend**  
New `services/minio_storage.py` implementing the same interface as `LocalDocumentStorage` but using MinIO's S3-compatible API via the `minio` Python SDK.

**47. Replace LocalDocumentStorage with MinIO**  
Update `document_storage` singleton to use MinIO in production, keep local as fallback for dev without Docker.

**48. Auto-create MinIO bucket on startup**  
On backend startup, check if `itx-documents` bucket exists, create it if not. Set bucket policy for internal access.

**49. Migrate document upload flow to MinIO**  
Update `DocumentService.create_upload` to generate MinIO presigned URLs instead of HMAC-signed local paths.

**50. Add document download via MinIO presigned URLs**  
Update `filingArtifactUrl` and evidence document downloads to use MinIO presigned GET URLs.

### Embedding Pipeline (Points 51–60)

**51. Create embedding service**  
New `services/embedding_service.py`:
- Uses OpenAI `text-embedding-3-small` model (8191 token context, very cost-effective)
- Batch embedding support (up to 2048 inputs per call)
- Async with retry logic
- Returns `List[List[float]]`

**52. Create chunking strategy module**  
New `workers/pipelines/chunking.py`:
- **Sliding window chunker**: 512 tokens with 64 token overlap
- **Section-aware chunker**: Splits on section headers (Part A, Part B, Schedule, etc.)
- **Table-aware chunker**: Keeps table rows together, embeds table context
- **Semantic chunker**: Groups sentences by topic similarity
- Auto-selects strategy based on document type (Form 16 = section-aware, AIS = table-aware, free-text = sliding window)

**53. Create Qdrant vector store client**  
New `services/qdrant_client.py`:
- Collection management (create, delete, check)
- Point upsert with payload metadata
- Filtered search (by thread_id, doc_type, category)
- Scroll/pagination for large result sets
- Uses `qdrant-client` Python SDK

**54. Create document indexing pipeline**  
New `workers/pipelines/index_embeddings.py`:
- Receives parsed document text from existing `document_pipeline.py`
- Applies chunking strategy
- Generates embeddings via OpenAI
- Stores in Qdrant with metadata:
  ```python
  {
      "thread_id": str,
      "document_id": str,
      "doc_type": str,  # form16, ais, tis, etc.
      "chunk_index": int,
      "chunk_text": str,
      "page_number": int | None,
      "section_name": str | None,
      "file_name": str,
      "created_at": str,
  }
  ```

**55. Integrate indexing into existing document pipeline**  
After `process_document()` succeeds in `document_pipeline.py`, trigger `index_embeddings()` as the next pipeline stage. Add it to the worker queue.

**56. Create semantic search API endpoint**  
New endpoint `POST /api/documents/search`:
```json
{
  "thread_id": "...",
  "query": "What is my total salary income?",
  "top_k": 5,
  "doc_types": ["form16", "ais"]  // optional filter
}
```
Returns ranked chunks with scores, source document info, and highlight text.

**57. Wire agent to use semantic search**  
Update the agent graph nodes (`extract_facts`, `reconcile`, `missing_inputs`, `list_required_info`) to call the semantic search endpoint instead of relying only on structured parsed data.

**58. Add re-indexing support**  
When a document is re-uploaded (new version), delete old Qdrant points for that `document_id` and re-index. Handle versioning cleanly.

**59. Add embedding health check**  
New endpoint `GET /api/documents/embedding-health`:
- Reports Qdrant collection stats (point count, segments)
- Reports embedding model status
- Reports MinIO connectivity

**60. Add batch embedding worker**  
For bulk re-indexing: a worker job that processes all documents for a thread, chunks them, and indexes in batch (up to 2048 embeddings per OpenAI call for efficiency).

---

## Part 3: Chat-Agent Integration (Points 61–70)

**61. Create chat API endpoint**  
New endpoint `POST /api/chat/message`:
```json
{
  "thread_id": "...",
  "message": "File my income tax return for the current year",
  "context": {
    "page": "dashboard",
    "portal_state": {}
  }
}
```
Returns streaming agent response.

**62. Add chat message persistence**  
Store chat messages in PostgreSQL table `chat_messages`:
```sql
CREATE TABLE chat_messages (
  id UUID PRIMARY KEY,
  thread_id TEXT NOT NULL,
  role TEXT NOT NULL,  -- 'user', 'agent', 'system'
  content TEXT NOT NULL,
  message_type TEXT DEFAULT 'text',  -- 'text', 'card', 'action', 'document'
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**63. Add agent intent detection**  
When user says "File my income tax return", agent:
1. Checks what documents are uploaded
2. Searches embeddings for required info
3. Lists missing information
4. Asks user to upload missing documents
5. Shows progress as chat cards

**64. Add document-aware chat responses**  
Agent can answer questions like "What is my HRA claim?" by searching embeddings, finding the relevant chunk from Form 16, and presenting the answer with source citation.

**65. Add WebSocket chat channel**  
Extend existing `/api/ws` with a chat channel for real-time message streaming. Agent responses stream token-by-token.

**66. Connect extension chat to WebSocket**  
Replace `chrome.runtime.sendMessage` chat flow with direct WebSocket connection from sidepanel to backend.

**67. Add file upload from chat**  
When user clicks attach, upload file to MinIO via presigned URL, then send a chat message with the document reference. Agent auto-triggers document pipeline.

**68. Add chat history pagination**  
Load last 50 messages initially, load more on scroll-up. API supports cursor-based pagination.

**69. Add agent status messages**  
During long operations (document parsing, embedding generation), agent sends status updates: "Parsing your Form 16...", "Extracting tax facts...", "Almost done..."

**70. Add error recovery in chat**  
When an operation fails, agent explains what went wrong in plain English and suggests next steps, instead of dumping error strings.

---

## Part 4: Dashboard Integration (Points 71–80)

**71. Add document upload to web dashboard**  
Upload area in web dashboard where user/CA can drag-and-drop PDF documents. Files go to MinIO, trigger document pipeline.

**72. Add uploaded documents list in dashboard**  
Table showing all uploaded documents for a thread: file name, type, status (processing/indexed/error), upload date, page count.

**73. Show document processing status**  
Real-time status: "Uploaded" -> "Parsing" -> "Extracting facts" -> "Generating embeddings" -> "Indexed"

**74. Add document search in dashboard**  
Search box to semantically search across all uploaded documents for a thread. Uses the same Qdrant search API.

**75. Add document viewer in dashboard**  
Click a document to view its content: parsed text, extracted facts, and the raw PDF (via MinIO presigned URL).

**76. Show embedding stats in dashboard**  
Per-thread: number of documents indexed, total chunks, embedding coverage percentage.

**77. Add bulk document upload**  
Select multiple files at once. Progress bar for batch upload. All files queued for processing.

**78. Add document type auto-detection**  
When uploading, auto-classify document type (Form 16, AIS, TIS, bank statement, etc.) using the existing `classify.py` pipeline.

**79. Add document deletion**  
Delete a document: removes from MinIO, deletes Qdrant points, removes from PostgreSQL. Shows confirmation dialog.

**80. Add document re-process button**  
Re-trigger the full pipeline (parse -> extract -> embed) for a document. Useful when pipeline is updated.

---

## 20 Use Cases the Product Will Cover

### Core Filing Use Cases
1. **UC-01: One-command ITR filing** — User says "File my income tax return for AY 2025-26" and the agent orchestrates the entire flow.
2. **UC-02: Document upload & auto-parse** — User uploads Form 16, AIS, TIS, bank statements. Agent auto-parses, extracts facts, and indexes for search.
3. **UC-03: Intelligent missing info detection** — Agent searches indexed documents, identifies what's missing (e.g., "I can't find your home loan interest certificate"), and asks user to upload.
4. **UC-04: Semantic document Q&A** — User asks "What was my total salary?" and agent searches embeddings to find the answer with source citation.
5. **UC-05: Auto-fill ITR form** — Agent generates a fill plan from extracted facts and executes approved fills on the e-Filing portal.

### Tax Advisory Use Cases
6. **UC-06: Old vs. New regime comparison** — Agent compares both regimes using actual numbers from uploaded documents and recommends the optimal choice.
7. **UC-07: Deduction optimization** — Agent identifies unclaimed deductions (80C, 80D, HRA) by cross-referencing documents.
8. **UC-08: Mismatch resolution** — When AIS and Form 16 don't match, agent highlights discrepancies and suggests resolution.

### Submission & Post-Filing Use Cases
9. **UC-09: Pre-submission validation** — Agent validates all fields before submission, explains any blocking issues in plain English.
10. **UC-10: E-verification handoff** — Agent guides user through e-verification (Aadhaar OTP, net banking, etc.).
11. **UC-11: Refund status tracking** — Agent checks and reports refund processing status.
12. **UC-12: Notice response preparation** — When user receives an IT notice, agent prepares a response checklist.

### Multi-Year & Revision Use Cases
13. **UC-13: Year-over-year comparison** — Agent compares current filing with previous year, highlights changes.
14. **UC-14: Revised return preparation** — Agent helps file a revised/updated return if errors are discovered.

### CA/Professional Use Cases
15. **UC-15: CA handoff package** — Agent prepares a review package for the CA with all documents, facts, and recommendations.
16. **UC-16: Multi-client dashboard** — CA dashboard shows all clients, their filing status, and pending actions.

### Document Intelligence Use Cases
17. **UC-17: Cross-document fact reconciliation** — Agent reconciles facts across multiple documents (e.g., salary in Form 16 vs. AIS) and flags conflicts.
18. **UC-18: Smart document search** — Search across all uploaded documents using natural language queries.
19. **UC-19: Document-backed evidence trail** — Every tax fact shows its source document, page, and confidence score.

### Platform Use Cases
20. **UC-20: Conversational tax filing** — The entire filing process happens through natural conversation in the chat interface, with the agent proactively guiding the user through each step.

---

## Implementation Priority

### Phase 1: UI Transformation (Points 1–40) — Week 1-2
- Chat-first layout, auto-grant consents, styling, message types
- This alone makes the product usable

### Phase 2: Infrastructure (Points 41–50) — Week 2-3
- Qdrant + MinIO in docker-compose
- MinIO storage backend replacement
- Basic document upload from chat

### Phase 3: Embedding Pipeline (Points 51–60) — Week 3-4
- Chunking strategies, OpenAI embeddings, Qdrant indexing
- Semantic search API

### Phase 4: Chat-Agent Intelligence (Points 61–70) — Week 4-5
- Chat API, WebSocket streaming, intent detection
- Document-aware responses

### Phase 5: Dashboard (Points 71–80) — Week 5-6
- Document management in web dashboard
- Search, viewer, bulk upload

---

## Technical Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Embedding model | OpenAI `text-embedding-3-small` | 8191 token context, $0.02/1M tokens, good quality |
| Vector DB | Qdrant | Open source, Docker-ready, filtered search, payload storage |
| Object storage | MinIO | S3-compatible, Docker-ready, presigned URLs, free |
| Chunking | Multi-strategy (section, table, sliding window) | Tax docs have varied structure |
| Chat transport | WebSocket | Real-time streaming, typing indicators |
| UI framework | React (existing) | Already used in extension |
| Styling | CSS custom properties + component classes | Lightweight, no build dependency |

---

## Files to Create/Modify

### New Files
- `apps/extension/src/sidepanel/components/ChatBubble.tsx`
- `apps/extension/src/sidepanel/components/ChatInput.tsx`
- `apps/extension/src/sidepanel/components/MessageCard.tsx`
- `apps/extension/src/sidepanel/components/WelcomeScreen.tsx`
- `apps/extension/src/sidepanel/components/SettingsDrawer.tsx`
- `apps/extension/src/sidepanel/components/FileUpload.tsx`
- `apps/extension/src/sidepanel/components/TypingIndicator.tsx`
- `apps/extension/src/sidepanel/styles/chat.css`
- `apps/extension/src/sidepanel/styles/tokens.css`
- `apps/backend/src/itx_backend/api/chat.py`
- `apps/backend/src/itx_backend/services/embedding_service.py`
- `apps/backend/src/itx_backend/services/qdrant_client.py`
- `apps/backend/src/itx_backend/services/minio_storage.py`
- `apps/workers/src/itx_workers/pipelines/chunking.py`
- `apps/workers/src/itx_workers/pipelines/index_embeddings.py`

### Modified Files
- `apps/extension/src/sidepanel/App.tsx` — Complete rewrite to chat-first layout
- `apps/extension/src/sidepanel/panes/ChatPane.tsx` — Full redesign
- `apps/extension/src/sidepanel/backend.ts` — Add chat API, WebSocket, file upload
- `infra/docker/docker-compose.yml` — Add Qdrant, MinIO, volumes
- `apps/backend/src/itx_backend/main.py` — Register new routers
- `apps/backend/src/itx_backend/config.py` — New settings
- `apps/backend/src/itx_backend/services/documents.py` — MinIO integration
- `apps/workers/src/itx_workers/document_pipeline.py` — Add embedding stage
- `apps/web-dashboard/src/main.ts` — Add document upload section
