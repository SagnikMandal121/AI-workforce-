from fastapi import FastAPI
from contextlib import asynccontextmanager
from runtime.employee_management.router import router as employee_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: connect to db, redis, event bus
    yield
    # Shutdown: disconnect
    
app = FastAPI(
    title="AI Workforce Runtime",
    description="Orchestration engine for AI employees.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(employee_router)

@app.get("/health")
async def health_check():
    return {"status": "ok"}
