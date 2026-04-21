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
)
from itx_backend.db.session import close_connection_pool, get_pool, init_connection_pool


@unittest.skipUnless(os.getenv("ITX_DATABASE_URL"), "ITX_DATABASE_URL required for Postgres tests")
class ActionsApiTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
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
        await close_connection_pool()

    async def test_proposal_approval_execute_persists_action_audit(self) -> None:
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