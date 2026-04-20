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
from itx_backend.agent.state import AgentState


class AgentGraph:
    def run(self, state: AgentState) -> AgentState:
        state = bootstrap.run(state)
        state = revised_return.run(state)
        state = portal_scan.run(state)
        state = document_intake.run(state)
        state = extract_facts.run(state)
        state = reconcile.run(state)
        state = infer_itr.run(state)
        state = explain_step.run(state)
        state = list_required_info.run(state)
        state = missing_inputs.run(state)
        state = fill_plan.run(state)
        state = approval_gate.run(state)
        state = execute_actions.run(state)
        state = validate_response.run(state)
        state = recovery.run(state)
        state = submission_summary.run(state)
        state = approval_gate.run(state)
        state = everify_handoff.run(state)
        state = ask_user.run(state)
        state = archive.run(state)
        return state


graph = AgentGraph()
