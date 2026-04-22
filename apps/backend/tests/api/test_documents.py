from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.api.documents import (
    DocumentContentUploadRequest,
    DocumentIngestRequest,
    UploadInitRequest,
    ingest_uploaded_document,
    list_thread_documents,
    signed_upload,
    upload_document_content,
)
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool
from itx_backend.security.request_auth import reset_request_auth, set_request_auth
from itx_backend.services.auth_runtime import AuthContext
from itx_backend.services.document_storage import document_storage


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class DocumentsApiTest(unittest.IsolatedAsyncioTestCase):
    def _bind_auth(self, user_id: str) -> None:
        if hasattr(self, "_auth_token") and self._auth_token is not None:
            reset_request_auth(self._auth_token)
        self._auth_token = set_request_auth(
            AuthContext(
                user_id=user_id,
                email=f"{user_id}@example.com",
                device_id=f"device-{user_id}",
                session_id=f"session-{user_id}",
            )
        )

    async def asyncSetUp(self) -> None:
        self._auth_token = None
        self.storage_dir = tempfile.TemporaryDirectory()
        document_storage._root = Path(self.storage_dir.name)
        await close_connection_pool()
        await init_connection_pool()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table document_jobs, document_pages, document_tables, document_entities, document_extractions, document_versions, documents, agent_checkpoints cascade"
            )
        await checkpointer.save(AgentState(thread_id="thread-doc-1", user_id="user-1"))

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table document_jobs, document_pages, document_tables, document_entities, document_extractions, document_versions, documents, agent_checkpoints cascade"
            )
        if self._auth_token is not None:
            reset_request_auth(self._auth_token)
        await close_connection_pool()
        self.storage_dir.cleanup()

    async def test_signed_upload_content_processes_and_attaches_to_thread(self) -> None:
        self._bind_auth("user-1")
        created = await signed_upload(
            UploadInitRequest(
                file_name="form16.txt",
                mime_type="text/plain",
                thread_id="thread-doc-1",
                doc_type="form16",
            )
        )

        uploaded = await upload_document_content(
            created["document_id"],
            created["version_no"],
            created["expires"],
            created["signature"],
            DocumentContentUploadRequest(
                thread_id="thread-doc-1",
                doc_type="form16",
                content_text=(
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

        self.assertEqual(uploaded["status"], "parsed")
        self.assertEqual(uploaded["document_type"], "form16")
        self.assertEqual(len(documents["documents"]), 1)
        self.assertEqual(documents["documents"][0]["status"], "parsed")
        self.assertEqual(documents["documents"][0]["latest_version_no"], 1)
        self.assertEqual(latest_state.tax_facts["pan"], "ABCDE1234F")
        self.assertEqual(latest_state.tax_facts["salary"]["gross"], 1850000.0)
        self.assertEqual(latest_state.tax_facts["tax_paid"]["tds_salary"], 210000.0)

    async def test_signed_upload_returns_indexed_status_when_embedding_stage_succeeds(self) -> None:
        self._bind_auth("user-1")
        created = await signed_upload(
            UploadInitRequest(
                file_name="form16.txt",
                mime_type="text/plain",
                thread_id="thread-doc-1",
                doc_type="form16",
            )
        )

        with patch(
            "itx_workers.pipelines.index_embeddings.index_document_embeddings",
            new=AsyncMock(return_value={"status": "indexed", "chunk_count": 2, "model": "test-model", "dimensions": 8}),
        ):
            uploaded = await upload_document_content(
                created["document_id"],
                created["version_no"],
                created["expires"],
                created["signature"],
                DocumentContentUploadRequest(
                    thread_id="thread-doc-1",
                    doc_type="form16",
                    content_text=(
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

        self.assertEqual(uploaded["status"], "indexed")
        self.assertEqual(documents["documents"][0]["status"], "indexed")

    async def test_list_documents_hides_stale_pending_upload_retries(self) -> None:
        self._bind_auth("user-1")
        first_attempt = await signed_upload(
            UploadInitRequest(
                file_name="retry-form16.txt",
                mime_type="text/plain",
                thread_id="thread-doc-1",
                doc_type="form16",
            )
        )
        second_attempt = await signed_upload(
            UploadInitRequest(
                file_name="retry-form16.txt",
                mime_type="text/plain",
                thread_id="thread-doc-1",
                doc_type="form16",
            )
        )

        pending_documents = await list_thread_documents("thread-doc-1")

        self.assertEqual(len(pending_documents["documents"]), 1)
        self.assertEqual(pending_documents["documents"][0]["document_id"], second_attempt["document_id"])
        self.assertEqual(pending_documents["documents"][0]["status"], "pending_upload")

        await upload_document_content(
            second_attempt["document_id"],
            second_attempt["version_no"],
            second_attempt["expires"],
            second_attempt["signature"],
            DocumentContentUploadRequest(
                thread_id="thread-doc-1",
                doc_type="form16",
                content_text=(
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

        self.assertEqual(first_attempt["document_id"] != second_attempt["document_id"], True)
        self.assertEqual(len(documents["documents"]), 1)
        self.assertEqual(documents["documents"][0]["document_id"], second_attempt["document_id"])
        self.assertEqual(documents["documents"][0]["status"], "parsed")

    async def test_reupload_creates_new_version_and_reconciles_ais_vs_form16(self) -> None:
        self._bind_auth("user-1")
        form16 = await signed_upload(
            UploadInitRequest(
                file_name="form16.txt",
                mime_type="text/plain",
                thread_id="thread-doc-1",
                doc_type="form16",
            )
        )
        await upload_document_content(
            form16["document_id"],
            form16["version_no"],
            form16["expires"],
            form16["signature"],
            DocumentContentUploadRequest(
                thread_id="thread-doc-1",
                doc_type="form16",
                content_text=(
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

        ais = await signed_upload(
            UploadInitRequest(
                file_name="ais.json",
                mime_type="application/json",
                thread_id="thread-doc-1",
                doc_type="ais_json",
            )
        )
        await upload_document_content(
            ais["document_id"],
            ais["version_no"],
            ais["expires"],
            ais["signature"],
            DocumentContentUploadRequest(
                thread_id="thread-doc-1",
                doc_type="ais_json",
                content_text=(
                    '{"pan":"ABCDE1234F","assessmentYear":"2025-26","grossSalary":2100000,'
                    '"tdsSalary":240000}'
                ),
            ),
        )

        latest_state = await checkpointer.latest("thread-doc-1")
        mismatch_fields = {mismatch["field"] for mismatch in latest_state.reconciliation["mismatches"]}
        self.assertIn("salary.gross", mismatch_fields)

        revised = await signed_upload(
            UploadInitRequest(
                document_id=form16["document_id"],
                file_name="form16-revised.txt",
                mime_type="text/plain",
                thread_id="thread-doc-1",
                doc_type="form16",
                reason="revised_form16",
            )
        )
        await upload_document_content(
            revised["document_id"],
            revised["version_no"],
            revised["expires"],
            revised["signature"],
            DocumentContentUploadRequest(
                thread_id="thread-doc-1",
                doc_type="form16",
                content_text=(
                    "Form 16\n"
                    "Employee Name: Alice Example\n"
                    "PAN: ABCDE1234F\n"
                    "Employer Name: Example Technologies Pvt Ltd\n"
                    "Employer TAN: BLRA12345B\n"
                    "Assessment Year: 2025-26\n"
                    "Gross Salary: 2100000\n"
                    "Tax deducted at source: 240000\n"
                ),
            ),
        )

        documents = await list_thread_documents("thread-doc-1")
        latest_state = await checkpointer.latest("thread-doc-1")
        form16_document = next(doc for doc in documents["documents"] if doc["document_type"] == "form16")
        self.assertEqual(form16_document["latest_version_no"], 2)
        self.assertEqual(len(form16_document["versions"]), 2)
        self.assertNotIn("salary.gross", {mismatch["field"] for mismatch in latest_state.reconciliation["mismatches"]})
        self.assertEqual(latest_state.tax_facts["salary"]["gross"], 2100000.0)