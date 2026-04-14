from dataclasses import asdict, dataclass, field
from typing import Literal


SessionStatus = Literal["active", "suspended", "discarded", "promoted"]


@dataclass(slots=True)
class CommandResult:
    command: list[str]
    exit_code: int
    stdout: str
    stderr: str
    category: str = "unknown"
    recovery_triggered: bool = False
    retried: bool = False
    recovery_scripts: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SessionRecord:
    name: str
    project_path: str
    session_path: str
    server_path: str
    workspace_name: str
    mode: str
    status: SessionStatus
    last_shelveset: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class ProjectDetection:
    kind: str
    confidence: str
    workspace_name: str | None
    server_path: str | None
    local_path: str
    is_agent_ready: bool


@dataclass(slots=True)
class OnboardingAdvice:
    project_kind: str
    confidence: str
    workspace: dict[str, str | None]
    recommended_workflow: dict[str, str]
    supports: dict[str, bool]
    notes: list[str]
