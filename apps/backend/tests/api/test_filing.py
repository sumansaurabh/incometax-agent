from __future__ import annotations

import os
from pathlib import Path
import tempfile
import unittest

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.api.actions import ActionDecision, decision
from itx_backend.api.filing import (
    CompleteSubmissionRequest,
    EVerifyCompleteRequest,
    EVerifyPrepareRequest,
    EVerifyStartRequest,
    FilingSummaryRequest,
    RevisionCreateRequest,
    SubmitPrepareRequest,
    complete_everify,
    complete_submit,
    create_revision,
    filing_state,
    generate_summary,
    prepare_everify,
    prepare_submit,
    start_everify,
)
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool
from itx_backend.services.document_storage import document_storage


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class FilingApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.storage_dir = tempfile.TemporaryDirectory()
        document_storage._root = Path(self.storage_dir.name)
        await close_connection_pool()
        await init_connection_pool()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table revision_threads, filed_return_artifacts, everification_status, submission_summaries, draft_returns, consents, approvals, action_proposals, action_executions, field_fill_history, validation_errors, filing_audit_trail, agent_checkpoints cascade"
            )

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table revision_threads, filed_return_artifacts, everification_status, submission_summaries, draft_returns, consents, approvals, action_proposals, action_executions, field_fill_history, validation_errors, filing_audit_trail, agent_checkpoints cascade"
            )
        await close_connection_pool()
        self.storage_dir.cleanup()

    async def test_summary_submit_and_everify_flow_persists_artifacts(self) -> None:
        await checkpointer.save(
            AgentState(
                thread_id="thread-filing-1",
                user_id="user-1",
                itr_type="ITR-1",
                tax_facts={
                    "assessment_year": "2025-26",
                    "name": "Alice Example",
                    "pan": "ABCDE1234F",
                    "regime": "new",
                    "salary": {"gross": 1600000},
                    "tax_paid": {"tds_salary": 190000},
                    "bank": {"account_number": "1234567890", "ifsc": "HDFC0001234"},
                },
                fact_evidence={
                    "salary.gross": [{"document_type": "form16", "confidence": 0.98}],
                    "bank.account_number": [{"document_type": "cancelled_cheque", "confidence": 0.95}],
                },
                reconciliation={"mismatches": []},
            )
        )

        summary = await generate_summary(FilingSummaryRequest(thread_id="thread-filing-1"))
        self.assertTrue(summary["submission_summary"]["can_submit"])

        prepared = await prepare_submit(SubmitPrepareRequest(thread_id="thread-filing-1", is_final=True))
        approval_id = prepared["pending_approvals"][0]["approval_id"]
        await decision(ActionDecision(thread_id="thread-filing-1", approval_id=approval_id, approved=True))

        submitted = await complete_submit(
            CompleteSubmissionRequest(
                thread_id="thread-filing-1",
                ack_no="ACK-12345",
                portal_ref="PORTAL-REF-9",
            )
        )
        self.assertEqual(submitted["submission_status"], "submitted")
        self.assertEqual(submitted["artifacts"]["ack_no"], "ACK-12345")

        prepared_everify = await prepare_everify(
            EVerifyPrepareRequest(thread_id="thread-filing-1", method="aadhaar_otp")
        )
        everify_approval_id = prepared_everify["pending_approvals"][-1]["approval_id"]
        await decision(ActionDecision(thread_id="thread-filing-1", approval_id=everify_approval_id, approved=True))

        handoff = await start_everify(EVerifyStartRequest(thread_id="thread-filing-1", method="aadhaar_otp"))
        self.assertEqual(handoff["everify_handoff"]["method"], "aadhaar_otp")

        completed = await complete_everify(
            EVerifyCompleteRequest(
                thread_id="thread-filing-1",
                handoff_id=handoff["everify_handoff"]["handoff_id"],
                portal_ref="EVC-REF-001",
            )
        )
        self.assertEqual(completed["submission_status"], "verified")
        self.assertTrue(completed["archived"])

        filing = await filing_state("thread-filing-1")
        self.assertEqual(filing["submission_status"], "verified")
        self.assertEqual(filing["artifacts"]["ack_no"], "ACK-12345")
        self.assertEqual(len(filing["consents"]), 2)
        self.assertEqual(filing["everification"]["status"], "completed")
        self.assertIsNotNone(filing["summary_record"])

        pool = await get_pool()
        async with pool.acquire() as connection:
            artifact_count = await connection.fetchval("select count(*) from filed_return_artifacts where thread_id = $1", "thread-filing-1")
            consent_count = await connection.fetchval("select count(*) from consents where thread_id = $1", "thread-filing-1")
        self.assertEqual(artifact_count, 1)
        self.assertEqual(consent_count, 2)

    async def test_revision_creates_new_thread_record(self) -> None:
        await checkpointer.save(
            AgentState(
                thread_id="thread-filing-2",
                user_id="user-2",
                itr_type="ITR-1",
                tax_facts={
                    "assessment_year": "2025-26",
                    "name": "Bob Example",
                    "pan": "ABCDE1234G",
                },
                submission_summary={
                    "assessment_year": "2025-26",
                    "itr_type": "ITR-1",
                    "can_submit": True,
                },
                filing_artifacts={"ack_no": "ACK-OLD"},
                submission_status="submitted",
            )
        )

        revision = await create_revision(
            RevisionCreateRequest(
                thread_id="thread-filing-2",
                reason="Received revised Form 16",
                revision_number=2,
            )
        )
        self.assertNotEqual(revision["revision_thread_id"], "thread-filing-2")

        latest = await checkpointer.latest(revision["revision_thread_id"])
        self.assertIsNotNone(latest)
        assert latest is not None
        self.assertEqual(latest.revision_context["revision_number"], 2)

        pool = await get_pool()
        async with pool.acquire() as connection:
            revision_count = await connection.fetchval("select count(*) from revision_threads where base_thread_id = $1", "thread-filing-2")
        self.assertEqual(revision_count, 1)