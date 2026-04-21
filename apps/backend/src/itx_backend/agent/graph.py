from itx_backend.agent.nodes import (
    approval_gate,
    archive,
    ask_user,
    bootstrap,
    document_intake,
    everify_handoff,
    explain_step,
    execute_actions,
    extract_facts,
    fill_plan,
    infer_itr,
    list_required_info,
    missing_inputs,
    portal_scan,
    recovery,
    reconcile,
    revised_return,
    submission_summary,
    validate_response,
)
from itx_backend.agent.checkpointer import checkpointer
from itx_backend.agent.state import AgentState


class AgentGraph:
    def __init__(self) -> None:
        self._nodes = [
            bootstrap.run,
            revised_return.run,
            portal_scan.run,
            document_intake.run,
            extract_facts.run,
            reconcile.run,
            infer_itr.run,
            explain_step.run,
            list_required_info.run,
            missing_inputs.run,
            fill_plan.run,
            approval_gate.run,
            execute_actions.run,
            validate_response.run,
            recovery.run,
            submission_summary.run,
            approval_gate.run,
            everify_handoff.run,
            ask_user.run,
            archive.run,
        ]

    def run(self, state: AgentState) -> AgentState:
        for node in self._nodes:
            state = node(state)
            checkpointer.save(state)
        return state


graph = AgentGraph()
