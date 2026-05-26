import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.routes import router
from app.bootstrap import bootstrap
from app.config import get_settings
from app.scheduler import start_scheduler, stop_scheduler
from app.web import STATIC_DIR, router as web_router


settings = get_settings()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    bootstrap()
    if settings.enable_scheduler:
        logger.info("Starting scheduler")
        start_scheduler()
    else:
        logger.info("Scheduler disabled by ENABLE_SCHEDULER")
    try:
        yield
    finally:
        if settings.enable_scheduler:
            logger.info("Stopping scheduler")
            stop_scheduler()
        logger.info("Application shutdown complete")


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
app.include_router(web_router)
app.include_router(router)
