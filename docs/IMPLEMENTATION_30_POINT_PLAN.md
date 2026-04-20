# 30-Point Implementation Plan (Executed)

This plan is directly derived from the docs in this repository. Status marks reflect implementation in code scaffold form.

1. Initialize pnpm + uv + Turbo monorepo. Status: Done
2. Create top-level folder structure from FOLDER_STRUCTURE.md. Status: Done
3. Configure root CI pipeline for build/lint/test. Status: Done
4. Create extension MV3 manifest with incometax host restriction. Status: Done
5. Build extension side panel shell UI. Status: Done
6. Add extension background service worker and router. Status: Done
7. Add extension backend connector over WebSocket. Status: Done
8. Add extension secure storage helpers. Status: Done
9. Add extension content script bootstrapping. Status: Done
10. Add extension page detector (read-only phase). Status: Done
11. Add extension field-map and action executors. Status: Done
12. Create backend FastAPI app and health endpoint. Status: Done
13. Implement backend auth API stub. Status: Done
14. Implement backend threads API stub. Status: Done
15. Implement backend documents signed-upload stub. Status: Done
16. Implement backend actions decision API stub. Status: Done
17. Implement backend tax-facts read API stub. Status: Done
18. Implement backend websocket echo channel for extension round-trip. Status: Done
19. Implement LangGraph-style state and graph flow bootstrap->portal_scan->ask_user->archive. Status: Done
20. Implement checkpointer baseline for thread persistence. Status: Done
21. Add telemetry baseline (tracing + metrics). Status: Done
22. Add security baseline (PII redaction + crypto + rate limit utility). Status: Done
23. Add DB layer baseline (session + models + bootstrap migration). Status: Done
24. Implement workers queue and doc pipeline stages. Status: Done
25. Implement workers parser modules for AIS/TIS/Form16/etc. Status: Done
26. Implement workers reconciliation and severity modules. Status: Done
27. Implement canonical tax-schema package (JSON schemas + TS/Py outputs + build scripts). Status: Done
28. Implement action-dsl package (spec + schema + TS/Py outputs). Status: Done
29. Implement portal-adapters package (registry + page adapters + utils). Status: Done
30. Implement deterministic rules-core package and baseline tests, plus infra/test/persona scaffolds. Status: Done

## Notes

- This is an end-to-end implementation scaffold matching all planned capabilities and folder structure.
- Production hardening, legal/tax validation, and full portal-specific selector tuning are iterative steps on top of this implemented baseline.
