# Use Cases

60+ concrete use cases the implemented system can fulfill, grouped by capability. Each use case ends with the primary artifact or outcome the user receives.

## A. Onboarding & session

1. **Install and activate** — user installs the extension; side panel opens only on the official e-Filing portal with a verified-host badge. *Outcome: trust signal + chat ready.*
2. **Device + session binding** — issue a device-scoped token so one device cannot silently act as another. *Outcome: revocable session.*
3. **Consent-first onboarding** — show exact consent text per purpose (upload AIS, fill portal, regime compare); hash + store in `consents`. *Outcome: DPDP-aligned record.*
4. **Resume a paused filing** — user returns days later and the agent reloads the exact LangGraph checkpoint and current portal context. *Outcome: zero-rework resume.*

## B. Portal awareness (read-only copilot)

5. **Explain the current page** — "You're on Schedule S — Salary. You need your Form 16 Part B values here." *Outcome: plain-English step explainer.*
6. **List required inputs for this page** — auto-extracted from the page adapter. *Outcome: checklist before the user starts typing.*
7. **Translate a portal validation error** — agent rewrites a cryptic portal error into an actionable question. *Outcome: faster error recovery.*
8. **Identify the right ITR form** — based on detected income heads and residential status. *Outcome: form recommendation with rationale.*
9. **Flag an unsupported flow** — agent detects foreign assets / complex derivatives and downgrades to guided checklist. *Outcome: explicit "get a CA" handoff.*
10. **Anti-phishing guard** — refuse to operate on any host other than the official portal. *Outcome: no action on lookalike domains.*

## C. Document intake & extraction

11. **Parse AIS (JSON / CSV / PDF)** — prefer structured formats; PDF used as evidence view. *Outcome: AIS lines as canonical facts.*
12. **Parse TIS** — ingest derived values for reconciliation. *Outcome: prefill-aligned starting point.*
13. **Parse Form 16 (Part A + Part B)** — employer, TAN, gross salary, exempt allowances, TDS. *Outcome: salary facts + evidence.*
14. **Parse Form 16A** — TDS on non-salary income. *Outcome: tax-paid entries.*
15. **Parse salary slips** — reconcile gross / deductions / variable pay across months. *Outcome: monthly breakdown.*
16. **Parse interest certificates** — banks / post offices. *Outcome: other-sources facts.*
17. **Parse rent receipts for HRA** — compute exempt HRA with the rules engine. *Outcome: deduction entries + audit.*
18. **Parse home-loan interest certificate** — principal (80C) + interest (Section 24). *Outcome: split entries.*
19. **Parse ELSS / PPF / LIC / tuition receipts** — map to 80C sub-buckets. *Outcome: deduction items.*
20. **Parse health-insurance receipts** — 80D self / parents split with age-based caps. *Outcome: capped deduction values.*
21. **Parse broker capital-gains statements** — STCG/LTCG with ISIN-level evidence. *Outcome: Schedule CG entries.*
22. **OCR fallback on scanned proofs** — only when the text layer fails; confidence recorded. *Outcome: scan-friendly ingestion.*
23. **Reject malicious or unreadable files** — virus scan + sanitization. *Outcome: blocked upload with reason.*
24. **Multi-version documents** — re-upload updated Form 16 without losing prior evidence links. *Outcome: versioned history.*

## D. Reconciliation & mismatch handling

25. **AIS vs Form 16 salary diff** — flagged, explained, routed to a question. *Outcome: resolved or accepted variance.*
26. **AIS vs broker statement diff** — duplicate-trade detection. *Outcome: de-duplicated capital gains.*
27. **AIS vs bank certificate interest diff** — severity-classified. *Outcome: mismatch table with fixes.*
28. **Detect likely under-reporting** — AIS contains an entry not in user docs. *Outcome: forced question before fill.*
29. **Detect likely AIS prefill issue** — user feedback path to override. *Outcome: override with evidence.*
30. **Duplicate-proof detection** — same LIC premium claimed twice. *Outcome: one surviving entry.*

## E. Tax reasoning

