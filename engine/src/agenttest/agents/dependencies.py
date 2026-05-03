from fastapi import Request

from .factory import AgentClientFactory


def get_factory(request: Request) -> AgentClientFactory:
    """FastAPI dependency that returns the singleton `AgentClientFactory`
    created in `main.lifespan` and stashed on `app.state.agents`.
    """
    return request.app.state.agents  # type: ignore[no-any-return]
