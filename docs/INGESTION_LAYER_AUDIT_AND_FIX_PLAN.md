# Ingestion Layer Audit And Fix Plan

Created: 2026-04-23  
Scope: extension sidepanel, dashboard upload/search, backend document APIs, worker parser pipeline, Postgres storage, MinIO, Qdrant, and OpenAI embeddings.

## Implementation Status After This Pass

- The two uploaded PDFs in thread `8e04f368-5227-4106-8026-697770c87b7a` were revalidated directly against the live backend pipeline and restored into the local thread after validation.
- Form 16 Part A now contributes employee name `AKANSHA SINHA`, employer `APTUSDATALABS TECHNOLOGIES PRIVATE LIMITED`, and salary TDS `82768.00`; Form 16 Part B contributes PAN `GWPPS0879L`, gross salary `730907.00`, standard deduction `75000.00`, taxable income `655907.00`, rebate `17796.00`, and employer TAN `BLRA20443D`.
- Postgres now stores durable document chunks in `document_chunks`; search uses those chunks before falling back to page text.
- Search for `what is my salary` now returns the Form 16 Part B salary chunk first through `lexical_fallback`.
- `process_immediately=true` now executes inline in the backend instead of enqueueing and racing the background worker, so synchronous uploads/reprocess calls no longer unpredictably return `queued`.
- Thread document lists now collapse stale duplicate `pending_upload` retries, so the dashboard does not show every abandoned retry row for the same file.
- Qdrant/OpenAI embedding generation is still skipped in the current Docker runtime because `ITX_OPENAI_API_KEY` is empty. Once the key is configured, the same chunking path will index to Qdrant with `text-embedding-3-small`.

## 30 Things That Work Today

1. The extension can create or reuse a filing thread after login.
2. Pilot consent auto-grant is wired into sidepanel thread bootstrap.
3. The sidepanel chat can accept file uploads through the attachment control.
4. The dashboard can upload multiple files for a selected thread.
5. `/api/documents/signed-upload` creates a document record and version record.
6. `/api/documents/{document_id}/content` stores uploaded bytes through the document storage abstraction.
7. MinIO can be selected as the document storage backend.
8. Local storage remains available as a fallback backend.
9. Uploaded documents are queued for parsing.
10. `process_immediately=true` can process a document synchronously during upload.
11. PDF, JSON, CSV, text, and generic bytes enter one document pipeline.
12. Existing parsers cover Form 16, Form 16A, AIS JSON, AIS CSV, AIS PDF, TIS, salary slips, interest certificates, health insurance, rent receipts, home loan certificates, ELSS/PPF, and broker capital gains.
13. Parsed normalized facts are stored in `document_extractions`.
14. Page text is stored in `document_pages`.
15. Entities are stored in `document_entities`.
16. Uploaded document versions are tracked in `document_versions`.
17. `list_thread_documents` returns thread-level document status for dashboard and sidepanel and collapses stale duplicate pending retries per file.
18. The agent state can attach processed documents to a thread checkpoint.
19. The extract-facts node can merge normalized fields into canonical tax facts.
20. Fill-plan generation already maps `gross_salary`, employer details, PAN, deductions, tax-paid fields, bank fields, and regime choice into portal selectors.
21. The dashboard shows uploaded files, type, status, latest version, and avoids duplicate stale pending rows for the same file.
22. The sidepanel shows document cards after upload.
23. Qdrant is present in Docker Compose and health-checked.
24. MinIO is present in Docker Compose and health-checked.
25. The embedding service is implemented for OpenAI `text-embedding-3-small`.
26. The semantic-search endpoint exists and returns Qdrant results when embeddings are available.
27. The search endpoint has a lexical fallback.
28. The embedding health endpoint reports whether OpenAI, Qdrant, and storage are configured.
29. Backend auth protects document upload, list, search, and reprocess APIs.
30. The app now parses the two sample PDFs end to end into searchable Form 16 facts with employee name, employer name, salary, and TDS merged into thread tax facts.

## 30 Things That Break Or Are Incomplete

