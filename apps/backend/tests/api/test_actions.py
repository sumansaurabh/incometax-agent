from __future__ import annotations

import os
import unittest

from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState
from itx_backend.api.actions import (
    ActionDecision,
    ActionExecutionRequest,
    ProposalRequest,
    UndoExecutionRequest,
    decision,
    execute,
    proposal,
    thread_actions,
    undo,
    validation_help,
    ValidationHelpRequest,
)
from itx_backend.api.threads import ThreadEnsureRequest, ensure_thread
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool
from itx_backend.security.request_auth import reset_request_auth, set_request_auth
from itx_backend.services.auth_runtime import AuthContext


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class ActionsApiTest(unittest.IsolatedAsyncioTestCase):
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
        await close_connection_pool()
        await init_connection_pool()
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table validation_errors, field_fill_history, approvals, action_executions, action_proposals, filing_audit_trail, agent_checkpoints cascade"
            )

    async def asyncTearDown(self) -> None:
        pool = await get_pool()
        async with pool.acquire() as connection:
            await connection.execute(
                "truncate table validation_errors, field_fill_history, approvals, action_executions, action_proposals, filing_audit_trail, agent_checkpoints cascade"
            )
        if self._auth_token is not None:
            reset_request_auth(self._auth_token)
        await close_connection_pool()

    async def test_proposal_approval_execute_persists_action_audit(self) -> None:
        self._bind_auth("user-1")
        await checkpointer.save(
            AgentState(
                thread_id="thread-actions-1",
                user_id="user-1",
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

        planned = await proposal(
            ProposalRequest(
                thread_id="thread-actions-1",
                page_type="salary-schedule",
            )
        )

        self.assertEqual(planned["fill_plan"]["total_actions"], 3)
        self.assertEqual(planned["pending_approvals"][0]["approval_type"], "fill_page")

        approval_id = planned["pending_approvals"][0]["approval_id"]
        approved = await decision(
            ActionDecision(
                thread_id="thread-actions-1",
                approval_id=approval_id,
                approved=True,
            )
        )
        self.assertEqual(approved["approval_status"], "approved")
        self.assertEqual(len(approved["approved_actions"]), 3)

        executed = await execute(ActionExecutionRequest(thread_id="thread-actions-1"))
        self.assertEqual(executed["validation_summary"]["executed"], 3)
        self.assertEqual(executed["validation_summary"]["blocked"], 0)
        self.assertEqual(executed["portal_state"]["fields"]["#grossSalary"]["value"], 1850000)
        self.assertEqual(executed["portal_state"]["fields"]["#employerName"]["value"], "Example Technologies Pvt Ltd")

        activity = await thread_actions("thread-actions-1")
        self.assertEqual(len(activity["proposals"]), 1)
        self.assertEqual(activity["approvals"][0]["status"], "approved")
        self.assertEqual(len(activity["executions"]), 1)
        self.assertTrue(activity["executions"][0]["success"])

        pool = await get_pool()
        async with pool.acquire() as connection:
            fill_history_count = await connection.fetchval("select count(*) from field_fill_history where thread_id = $1", "thread-actions-1")
            audit_count = await connection.fetchval("select count(*) from filing_audit_trail where ay_id = $1", "2025-26")

        self.assertEqual(fill_history_count, 3)
        self.assertEqual(audit_count, 3)

    async def test_bank_change_targeted_fill_and_undo(self) -> None:
        self._bind_auth("user-2")
        await checkpointer.save(
            AgentState(
                thread_id="thread-actions-2",
                user_id="user-2",
                current_page="bank-account",
                portal_state={
                    "page": "bank-account",
                    "fields": {
                        "#ifscCode": {"value": "OLDIFSC0001"},
                        "#bankName": {"value": "Axis Bank"},
                    },
                    "validationErrors": [],
                },
                tax_facts={
                    "assessment_year": "2025-26",
                    "bank": {
                        "ifsc": "NEWIFSC0002",
                    },
                },
                fact_evidence={
                    "bank.ifsc": [{"document_type": "cancelled_cheque"}],
                },
            )
        )

        planned = await proposal(
            ProposalRequest(
                thread_id="thread-actions-2",
                page_type="bank-account",
                field_id="bank.ifsc",
            )
        )

        self.assertEqual(planned["fill_plan"]["total_actions"], 1)
        self.assertEqual(planned["pending_approvals"][0]["approval_type"], "bank_change")

        approval_id = planned["pending_approvals"][0]["approval_id"]
        await decision(
            ActionDecision(
                thread_id="thread-actions-2",
                approval_id=approval_id,
                approved=True,
            )
        )
        executed = await execute(ActionExecutionRequest(thread_id="thread-actions-2"))
        self.assertEqual(executed["validation_summary"]["executed"], 1)
        self.assertEqual(executed["portal_state"]["fields"]["#ifscCode"]["value"], "NEWIFSC0002")

        restored = await undo(
            UndoExecutionRequest(
                thread_id="thread-actions-2",
                execution_id=executed["execution_id"],
            )
        )
        self.assertEqual(restored["portal_state"]["fields"]["#ifscCode"]["value"], "OLDIFSC0001")
        self.assertEqual(len(restored["reverted_actions"]), 1)

        activity = await thread_actions("thread-actions-2")
        self.assertEqual(activity["approvals"][0]["kind"], "bank_change")
        self.assertEqual(len(activity["executions"]), 2)

    async def test_ensure_thread_and_browser_reported_execution(self) -> None:
        self._bind_auth("user-3")
        ensured = await ensure_thread(ThreadEnsureRequest(user_id="user-3"))
        self.assertEqual(ensured.user_id, "user-3")

        await checkpointer.save(
            AgentState(
                thread_id=ensured.thread_id,
                user_id="user-3",
                current_page="salary-schedule",
                portal_state={
                    "page": "salary-schedule",
                    "fields": {
                        "#grossSalary": {"value": ""},
                    },
                    "validationErrors": [],
                },
                tax_facts={
                    "assessment_year": "2025-26",
                    "gross_salary": 2500000,
                },
                fact_evidence={
                    "gross_salary": [{"document_type": "form16"}],
                },
            )
        )

        planned = await proposal(
            ProposalRequest(
                thread_id=ensured.thread_id,
                page_type="salary-schedule",
            )
        )
        approval_id = planned["pending_approvals"][0]["approval_id"]
        await decision(
            ActionDecision(
                thread_id=ensured.thread_id,
                approval_id=approval_id,
                approved=True,
            )
        )

        first_action = planned["fill_plan"]["pages"][0]["actions"][0]
        executed = await execute(
            ActionExecutionRequest(
                thread_id=ensured.thread_id,
                portal_state_before={
                    "page": "salary-schedule",
                    "fields": {
                        "#grossSalary": {"value": ""},
                    },
                    "validationErrors": [],
                },
                portal_state_after={
                    "page": "salary-schedule",
                    "fields": {
                        "#grossSalary": {"value": 2500000},
                    },
                    "validationErrors": [],
                },
                execution_results=[
                    {
                        **first_action,
                        "result": "ok",
                        "read_after_write": {
                            "ok": True,
                            "observed_value": 2500000,
                            "previous_value": "",
                        },
                    }
                ],
                validation_errors=[],
            )
        )

        self.assertEqual(executed["validation_summary"]["executed"], 1)
        self.assertEqual(executed["portal_state"]["fields"]["#grossSalary"]["value"], 2500000)

        activity = await thread_actions(ensured.thread_id)
        self.assertEqual(len(activity["executions"]), 1)
        self.assertEqual(activity["executions"][0]["results"]["executed_actions"][0]["read_after_write"]["previous_value"], "")

    async def test_validation_help_translates_required_and_ifsc_errors(self) -> None:
        self._bind_auth("user-4")
        await checkpointer.save(
            AgentState(
                thread_id="thread-actions-4",
                user_id="user-4",
                current_page="bank-account",
                portal_state={
                    "page": "bank-account",
                    "fields": {
                        "#ifscCode": {"value": "", "label": "IFSC Code", "required": True},
                    },
                    "validationErrors": [],
                },
                tax_facts={
                    "bank": {"ifsc": "HDFC0001234"},
                },
            )
        )

        translated = await validation_help(
            ValidationHelpRequest(
                thread_id="thread-actions-4",
                page_type="bank-account",
                portal_state={
                    "page": "bank-account",
                    "fields": {
                        "#ifscCode": {"value": "", "label": "IFSC Code", "required": True},
                    },
                },
                validation_errors=[
                    {"field": "#ifscCode", "message": "IFSC code is required"},
                ],
            )
        )

        self.assertEqual(len(translated["items"]), 1)
        self.assertIn("mandatory", translated["items"][0]["plain_english"].lower())
        self.assertIn("HDFC0001234", translated["items"][0]["suggested_fix"])