"""A2A protocol data structures, modeled after Google A2A / Anthropic peer-agent designs."""

from typing import Literal
from pydantic import BaseModel


class AuthSpec(BaseModel):
    """Auth requirement an agent advertises. Demo only supports bearer."""

    scheme: Literal["bearer"] = "bearer"
    # In production you'd add: issuer, scopes, audience, jwks_uri, etc.


class AgentCard(BaseModel):
    """Self-description published by each agent at /.well-known/agent.json."""

    name: str
    description: str
    capabilities: list[str]  # task types this agent can handle
    endpoint: str
    version: str = "1.0"
    auth: AuthSpec | None = None   # None = open / no auth required


class TaskRequest(BaseModel):
    """Sent by a coordinator (or any agent) to a specialist agent."""

    task_id: str
    task_type: str          # must match one of the target's capabilities
    input: dict             # task-specific payload
    requester: str          # caller name, for tracing


class TaskResponse(BaseModel):
    """Returned by the specialist agent."""

    task_id: str
    state: Literal["completed", "failed"]
    output: dict | None = None
    error: str | None = None
