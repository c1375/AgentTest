from typing import Any

from anthropic import AsyncAnthropic


class ProviderRegistry:
    """Owns one shared LLM provider client per provider name.

    Today only Anthropic is wired. OpenAI / others can be added when an
    AgentRole in `configs/agents.yaml` declares a non-anthropic provider.
    """

    def __init__(self, *, anthropic_api_key: str) -> None:
        self._anthropic = AsyncAnthropic(api_key=anthropic_api_key)

    def get(self, provider: str) -> Any:
        if provider == "anthropic":
            return self._anthropic
        raise KeyError(
            f"Unknown provider '{provider}'. "
            "Wire it in ProviderRegistry before referencing in agents.yaml."
        )

    async def aclose(self) -> None:
        await self._anthropic.close()
