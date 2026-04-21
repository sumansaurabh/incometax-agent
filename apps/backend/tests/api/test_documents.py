from __future__ import annotations

import os
import unittest

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.api.documents import (
    DocumentIngestRequest,
    UploadInitRequest,
    ingest_uploaded_document,
    list_thread_documents,
    signed_upload,
)
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class DocumentsApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        await close_connection_pool()
        await init_connection_pool()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("truncate table document_entities, document_extractions, document_versions, documents, agent_checkpoints cascade")
        await checkpointer.save(AgentState(thread_id="thread-doc-1", user_id="user-1"))

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute("truncate table document_entities, document_extractions, document_versions, documents, agent_checkpoints cascade")
        await close_connection_pool()

    async def test_ingest_document_persists_and_attaches_to_thread(self) -> None:
        created = await signed_upload(
            UploadInitRequest(
                file_name="form16.txt",
                mime_type="text/plain",
                thread_id="thread-doc-1",
                doc_type="form16",
            )
        )

        ingested = await ingest_uploaded_document(
            created["document_id"],
            DocumentIngestRequest(
                thread_id="thread-doc-1",
                doc_type="form16",
                raw_text=(
                    "Form 16\n"
                    "Employee Name: Alice Example\n"
                    "PAN: ABCDE1234F\n"
                    "Employer Name: Example Technologies Pvt Ltd\n"
                    "Employer TAN: BLRA12345B\n"
                    "Assessment Year: 2025-26\n"
                    "Gross Salary: 1850000\n"
                    "Tax deducted at source: 210000\n"
                ),
            ),
        )
        documents = await list_thread_documents("thread-doc-1")
        latest_state = await checkpointer.latest("thread-doc-1")

        self.assertEqual(ingested["status"], "parsed")
        self.assertEqual(ingested["document_type"], "form16")
        self.assertEqual(len(documents["documents"]), 1)
        self.assertEqual(documents["documents"][0]["status"], "parsed")
        self.assertEqual(latest_state.tax_facts["pan"], "ABCDE1234F")
        self.assertEqual(latest_state.tax_facts["salary"]["gross"], 1850000.0)
        self.assertEqual(latest_state.tax_facts["tax_paid"]["tds_salary"], 210000.0)