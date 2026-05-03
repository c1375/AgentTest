from typing import Any

from anthropic import AsyncAnthropic
from anthropic.types import Message

from .properties import AgentConfig
from .role import AgentRole


class AgentClient:
    """A role-bound async LLM client.

    Mirrors MyKefi's named ChatClient bean pattern: each role gets its own
    AgentClient instance pre-bound to a model, max_tokens, and temperature
    from `configs/agents.yaml`. Call sites only pass the prompt content.

    Anthropic-specific for now. If a second provider lands, lift this to a
    Protocol with one impl per provider (mirroring MyKefi's ChatClient
    interface) — see TODO in factory.py.
    """

    def __init__(
        self,
        *,
        role: AgentRole,
        config: AgentConfig,
        raw_client: AsyncAnthropic,
    ) -> None:
        self.role = role
        self.config = config
        self._raw = raw_client

    async def complete(
        self,
        *,
        system: str | None = None,
        messages: list[dict[str, Any]],
        max_tokens: int | None = None,
        temperature: float | None = None,
    ) -> Message:
        """Single-shot completion. Returns the raw Anthropic Message object.

        Per-call `max_tokens` / `temperature` override the role defaults.
        When `prompt_cache_enabled` is set on the role, the system prompt is
        sent with `cache_control: ephemeral` so Anthropic caches it for
        ~5 minutes — mirrors MyKefi's `AnthropicCacheStrategy.TOOLS_ONLY`
        with FIVE_MINUTES TTL on the SYSTEM message type.
        """
        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": max_tokens if max_tokens is not None else self.config.max_tokens,
            "temperature": (
                temperature if temperature is not None else self.config.temperature
            ),
            "messages": messages,
        }
        if system is not None:
            if self.config.prompt_cache_enabled:
                kwargs["system"] = [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]
            else:
                kwargs["system"] = system
        return await self._raw.messages.create(**kwargs)
