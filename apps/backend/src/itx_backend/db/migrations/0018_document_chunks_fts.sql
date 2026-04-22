-- Adds a Postgres FTS column + GIN index for BM25-like keyword retrieval
-- over document_chunks. Used alongside the Qdrant dense index by the
-- hybrid retriever (dense + BM25 -> RRF -> Cohere rerank).

alter table document_chunks
  add column if not exists fts tsvector
  generated always as (to_tsvector('english', coalesce(chunk_text, ''))) stored;

create index if not exists idx_document_chunks_fts on document_chunks using gin (fts);

-- Helper index for the thread+doc_type prefilter that the retriever applies
-- before ranking. Keeps the BM25 scan bounded per thread.
create index if not exists idx_document_chunks_thread_doc on document_chunks(thread_id, document_id);