1. The current Docker backend has no OpenAI API key configured, so real embeddings cannot be generated.
2. Documents show `parsed` instead of `indexed` when embeddings are skipped.
3. Before this fix, scanned/image PDFs were decoded as PDF object streams instead of tax text.
4. Before this fix, UUID filenames caused the client to declare `doc_type="unknown"`.
5. Before this fix, `doc_type="unknown"` was treated as a real declaration and blocked auto-classification.
6. Before this fix, classification ran before PDF text extraction and was not rerun after text was available.
7. The two uploaded Form 16 PDFs were stored as `unknown`.
8. The two uploaded Form 16 PDFs had no useful page text for search.
9. Search for "what is my salary" could not match the documents because stored text was PDF stream garbage.
10. Search fallback only searched page text; it did not have a durable chunk table.
11. Chunk metadata was not persisted in Postgres.
12. Re-indexing uploaded documents required manual queue/database intervention.
13. The sidepanel still has no explicit reprocess action for a low-quality or failed document.
14. The extension and dashboard still do not explain why a document is `parsed` instead of `indexed` when embeddings are skipped.
15. Form 16 Part A and Part B uploaded separately can overwrite useful non-zero facts with zero facts.
16. Form 16 parser labels were too narrow for TRACES/CPC OCR text.
17. Form 16 parser could confuse section numbers, row numbers, or tax formula numbers for amounts.
18. OCR on Form 16 Part A can still miss the employee PAN, so the merged identity for these files still depends on Part B for PAN.
19. Form 16B was not recognized.
20. Image file OCR was effectively a byte-decoding fallback, not real OCR.
21. Docker images did not include Tesseract OCR.
22. Docker images did not include pypdf, PyMuPDF, or Pillow.
23. PDF extraction had no native-text-first and OCR fallback ladder.
24. Large multi-page scanned PDFs had no page-level OCR loop.
25. Parser confidence and extraction confidence were not surfaced enough in UI.
26. The ingestion pipeline was too synchronous for large files when `process_immediately=true`.
27. Failed upload attempts can still leave stale rows in the database, although thread document lists now collapse duplicate pending retries in the UI.
28. Qdrant point count is not shown next to document rows.
29. Agent chat does not yet automatically call document search before answering every tax question.
30. The current first-form filing flow still depends on extracted facts matching portal field mappings and portal selectors.

## Validation Notes

- Direct live validation was run against the two PDFs in `/Users/sumansaurabh/Downloads/income-tax-form` inside the Docker backend container.
- Focused automated checks now cover realistic Form 16 identity extraction, indexed-status propagation, and stale pending-upload filtering.
- Running backend document API tests against the shared local Postgres instance truncates `documents` and `agent_checkpoints`; if local manual uploads matter, restore or isolate the database before test runs.

## Use Cases Covered By The Fixed Ingestion Layer

1. Upload Form 16 Part A PDF and extract TDS salary, employer TAN, assessment year, and evidence text.
2. Upload Form 16 Part B PDF and extract gross salary, standard deduction, taxable income, rebate, and PAN.
3. Upload both Form 16 parts and merge non-zero facts without Part B zero values erasing Part A TDS.
4. Search uploaded Form 16 documents for "salary", "standard deduction", "tax deducted", or "PAN".
5. Reprocess already uploaded documents after parser improvements.
6. Upload scanned/image-heavy PDFs and extract text through OCR.
7. Upload native text PDFs and extract text without OCR overhead.
8. Upload image files and extract text through Tesseract.
9. Upload AIS/TIS JSON or CSV and parse through structured parsers.
10. Upload unknown PDFs and classify after extracted text is available.
11. Persist chunks in Postgres for DB search and audit even without OpenAI keys.
12. Generate Qdrant embeddings when `ITX_OPENAI_API_KEY` is configured.
13. Fall back to lexical chunk search when OpenAI or Qdrant is unavailable.
14. Show uploaded document status in dashboard.
15. Show document upload status in sidepanel chat cards.
16. Use extracted facts for salary schedule fill plans.
17. Use extracted tax-paid facts for tax-paid schedule fill plans.
18. Use extracted PAN/name facts for personal-info fill plans where confidence is sufficient.
19. Keep raw uploaded files in MinIO or local storage.
20. Keep document versions for re-uploads.

## Implementation Plan

1. Replace raw PDF byte scraping with pypdf native extraction.
2. Add PyMuPDF rendering for scanned PDFs.
3. Add Tesseract OCR for image-heavy PDF pages and image uploads.
4. Treat `unknown`, `auto`, and `detect` as no declared document type.
5. Reclassify after text extraction.
6. Add Form 16B classification and a minimal Form 16B parser.
7. Improve Form 16 amount extraction for TRACES/CPC layouts.
8. Extract employee PAN from the employee PAN region before falling back to first PAN.
9. Persist chunks into `document_chunks`.
10. Update lexical search to search chunks first.
11. Keep Qdrant/OpenAI semantic search as the primary path when configured.
12. Add document reprocess API.
13. Add dashboard reprocess action.
14. Prevent zero values from overwriting non-zero canonical facts.
15. Add Docker OCR and PDF dependencies.
16. Rebuild backend and worker images.
17. Reprocess the two uploaded PDFs.
18. Verify Postgres document rows become `form16`.
19. Verify document pages contain tax text, not PDF object streams.
20. Verify document chunks contain salary/TDS text.
21. Verify dashboard search for "what is my salary" returns Form 16 evidence.
22. Verify sidepanel search card returns evidence.
23. Verify `tax_facts` includes salary gross, TDS salary, standard deduction, taxable income, and assessment year.
24. Verify fill-plan generation can prepare salary-schedule fields.
25. Add tests for scanned Form 16 OCR path where environment supports Tesseract.
26. Add tests for post-extraction classification from UUID PDF names.
27. Add tests for zero-value merge protection.
28. Add tests for chunk lexical search fallback.
29. Surface embedding health in dashboard later.
30. Move large-file ingestion to async worker-only mode after the pilot sync path is stable.
