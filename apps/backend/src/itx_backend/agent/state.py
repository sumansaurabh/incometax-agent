from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class AgentState(BaseModel):
    model_config = ConfigDict(extra="allow")

    thread_id: str
    user_id: str
    current_node: str = "bootstrap"
    portal_page: str = "unknown"
    current_page: str = "unknown"
    itr_type: str = "ITR-1"
    messages: list[Any] = Field(default_factory=list)
    archived: bool = False

    # Common mutable agent payloads
    portal_state: dict[str, Any] = Field(default_factory=dict)
    tax_facts: dict[str, Any] = Field(default_factory=dict)
    fill_plan: Optional[dict[str, Any]] = None
    pending_approvals: list[dict[str, Any]] = Field(default_factory=list)
    approved_actions: list[str] = Field(default_factory=list)
    submission_summary: Optional[dict[str, Any]] = None
    pending_submission: Optional[dict[str, Any]] = None
    learned_mappings: dict[str, Any] = Field(default_factory=dict)
    documents: list[dict[str, Any]] = Field(default_factory=list)
    rejected_documents: list[dict[str, Any]] = Field(default_factory=list)
    reconciliation: dict[str, Any] = Field(default_factory=dict)
    fact_evidence: dict[str, Any] = Field(default_factory=dict)
    ais_facts: dict[str, Any] = Field(default_factory=dict)
    fill_target: dict[str, Any] = Field(default_factory=dict)
    browser_execution: Optional[dict[str, Any]] = None
    executed_actions: list[dict[str, Any]] = Field(default_factory=list)
    blocked_actions: list[dict[str, Any]] = Field(default_factory=list)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    action_history: list[dict[str, Any]] = Field(default_factory=list)
    last_execution_portal_state: dict[str, Any] = Field(default_factory=dict)
    current_approval_id: Optional[str] = None
    action_proposal_id: Optional[str] = None
    last_execution_id: Optional[str] = None
    answered_questions: set[str] = Field(default_factory=set)

    def get(self, key: str, default: Any = None) -> Any:
        return getattr(self, key, default)

    def apply_update(self, updates: dict[str, Any]) -> None:
        for key, value in updates.items():
            setattr(self, key, value)
