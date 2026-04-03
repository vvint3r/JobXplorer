"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import auth, users, resumes, searches, jobs, insights, alignment, pipelines, optimized_resumes, application_logs, notifications

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.api_v1_prefix}/users", tags=["users"])
app.include_router(resumes.router, prefix=f"{settings.api_v1_prefix}/resumes", tags=["resumes"])
app.include_router(searches.router, prefix=f"{settings.api_v1_prefix}/searches", tags=["searches"])
app.include_router(jobs.router, prefix=f"{settings.api_v1_prefix}/jobs", tags=["jobs"])
app.include_router(insights.router, prefix=f"{settings.api_v1_prefix}/insights", tags=["insights"])
app.include_router(alignment.router, prefix=f"{settings.api_v1_prefix}/alignment", tags=["alignment"])
app.include_router(pipelines.router, prefix=f"{settings.api_v1_prefix}/pipelines", tags=["pipelines"])
app.include_router(optimized_resumes.router, prefix=f"{settings.api_v1_prefix}/optimized-resumes", tags=["optimized-resumes"])
app.include_router(application_logs.router, prefix=f"{settings.api_v1_prefix}/application-logs", tags=["application-logs"])
app.include_router(notifications.router, prefix=f"{settings.api_v1_prefix}/notifications", tags=["notifications"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "service": settings.app_name}