31. **Old vs new regime comparison** — deterministic math; regime chosen by user. *Outcome: regime recommendation + number table.*
32. **Eligibility check for ITR-1** — residency, income heads, thresholds. *Outcome: pass/fail with reason list.*
33. **Required-schedule detection** — e.g., Schedule CG triggered by capital-gain facts. *Outcome: mandatory schedules list.*
34. **Deduction caps** — 80C ≤ 1.5L, 80D age-based, 80G qualifying amount, 80TTA/TTB. *Outcome: capped applied values.*
35. **Standard deduction applicability** — salary + pension. *Outcome: auto-applied fact.*
36. **Presumptive income eligibility (44AD/44ADA)** — for ITR-4 in later phase. *Outcome: eligibility verdict.*
37. **Residential-status questionnaire** — day-count + tie-breaker rules (resident / RNOR / NR). *Outcome: status fact.*
38. **Refund / additional-tax estimate** — from canonical facts and rule engine. *Outcome: expected refund or demand.*

## F. Filling the portal (human-in-the-loop)

39. **Batched fill plan** — show every field + value + source before any DOM change. *Outcome: one-tap batch approval.*
40. **Targeted single-field fill** — "Enter 80C = 1,50,000 here." *Outcome: single-field approve → fill.*
41. **Read-after-write** — confirm what the portal actually accepted. *Outcome: reconciled field state.*
42. **Selector-drift recovery** — user clicks target field once to retrain the map. *Outcome: adapter learns mapping.*
43. **Regime toggle with impact preview** — switching old↔new shows the delta before committing. *Outcome: informed regime switch.*
44. **Bank account update** — hard approval gate before changing refund account. *Outcome: recorded approval.*
45. **Inline evidence on every field** — tap a filled value to see the source PDF snippet. *Outcome: full traceability.*
46. **Undo last fill batch** — rollback-friendly action log. *Outcome: one-click undo where the portal allows it.*

## G. Review, submission, verification

47. **Pre-submission summary** — totals, regime, deductions, mismatches, disclosure checks. *Outcome: signed-off summary.*
48. **Explicit submission consent** — exact consent text hashed into `consents`. *Outcome: legally clean audit.*
49. **E-verification handoff** — UI branches for Aadhaar OTP / EVC / net banking / DSC; agent never touches OTPs. *Outcome: user-controlled verification.*
50. **ITR-V + JSON archive** — downloadable filing bundle with evidence. *Outcome: audit-grade artifact.*
51. **Revised return** — thread forks off the filed return with prior context. *Outcome: revision workflow.*
52. **Updated return (ITR-U) support** — later phase; escalation-gated. *Outcome: supported flow when in scope.*

## H. Post-filing & multi-year

53. **Year-over-year comparison** — income, tax, regime, deductions. *Outcome: trend view.*
54. **Next-AY readiness checklist** — "Collect these 6 proofs before July." *Outcome: proactive checklist.*
55. **Notice-response prep (read-only)** — parse a 143(1) intimation and explain it; no automated reply. *Outcome: explainer + suggested response data.*
56. **Refund status tracking** — read-only scrape of status page with user approval. *Outcome: status display.*

## I. CA / reviewer workspace (later phase)

57. **Multi-client list** — CA sees clients with status, mismatches, pending approvals. *Outcome: queue.*
58. **Reviewer sign-off** — CA approves a fill plan on behalf of a client (with client counter-consent). *Outcome: dual-approval trail.*
59. **Bulk export** — audit bundle for a set of clients. *Outcome: compliance-ready archive.*

## J. Compliance, safety, trust

60. **Action-level audit export** — every filled field + source + approval row. *Outcome: user-visible audit.*
61. **Consent revocation** — user revokes a purpose; related data purge queued. *Outcome: enforced retention.*
62. **Retention-driven purge** — raw uploads auto-deleted 30 days post filing. *Outcome: minimized residual data.*
63. **PII-redacted logs** — model transcripts masked before storage. *Outcome: safer observability.*
64. **Anomaly blocking** — sudden off-pattern tool calls or rate spikes are auto-paused. *Outcome: thread quarantine.*
65. **Prompt-injection defense in documents** — document-sourced text cannot issue tool calls; only facts are extracted. *Outcome: safe ingestion.*

## K. Developer / operability

66. **Replay a failed filing** — reload DOM snapshots + checkpoint to reproduce a bug. *Outcome: deterministic debug.*
67. **Adapter hot-swap** — portal change → new adapter version → threads use new version without data loss. *Outcome: zero-downtime updates.*
68. **Rule-version pinning** — a filed return stays reproducible under its original rule set. *Outcome: historical integrity.*
69. **Synthetic persona fixtures** — seed the workers with 50+ canonical personas. *Outcome: CI-grade regression tests.*
70. **Extraction-accuracy dashboards** — per doc type, per parser version. *Outcome: measurable quality.*
