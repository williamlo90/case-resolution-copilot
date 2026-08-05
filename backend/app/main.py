from fastapi import FastAPI

from app.config import Settings, get_settings


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved = settings or get_settings()
    application = FastAPI(title="Case Resolution Copilot API", version="0.1.0")

    @application.get("/api/health/live")
    async def liveness() -> dict[str, str]:
        return {"status": "alive", "service": resolved.service_name}

    return application


app = create_app()
