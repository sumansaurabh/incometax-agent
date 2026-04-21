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
    ConsentGrantItem,
    ConsentGrantRequest,
    ConsentRevokeRequest,
    EVerifyCompleteRequest,
    EVerifyPrepareRequest,
    EVerifyStartRequest,
    FilingSummaryRequest,
    ItrUConfirmRequest,
    ItrUPrepareRequest,
    OfficialArtifactAttachmentRequest,
    RefundStatusCaptureRequest,
    RevisionCreateRequest,
    NextAyChecklistRequest,
    NoticePreparationRequest,
    YearOverYearRequest,
    attach_official_artifact,
    consent_catalog,
    confirm_itr_u,
    get_itr_u_state,
    prepare_itr_u,
    SubmitPrepareRequest,
    capture_refund_status,
    complete_everify,
    complete_submit,
    create_revision,
    filing_state,
    generate_summary,
    grant_consents,
    next_ay_checklist,
    prepare_notice,
    prepare_everify,
    prepare_submit,
    regime_preview,
    RegimePreviewRequest,
    revoke_consent,
    start_everify,
    year_over_year,
)
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool
from itx_backend.security.request_auth import reset_request_auth, set_request_auth
from itx_backend.services.document_storage import document_storage
from itx_backend.services.auth_runtime import AuthContext


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class FilingApiTest(unittest.IsolatedAsyncioTestCase):
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
                "truncate table itr_u_threads, refund_status_snapshots, notice_response_preparations, next_ay_checklists, year_over_year_comparisons, revision_threads, filed_return_artifacts, everification_status, submission_summaries, draft_returns, consents, approvals, action_proposals, action_executions, field_fill_history, validation_errors, filing_audit_trail, agent_checkpoints cascade"
            )

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table purge_jobs, itr_u_threads, refund_status_snapshots, notice_response_preparations, next_ay_checklists, year_over_year_comparisons, revision_threads, filed_return_artifacts, everification_status, submission_summaries, draft_returns, consents, approvals, action_proposals, action_executions, field_fill_history, validation_errors, filing_audit_trail, agent_checkpoints cascade"
            )
        if self._auth_token is not None:
            reset_request_auth(self._auth_token)
        await close_connection_pool()
        self.storage_dir.cleanup()

    async def test_summary_submit_and_everify_flow_persists_artifacts(self) -> None:
        self._bind_auth("user-1")
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

        official_artifact = await attach_official_artifact(
            OfficialArtifactAttachmentRequest(
                thread_id="thread-filing-1",
                page_type="filing-acknowledgement",
                page_title="Return filed successfully",
                page_url="https://www.incometax.gov.in/return-filed",
                portal_state={
                    "fields": {
                        "#ackNo": {"value": "ACK-12345", "fieldKey": "ack_no", "label": "Acknowledgement Number"},
                        "#filingDate": {"value": "2025-07-31T10:30:00+00:00", "fieldKey": "filed_at", "label": "Date of Filing"},
                    }
                },
                manual_text="Official portal acknowledgement for filed return ACK-12345.",
            )
        )
        self.assertEqual(official_artifact["artifacts"]["ack_no"], "ACK-12345")
        self.assertTrue(str(official_artifact["artifacts"]["itr_v_storage_uri"]).endswith("official-itr-v.md"))
        self.assertIn(
            "Official portal acknowledgement",
            document_storage.read(str(official_artifact["artifacts"]["itr_v_storage_uri"])).decode("utf-8"),
        )

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
        self.assertTrue(str((filing["artifacts"].get("artifact_manifest") or {}).get("official_itr_v_storage_uri", "")).endswith("official-itr-v.md"))
        self.assertEqual(len(filing["consents"]), 2)
        self.assertEqual(filing["everification"]["status"], "completed")
        self.assertIsNotNone(filing["summary_record"])

        pool = await get_pool()
        async with pool.acquire() as connection:
            artifact_count = await connection.fetchval("select count(*) from filed_return_artifacts where thread_id = $1", "thread-filing-1")
            consent_count = await connection.fetchval("select count(*) from consents where thread_id = $1", "thread-filing-1")
        self.assertEqual(artifact_count, 1)
        self.assertEqual(consent_count, 2)

        revoked = await revoke_consent(
            ConsentRevokeRequest(
                thread_id="thread-filing-1",
                consent_id=filing["consents"][0]["consent_id"],
            )
        )
        self.assertEqual(revoked["purge_job"]["status"], "completed")
        self.assertEqual(await checkpointer.latest("thread-filing-1"), None)

    async def test_onboarding_consents_catalog_and_grants_persist(self) -> None:
        self._bind_auth("user-consent")
        await checkpointer.save(
            AgentState(
                thread_id="thread-consent-1",
                user_id="user-consent",
                itr_type="ITR-1",
                tax_facts={"assessment_year": "2025-26", "name": "Consent Example"},
            )
        )

        catalog = await consent_catalog()
        self.assertGreaterEqual(len(catalog["items"]), 5)

        granted = await grant_consents(
            ConsentGrantRequest(
                thread_id="thread-consent-1",
                items=[
                    ConsentGrantItem(purpose="fill_portal"),
                    ConsentGrantItem(purpose="submit_return"),
                ],
            )
        )
        self.assertEqual({item["purpose"] for item in granted["granted"]}, {"fill_portal", "submit_return"})

        duplicate = await grant_consents(
            ConsentGrantRequest(
                thread_id="thread-consent-1",
                items=[ConsentGrantItem(purpose="fill_portal")],
            )
        )
        active_fill_portal = [
            consent for consent in duplicate["consents"] if consent["purpose"] == "fill_portal" and consent.get("revoked_at") is None
        ]
        self.assertEqual(len(active_fill_portal), 1)

        filing = await filing_state("thread-consent-1")
        active_purposes = {consent["purpose"] for consent in filing["consents"] if consent.get("revoked_at") is None}
        self.assertIn("fill_portal", active_purposes)
        self.assertIn("submit_return", active_purposes)

    async def test_revision_creates_new_thread_record(self) -> None:
        self._bind_auth("user-2")
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

    async def test_regime_preview_recommends_better_outcome(self) -> None:
        self._bind_auth("user-3")
        await checkpointer.save(
            AgentState(
                thread_id="thread-filing-3",
                user_id="user-3",
                itr_type="ITR-1",
                tax_facts={
                    "assessment_year": "2025-26",
                    "regime": "new",
                    "salary": {"gross": 950000},
                    "tax_paid": {"tds_salary": 60000},
                    "deductions": {"80c": 150000, "80d": 25000},
                    "exemptions": {"hra": 100000},
                },
            )
        )

        preview = await regime_preview(RegimePreviewRequest(thread_id="thread-filing-3"))
        self.assertIn(preview["recommended_regime"], {"old", "new"})
        self.assertIn("old_regime", preview)
        self.assertIn("new_regime", preview)
        self.assertIsInstance(preview["rationale"], list)

    async def test_post_filing_features_persist_and_surface_in_filing_state(self) -> None:
        self._bind_auth("user-4")
        await checkpointer.save(
            AgentState(
                thread_id="thread-filing-prior",
                user_id="user-4",
                itr_type="ITR-1",
                tax_facts={
                    "assessment_year": "2024-25",
                    "regime": "old",
                    "salary": {"gross": 1200000},
                    "deductions": {"80c": 120000, "80d": 15000},
                },
                submission_summary={
                    "assessment_year": "2024-25",
                    "itr_type": "ITR-1",
                    "regime": "old",
                    "gross_total_income": 1200000,
                    "total_deductions": 135000,
                    "taxable_income": 1065000,
                    "net_tax_liability": 92000,
                    "total_tax_paid": 95000,
                    "tax_payable": 0,
                    "refund_due": 3000,
                    "mismatch_count": 0,
                    "can_submit": True,
                    "blocking_issues": [],
                },
                submission_status="verified",
                filing_artifacts={"ack_no": "ACK-PRIOR"},
            )
        )
        await checkpointer.save(
            AgentState(
                thread_id="thread-filing-4",
                user_id="user-4",
                itr_type="ITR-1",
                tax_facts={
                    "assessment_year": "2025-26",
                    "name": "Carol Example",
                    "pan": "ABCDE1234H",
                    "regime": "new",
                    "salary": {"gross": 1500000},
                    "deductions": {"80c": 150000, "80d": 25000},
                    "tax_paid": {"tds_salary": 140000},
                    "exemptions": {"hra": 90000},
                    "bank": {"account_number": "1234567890", "ifsc": "HDFC0001234"},
                },
                reconciliation={"mismatches": []},
            )
        )

        summary = await generate_summary(FilingSummaryRequest(thread_id="thread-filing-4"))
        self.assertTrue(summary["submission_summary"]["gross_total_income"] > 0)

        comparison = await year_over_year(YearOverYearRequest(thread_id="thread-filing-4"))
        self.assertEqual(comparison["prior_assessment_year"], "2024-25")
        self.assertTrue(comparison["comparison"]["metrics"]["gross_total_income"]["delta"] > 0)

        checklist = await next_ay_checklist(NextAyChecklistRequest(thread_id="thread-filing-4"))
        self.assertEqual(checklist["target_assessment_year"], "2026-27")
        self.assertGreaterEqual(len(checklist["items"]), 4)

        notice = await prepare_notice(
            NoticePreparationRequest(
                thread_id="thread-filing-4",
                notice_type="143(1)",
                notice_text=(
                    "Intimation u/s 143(1)\n"
                    "Assessment Year: 2025-26\n"
                    "DIN: DIN-12345\n"
                    "Demand payable: INR 4500\n"
                    "Adjustment: TDS mismatch with Form 16\n"
                    "Response due by: 31/08/2026"
                ),
            )
        )
        self.assertEqual(notice["notice_type"], "143(1)")
        self.assertIn("TDS mismatch", " ".join(notice["extracted"]["adjustments"]))

        refund = await capture_refund_status(
            RefundStatusCaptureRequest(
                thread_id="thread-filing-4",
                manual_status="Refund credited",
                manual_portal_ref="REF-2026-1",
                manual_refund_amount=3200,
                manual_refund_mode="NEFT",
                manual_bank_masked="XXXX6789",
            )
        )
        self.assertEqual(refund["status"], "Refund credited")
        self.assertEqual(refund["source"], "manual")

        filing = await filing_state("thread-filing-4")
        self.assertIsNotNone(filing["year_over_year"])
        self.assertIsNotNone(filing["next_ay_checklist"])
        self.assertEqual(len(filing["notices"]), 1)
        self.assertEqual(filing["refund_status"]["portal_ref"], "REF-2026-1")

        pool = await get_pool()
        async with pool.acquire() as connection:
            yoy_count = await connection.fetchval("select count(*) from year_over_year_comparisons where thread_id = $1", "thread-filing-4")
            checklist_count = await connection.fetchval("select count(*) from next_ay_checklists where thread_id = $1", "thread-filing-4")
            notice_count = await connection.fetchval("select count(*) from notice_response_preparations where thread_id = $1", "thread-filing-4")
            refund_count = await connection.fetchval("select count(*) from refund_status_snapshots where thread_id = $1", "thread-filing-4")

        self.assertEqual(yoy_count, 1)
        self.assertEqual(checklist_count, 1)
        self.assertEqual(notice_count, 1)
        self.assertEqual(refund_count, 1)

    async def test_itr_u_prepare_and_confirm_flow(self) -> None:
        """ITR-U prepare returns eligibility + escalation gate; confirm creates the new thread."""
        self._bind_auth("user-5")
        # Seed a filed return on thread-filing-5.
        await checkpointer.save(
            AgentState(
                thread_id="thread-filing-5",
                user_id="user-5",
                itr_type="ITR-1",
                tax_facts={
                    "assessment_year": "2025-26",
                    "name": "Dave Example",
                    "pan": "ABCDE1234J",
                    "regime": "new",
                    "salary": {"gross": 1800000},
                    "tax_paid": {"tds_salary": 220000},
                    "bank": {"account_number": "9876543210", "ifsc": "ICIC0001234"},
                },
                submission_summary={
                    "assessment_year": "2025-26",
                    "itr_type": "ITR-1",
                    "regime": "new",
                    "gross_total_income": 1800000,
                    "total_deductions": 0,
                    "taxable_income": 1800000,
                    "net_tax_liability": 310000,
                    "total_tax_paid": 220000,
                    "tax_payable": 90000,
                    "refund_due": 0,
                    "mismatch_count": 0,
                    "can_submit": True,
                    "blocking_issues": [],
                },
                filing_artifacts={"ack_no": "ACK-ITR-U-BASE"},
                submission_status="submitted",
                reconciliation={"mismatches": []},
            )
        )

        # 1. /prepare — should be eligible, no blockers.
        escalation = await prepare_itr_u(
            ItrUPrepareRequest(
                thread_id="thread-filing-5",
                reason_code="income_not_disclosed",
                reason_detail="Freelance income from Q4 was omitted.",
            )
        )
        self.assertTrue(escalation["eligibility"]["eligible"])
        self.assertEqual(escalation["eligibility"]["blockers"], [])
        self.assertEqual(escalation["reason_code"], "income_not_disclosed")
        self.assertIn("escalation_md", escalation)
        self.assertIn("Chartered Accountant", escalation["escalation_md"])

        # 2. /confirm — creates ITR-U thread seed and confirms escalation.
        confirmed = await confirm_itr_u(
            ItrUConfirmRequest(
                thread_id="thread-filing-5",
                reason_code="income_not_disclosed",
                reason_detail="Freelance income from Q4 was omitted.",
                confirmed_by="ca-reviewer-1",
            )
        )
        self.assertEqual(confirmed["base_thread_id"], "thread-filing-5")
        itr_u_thread_id = confirmed["itr_u_thread_id"]
        self.assertTrue(itr_u_thread_id.startswith("thread-filing-5"))
        self.assertEqual(confirmed["itr_u_record"]["status"], "escalation_confirmed")
        self.assertEqual(confirmed["itr_u_record"]["reason_code"], "income_not_disclosed")
        self.assertEqual(confirmed["itr_u_record"]["base_ack_no"], "ACK-ITR-U-BASE")
        self.assertEqual(confirmed["itr_u_record"]["escalation_confirmed_by"], "ca-reviewer-1")
        self.assertIsNotNone(confirmed["itr_u_record"]["escalation_confirmed_at"])

        # Seed tax_facts on the new thread should carry ITR-U context.
        self.assertEqual(confirmed["seed_tax_facts"]["itr_u"]["base_thread_id"], "thread-filing-5")
        self.assertEqual(confirmed["seed_tax_facts"]["itr_u"]["reason_code"], "income_not_disclosed")

        # 3. New thread checkpoint must have been saved.
        itr_u_state = await checkpointer.latest(itr_u_thread_id)
        self.assertIsNotNone(itr_u_state)
        assert itr_u_state is not None
        self.assertTrue(itr_u_state.revision_context.get("is_itr_u"))
        self.assertEqual(itr_u_state.revision_context["base_thread_id"], "thread-filing-5")

        # 4. GET /itr-u/{thread_id} surfaces the record.
        record = await get_itr_u_state("thread-filing-5")
        self.assertEqual(record["status"], "escalation_confirmed")
        self.assertEqual(record["itr_u_thread_id"], itr_u_thread_id)

        # 5. filing_state/{thread_id} includes itr_u.
        filing = await filing_state("thread-filing-5")
        self.assertIsNotNone(filing["itr_u"])
        self.assertEqual(filing["itr_u"]["status"], "escalation_confirmed")

        # 6. DB record count sanity.
        pool = await get_pool()
        async with pool.acquire() as connection:
            count = await connection.fetchval(
                "select count(*) from itr_u_threads where base_thread_id = $1",
                "thread-filing-5",
            )
        self.assertEqual(count, 1)

    async def test_itr_u_prepare_rejects_unfiled_thread(self) -> None:
        """ITR-U /prepare returns 409 when the original return has not been filed."""
        self._bind_auth("user-6")
        await checkpointer.save(
            AgentState(
                thread_id="thread-filing-6",
                user_id="user-6",
                itr_type="ITR-1",
                tax_facts={"assessment_year": "2025-26"},
                submission_status="draft",
            )
        )
        from fastapi import HTTPException as FastAPIHTTPException
        with self.assertRaises(FastAPIHTTPException) as ctx:
            await prepare_itr_u(
                ItrUPrepareRequest(
                    thread_id="thread-filing-6",
                    reason_code="income_not_disclosed",
                )
            )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual(ctx.exception.detail["code"], "itr_u_not_eligible")