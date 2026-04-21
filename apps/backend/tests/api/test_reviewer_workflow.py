from __future__ import annotations

import os
import unittest

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.api.actions import ActionDecision, ActionExecutionRequest, ProposalRequest, decision, execute, proposal, thread_actions
from itx_backend.api.ca_workspace import (
    CounterConsentRequest,
    ReviewerDecisionRequest,
    ReviewerSignoffRequest,
    client_detail,
    clients,
    request_reviewer_signoff,
    reviewer_counter_consent,
    reviewer_decision,
)
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool
from itx_backend.security.request_auth import reset_request_auth, set_request_auth
from itx_backend.services.auth_runtime import AuthContext


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class ReviewerWorkflowApiTest(unittest.IsolatedAsyncioTestCase):
    def _bind_auth(self, user_id: str, email: str) -> None:
        if hasattr(self, "_auth_token") and self._auth_token is not None:
            reset_request_auth(self._auth_token)
        self._auth_token = set_request_auth(
            AuthContext(
                user_id=user_id,
                email=email,
                device_id=f"device-{user_id}",
                session_id=f"session-{user_id}",
            )
        )

    async def asyncSetUp(self) -> None:
        self._auth_token = None
        await close_connection_pool()
        await init_connection_pool()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table reviewer_signoffs, review_access_grants, consents, approvals, action_executions, action_proposals, field_fill_history, validation_errors, filing_audit_trail, agent_checkpoints cascade"
            )

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table reviewer_signoffs, review_access_grants, consents, approvals, action_executions, action_proposals, field_fill_history, validation_errors, filing_audit_trail, agent_checkpoints cascade"
            )
        if self._auth_token is not None:
            reset_request_auth(self._auth_token)
        await close_connection_pool()

    async def test_reviewer_signoff_blocks_execution_until_counter_consent(self) -> None:
        owner_user_id = "owner-user"
        reviewer_user_id = "reviewer-user"
        reviewer_email = "reviewer@example.com"
        thread_id = "thread-reviewer-1"

        self._bind_auth(owner_user_id, "owner@example.com")
        await checkpointer.save(
            AgentState(
                thread_id=thread_id,
                user_id=owner_user_id,
                current_page="salary-schedule",
                portal_state={
                    "page": "salary-schedule",
                    "fields": {
                        "#grossSalary": {"value": ""},
                        "#employerName": {"value": ""},
                        "#employerTAN": {"value": ""},
                    },
                    "validationErrors": [],
                },
                tax_facts={
                    "assessment_year": "2025-26",
                    "gross_salary": 1850000,
                    "employer_name": "Example Technologies Pvt Ltd",
                    "employer_tan": "BLRA12345B",
                },
                fact_evidence={
                    "gross_salary": [{"document_type": "form16"}],
                    "employer_name": [{"document_type": "form16"}],
                    "employer_tan": [{"document_type": "form16"}],
                },
            )
        )

        planned = await proposal(ProposalRequest(thread_id=thread_id, page_type="salary-schedule"))
        approval_id = planned["pending_approvals"][0]["approval_id"]
        await decision(ActionDecision(thread_id=thread_id, approval_id=approval_id, approved=True))

        signoff = await request_reviewer_signoff(
            ReviewerSignoffRequest(
                thread_id=thread_id,
                approval_id=approval_id,
                reviewer_email=reviewer_email,
                note="Please review salary autofill before execution.",
            )
        )
        self.assertEqual(signoff["status"], "pending_reviewer")

        owner_activity = await thread_actions(thread_id)
        self.assertEqual(owner_activity["reviewer_signoffs"][0]["status"], "pending_reviewer")

        self._bind_auth(reviewer_user_id, reviewer_email)
        reviewer_queue = await clients()
        shared_thread = next(item for item in reviewer_queue["items"] if item["thread_id"] == thread_id)
        self.assertEqual(shared_thread["access_role"], "reviewer")
        self.assertEqual(shared_thread["pending_signoff_count"], 1)

        reviewer_detail = await client_detail(thread_id)
        self.assertEqual(reviewer_detail["access_role"], "reviewer")
        self.assertEqual(reviewer_detail["reviewer_signoffs"][0]["status"], "pending_reviewer")

        reviewed = await reviewer_decision(
            signoff["signoff_id"],
            ReviewerDecisionRequest(approved=True, note="Looks correct based on Form 16."),
        )
        self.assertEqual(reviewed["status"], "reviewer_approved")

        self._bind_auth(owner_user_id, "owner@example.com")
        blocked = await execute(ActionExecutionRequest(thread_id=thread_id))
        self.assertEqual(blocked["validation_summary"]["executed"], 0)
        self.assertEqual(blocked["validation_summary"]["blocked"], 3)
        self.assertTrue(all(item["reason"] == "missing_durable_approval" for item in blocked["blocked_actions"]))

        counter_consented = await reviewer_counter_consent(
            signoff["signoff_id"],
            CounterConsentRequest(approved=True, note="Client accepts reviewer recommendation."),
        )
        self.assertEqual(counter_consented["status"], "client_approved")
        self.assertTrue(counter_consented["client_consent_key"].startswith("reviewer-signoff:"))

        executed = await execute(ActionExecutionRequest(thread_id=thread_id))
        self.assertEqual(executed["validation_summary"]["executed"], 3)
        self.assertEqual(executed["validation_summary"]["blocked"], 0)
        self.assertEqual(executed["portal_state"]["fields"]["#grossSalary"]["value"], 1850000)

        final_activity = await thread_actions(thread_id)
        self.assertEqual(final_activity["reviewer_signoffs"][0]["status"], "client_approved")

        pool = await get_pool()
        async with pool.acquire() as connection:
            consent_count = await connection.fetchval(
                "select count(*) from consents where thread_id = $1 and purpose = 'reviewer_counter_consent'",
                thread_id,
            )
        self.assertEqual(consent_count, 1)


if __name__ == "__main__":
    unittest.main()
