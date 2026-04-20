from pydantic import BaseModel, Field


class AgentState(BaseModel):
    thread_id: str
    user_id: str
    current_node: str = "bootstrap"
    portal_page: str = "unknown"
    messages: list[str] = Field(default_factory=list)
    archived: bool = False
