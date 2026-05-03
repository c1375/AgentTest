from typing import Any

from fastapi import APIRouter, Depends

from ..agents.dependencies import get_factory
from ..agents.factory import AgentClientFactory

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/agents")
def list_agents(
    factory: AgentClientFactory = Depends(get_factory),
) -> dict[str, dict[str, Any]]:
    """Dump the currently resolved per-role model config.

    Mirrors the spirit of MyKefi's admin model API — useful for verifying
    that `agents.yaml` was loaded correctly without making real Claude calls.
    """
    out: dict[str, dict[str, Any]] = {}
    for role in factory.list_roles():
        client = factory.get(role)
        out[role.value] = {
            "provider": client.config.provider,
            "model": client.config.model,
            "max_tokens": client.config.max_tokens,
            "temperature": client.config.temperature,
            "prompt_cache_enabled": client.config.prompt_cache_enabled,
        }
    return out
