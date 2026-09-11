from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import models  # noqa: F401 - ensures models are registered on Base
from app.config import settings
from app.database import Base, engine
from app.routers import auth, dashboard, public, widgets

MAX_BODY_BYTES = 50_000  # generous for a lead-capture form; rejects abuse fast, pre-parse


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

# The public endpoints (config, widget.js, submissions) must be callable from
# ANY customer origin by design — that's the whole point of an embeddable
# widget. The admin API is protected by the bearer token, not by CORS, so the
# same permissive policy is safe to apply app-wide.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.PUBLIC_CORS_ALLOW_ORIGINS == "*" else settings.PUBLIC_CORS_ALLOW_ORIGINS.split(","),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def reject_oversized_bodies(request: Request, call_next):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MAX_BODY_BYTES:
        return JSONResponse(status_code=413, content={"detail": "Payload too large"})
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "ok", "app": settings.APP_NAME}


app.include_router(auth.router)
app.include_router(widgets.router)
app.include_router(public.router)
app.include_router(dashboard.router)
