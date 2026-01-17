"""Main FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from llmstxt_api import __version__
from llmstxt_api.config import settings
from llmstxt_api.database import init_db
from llmstxt_api.middleware import RateLimitMiddleware
from llmstxt_api.routes import auth, generate, payment, subscriptions
from llmstxt_api.schemas import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    print("🚀 Starting llmstxt API...")
    await init_db()
    print("✓ Database initialized")
    yield
    # Shutdown
    print("👋 Shutting down llmstxt API...")


# Create FastAPI app
app = FastAPI(
    title="llmstxt API",
    description="Generate and assess llms.txt files for UK social sector organisations",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(auth.router, prefix="/api", tags=["Authentication"])
app.include_router(generate.router, prefix="/api", tags=["Generation"])
app.include_router(payment.router, prefix="/api/payment", tags=["Payment"])
app.include_router(subscriptions.router, prefix="/api", tags=["Subscriptions"])

web_dist_dir = Path(settings.web_dist_dir)
web_index_file = web_dist_dir / "index.html"


def web_available() -> bool:
    return web_index_file.exists()


def resolve_web_path(requested_path: str) -> Path | None:
    try:
        resolved = (web_dist_dir / requested_path).resolve()
    except Exception:
        return None
    if not str(resolved).startswith(str(web_dist_dir.resolve())):
        return None
    return resolved


@app.get("/", response_model=HealthResponse)
async def root():
    """Serve the web app if available, otherwise return health info."""
    if web_available():
        return FileResponse(web_index_file)
    return HealthResponse(
        status="healthy",
        version=__version__,
        environment=settings.environment,
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version=__version__,
        environment=settings.environment,
    )


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str):
    """Serve static assets and SPA routes for the web frontend."""
    if full_path.startswith("api"):
        raise HTTPException(status_code=404)
    if full_path in {"health", "docs", "redoc", "openapi.json"}:
        raise HTTPException(status_code=404)
    if not web_available():
        raise HTTPException(status_code=404)

    if not full_path:
        return FileResponse(web_index_file)

    candidate = resolve_web_path(full_path)
    if candidate and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(web_index_file)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "llmstxt_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
