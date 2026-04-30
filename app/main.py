"""Medihospes Scheduling API — FastAPI application entry point."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.api import auth, clinics, job_titles, notifications, reports, shifts, time_entries, users
from app.core.config import settings


class TrailingSlashMiddleware(BaseHTTPMiddleware):
    """Normalize URLs by stripping trailing slashes so routes match
    regardless of whether the client sends /path or /path/."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.scope["path"]
        if path != "/" and path.endswith("/"):
            request.scope["path"] = path.rstrip("/")
        return await call_next(request)


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

app.add_middleware(TrailingSlashMiddleware)

# CORS — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router, prefix="/api")
app.include_router(clinics.router, prefix="/api")
app.include_router(shifts.router, prefix="/api")
app.include_router(time_entries.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(notifications.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(job_titles.router, prefix="/api")


@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": settings.APP_NAME}
