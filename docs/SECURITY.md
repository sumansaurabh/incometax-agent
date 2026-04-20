# Security & Compliance

Personal tax data is highly sensitive and is governed in India by the **Digital Personal Data Protection Act, 2023 (DPDP)**. Architecture and controls below follow data-minimization, explicit consent, purpose limitation, encryption, and auditable access.

## 1. Data classification

| Class | Examples | Handling |
|---|---|---|
| P0 — Critical | PAN, Aadhaar-derived IDs, bank account, OTPs | Never log. Encrypted at rest with per-record key. OTPs never stored. |
| P1 — Sensitive | Salary, tax payments, deductions, uploads | Encrypted at rest. Masked in logs. Short retention. |
| P2 — Operational | Session tokens, device fingerprints | Short TTL, revocable. |
| P3 — Non-sensitive | Rule versions, adapter versions, anonymized metrics | Normal handling. |

## 2. Non-negotiables

1. **Official domain only.** Extension host permission is pinned to the verified e-Filing portal. Side panel shows verified-host badge. No action on any other host.
2. **No credential handling.** No storage of portal password, bank credentials, or OTPs. User drives login and e-verification.
3. **No arbitrary JS from model output.** Backend emits only closed-set action DSL; content script rejects anything else.
4. **No cross-tab execution.** Content scripts only run on the tax-portal tab they were bound to.
5. **No screenshot/DOM capture on pages containing OTP / DSC / bank-credential fields** by default.

## 3. Encryption

- TLS 1.2+ everywhere; HSTS on backend hosts.
- Postgres TDE + column-level encryption for P0 fields via envelope encryption.
- Object storage with SSE-KMS and per-file data keys.
- Secrets in a managed secrets manager; rotation policy.
- Client-side WebCrypto wrap for ephemeral extension session state.

## 4. Identity & authorization

- Short-lived access tokens (≤ 15 min) + refresh tokens bound to device + user.
- Row-level security in Postgres by `tenant_id` + `user_id`.
- Reviewer (CA) access requires dual consent (client + reviewer) recorded in `approvals`.
- Admin access is break-glass, logged to an append-only audit sink.

## 5. Consent ledger (DPDP alignment)

- Every purpose is granted separately: `upload_ais`, `fill_portal`, `regime_compare`, `share_with_reviewer`, `retain_beyond_30d`.
- Consent text displayed to the user is hashed into `consents.text_hash`.
- Revocation is first-class — revoking a purpose queues the associated data-purge job.
- Purpose-limited processing: a document uploaded under `upload_ais` cannot be used to train models.

## 6. Retention

| Class | Retention |
|---|---|
| Raw uploaded documents | 30 days post filing unless user pins |
| Extracted canonical facts | 7 years (statutory) |
| Agent checkpoints | 30 days post thread closure |
| Tool-call transcripts | 90 days, PII-redacted |
| Audit trail | 7 years |
| DOM snapshots | 7 days unless tied to an incident |

## 7. Audit trail

Every meaningful event writes a row to `filing_audit_trail` with `rule_version`, `adapter_version`, `actor`, `reason`, and a minimal payload. The trail is append-only; corrections are new rows, not overwrites.

Events include: `consent_granted`, `consent_revoked`, `document_uploaded`, `fact_added`, `fact_verified`, `fill_proposed`, `fill_approved`, `fill_executed`, `validation_error`, `mismatch_flagged`, `submission_approved`, `submitted`, `everified`, `purged`.

## 8. Prompt-injection & document safety

- Document-extracted text is never promoted to instructions. The agent treats all document content as data.
- System prompts include a refusal-to-execute rule for any model output that tries to issue tool calls from document-quoted text.
- Every tool call is schema-validated against the action DSL before the extension accepts it.
- Suspicious documents (executable content, obfuscated scripts in PDFs) are rejected by the sanitizer.

## 9. Anti-phishing

- Extension refuses to attach on lookalike domains; shows a warning banner.
- Background worker verifies TLS chain of the portal host before enabling any write action.
- If the page attempts to redirect to a non-whitelisted host, actions are auto-suspended.

## 10. Abuse & anomaly detection

- Per-user rate limits on tool calls, uploads, and graph transitions.
- Pattern detectors: unusual mid-session geography/device change, sudden high-value fills, off-hour submissions.
- Thread-level auto-pause on anomaly; requires user re-approval to resume.

## 11. Logging discipline

- PII redaction occurs **before** logs leave the process.
- Default log level redacts P0 + P1 fields.
- Model transcripts stored separately with stricter access; retention tied to 90-day rolling window.
- No screenshots of OTP, DSC, or bank-credential fields.

## 12. Backups & disaster recovery

- Postgres PITR enabled; encrypted snapshots.
- Object storage cross-region replication for audit bundles only (not raw P1 docs).
- Quarterly restore drills.

## 13. Third-party / model providers

- PII redaction before any external model call where feasible.
- Per-provider data-processing agreement with no-training guarantee.
- Ability to swap models without schema changes (routing lives in `ai_gateway`).

## 14. Security testing

- Pre-beta external pen-test.
- Quarterly threat-model review (STRIDE per service).
- Fuzzing of document parsers.
- Replay-harness adversarial cases: malformed AIS JSON, injected PDF text, hostile DOM labels.

## 15. Incident response

- 24-hour disclosure SLA to affected users per incident policy.
- Append-only incident log tied to `security_events`.
- Rollback path: per-thread quarantine → per-user suspend → global kill-switch on write actions.

## 16. User-visible trust surface

- Per-field evidence drill-down.
- Downloadable audit bundle with every filing.
- Consent dashboard with per-purpose grant/revoke toggles.
- "Forget me" flow that triggers retention-respecting purge.
