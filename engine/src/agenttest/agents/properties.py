from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from .role import AgentRole


class AgentConfig(BaseModel):
    """Per-role LLM configuration loaded from `configs/agents.yaml`.

    Mirrors MyKefi's `AgentProperties.AgentConfig` static inner class.
    """

    provider: str = "anthropic"
    model: str = "claude-sonnet-4-6"
    max_tokens: int = 4096
    temperature: float = 0.7
    enabled: bool = True
    prompt_cache_enabled: bool = False

    @property
    def is_anthropic(self) -> bool:
        return self.provider.lower() == "anthropic"


class AgentProperties(BaseModel):
    """Loaded shape of `configs/agents.yaml` — one entry per `AgentRole`."""

    agents: dict[AgentRole, AgentConfig] = Field(default_factory=dict)

    def get(self, role: AgentRole) -> AgentConfig:
        config = self.agents.get(role)
        if config is None:
            configured = sorted(r.value for r in self.agents)
            raise KeyError(
                f"No config for agent role '{role.value}' in agents.yaml. "
                f"Configured roles: {configured}"
            )
        return config

    @classmethod
    def from_yaml(cls, path: Path) -> "AgentProperties":
        with path.open(encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)
