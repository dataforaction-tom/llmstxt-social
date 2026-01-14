"""Main FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from llmstxt_api import __version__
from llmstxt_api.config import settings
from llmstxt_api.database import init_db
from llmstxt_api.middleware import RateLimitMiddleware
from llmstxt_api.routes import generate, payment
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
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Rate limiting middleware
app.add_middleware(RateLimitMiddleware)

# Include routers
app.include_router(generate.router, prefix="/api", tags=["Generation"])
app.include_router(payment.router, prefix="/api/payment", tags=["Payment"])


@app.get("/", response_model=HealthResponse)
async def root():
    """API health check and info."""
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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "llmstxt_api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
    )
