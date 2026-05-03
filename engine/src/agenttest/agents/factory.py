from anthropic import AsyncAnthropic

from ..adapters.registry import ProviderRegistry
from ..config import Settings
from .client import AgentClient
from .properties import AgentProperties
from .role import AgentRole


class AgentClientFactory:
    """Owns one `AgentClient` per `AgentRole`, built from `configs/agents.yaml`.

    Lifecycle: created once at FastAPI startup (see `main.lifespan`),
    `aclose()`-d at shutdown. Mirrors MyKefi's `DynamicChatClientConfig`
    bean wiring — without the runtime DB-override layer, which AgentTest
    does not need at its scale.

    TODO: if we ever want runtime model switching for a single role
    (e.g., swap synthesizer Sonnet → Opus mid-session), port MyKefi's
    `AgentModelConfig` table + `ModelAssignmentCache` + `DynamicChatClient`
    proxy. Until then, edit `agents.yaml` and restart.
    """

    def __init__(
        self,
        *,
        properties: AgentProperties,
        registry: ProviderRegistry,
    ) -> None:
        self._properties = properties
        self._registry = registry
        self._clients: dict[AgentRole, AgentClient] = {}
        self._build_all()

    def _build_all(self) -> None:
        for role in AgentRole:
            try:
                config = self._properties.get(role)
            except KeyError:
                continue
            if not config.enabled:
                continue
            raw = self._registry.get(config.provider)
            if not isinstance(raw, AsyncAnthropic):
                raise TypeError(
                    f"Role '{role.value}' uses provider '{config.provider}', "
                    "but only Anthropic is currently supported. "
                    "Add a provider impl to AgentClient first."
                )
            self._clients[role] = AgentClient(
                role=role,
                config=config,
                raw_client=raw,
            )

    def get(self, role: AgentRole) -> AgentClient:
        client = self._clients.get(role)
        if client is None:
            raise KeyError(
                f"No client for role '{role.value}'. "
                "Either it is disabled in agents.yaml or its provider is not registered."
            )
        return client

    def list_roles(self) -> list[AgentRole]:
        return list(self._clients)

    async def aclose(self) -> None:
        await self._registry.aclose()

    @classmethod
    def from_settings(cls, settings: Settings) -> "AgentClientFactory":
        properties = AgentProperties.from_yaml(settings.configs_dir / "agents.yaml")
        registry = ProviderRegistry(anthropic_api_key=settings.anthropic_api_key)
        return cls(properties=properties, registry=registry)
