from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .agents.factory import AgentClientFactory
from .config import settings
from .http.routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.agents = AgentClientFactory.from_settings(settings)
    try:
        yield
    finally:
        await app.state.agents.aclose()


app = FastAPI(title="AgentTest Engine", version="0.1.0", lifespan=lifespan)

app.include_router(router)
