from typing import Awaitable, Callable
from time import perf_counter

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
from itx_backend.telemetry.agent_observability import agent_observability
from itx_backend.telemetry.tracing import get_tracer


NodeRunner = Callable[[AgentState], Awaitable[AgentState]]


class AgentGraph:
    def __init__(self) -> None:
        self._nodes: list[NodeRunner] = [
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

    async def run(self, state: AgentState) -> AgentState:
        tracer = get_tracer("agent_graph")
        for node in self._nodes:
            node_name = node.__module__.split(".")[-1]
            started_at = perf_counter()
            await agent_observability.record(
                thread_id=state.thread_id,
                node_name=node_name,
                status="started",
                current_page=state.current_page,
            )
            with tracer.start_as_current_span(f"agent.{node_name}") as span:
                span.set_attribute("agent.thread_id", state.thread_id)
                span.set_attribute("agent.node", node_name)
                if state.current_page:
                    span.set_attribute("agent.current_page", state.current_page)
                try:
                    state = await node(state)
                    duration_ms = int((perf_counter() - started_at) * 1000)
                    span.set_attribute("agent.status", "completed")
                    span.set_attribute("agent.duration_ms", duration_ms)
                    await agent_observability.record(
                        thread_id=state.thread_id,
                        node_name=node_name,
                        status="completed",
                        duration_ms=duration_ms,
                        current_page=state.current_page,
                    )
                except Exception as exc:
                    duration_ms = int((perf_counter() - started_at) * 1000)
                    span.set_attribute("agent.status", "failed")
                    span.set_attribute("agent.duration_ms", duration_ms)
                    span.set_attribute("agent.error_type", exc.__class__.__name__)
                    await agent_observability.record(
                        thread_id=state.thread_id,
                        node_name=node_name,
                        status="failed",
                        duration_ms=duration_ms,
                        current_page=state.current_page,
                        metadata={"error_type": exc.__class__.__name__, "error": str(exc)},
                    )
                    raise
            await checkpointer.save(state)
        return state


graph = AgentGraph()
