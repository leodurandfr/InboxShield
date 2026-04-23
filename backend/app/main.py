import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.services.scheduler import start_scheduler, stop_scheduler

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting InboxShield backend...")
    try:
        await start_scheduler()
    except Exception:
        logger.exception("Failed to start scheduler — continuing without background jobs")
    yield
    # Shutdown
    logger.info("Shutting down InboxShield backend...")
    await stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Intelligent email management — privacy-first",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API routers
from app.api import (
    accounts,
    activity,
    analytics,
    emails,
    newsletters,
    review,
    rules,
    senders,
    system,
    threads,
    websocket,
)
from app.api import settings as settings_api

app.include_router(websocket.router, prefix="/api/v1")
app.include_router(accounts.router, prefix="/api/v1/accounts", tags=["accounts"])
app.include_router(emails.router, prefix="/api/v1/emails", tags=["emails"])
app.include_router(review.router, prefix="/api/v1/review", tags=["review"])
app.include_router(rules.router, prefix="/api/v1/rules", tags=["rules"])
app.include_router(newsletters.router, prefix="/api/v1/newsletters", tags=["newsletters"])
app.include_router(senders.router, prefix="/api/v1/senders", tags=["senders"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["analytics"])
app.include_router(activity.router, prefix="/api/v1/activity", tags=["activity"])
app.include_router(settings_api.router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(threads.router, prefix="/api/v1/threads", tags=["threads"])
app.include_router(system.router, prefix="/api/v1/system", tags=["system"])
