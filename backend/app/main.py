from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.model_engine.routes import router as model_engine_router
from app.api.chat import router as chat_router
from app.api.history import router as history_router
from app.api.knowledge import router as knowledge_router
from app.api.knowledge_search import (
    router as knowledge_search_router,
)
from app.api.agents.routes import router as agents_router
from app.api.sovereignty import router as sovereignty_router
from app.api.audit import router as audit_router
from app.api.analytics import router as analytics_router
from app.api.auth import router as auth_router

from app.core.database import init_db
from app.core import models


# =========================================
# DATABASE INITIALIZATION
# =========================================

init_db()


# =========================================
# FASTAPI APPLICATION
# =========================================

app = FastAPI(
    title="NOVA",
    description="Sovereign Industrial Intelligence Backend",
    version="0.1.0",
)


# =========================================
# CORS
# =========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =========================================
# API ROUTERS
# =========================================

app.include_router(
    chat_router
)

app.include_router(
    knowledge_router
)

app.include_router(
    knowledge_search_router
)

app.include_router(
    history_router
)

app.include_router(
    model_engine_router
)

app.include_router(
    agents_router
)

app.include_router(
    sovereignty_router
)

app.include_router(
    audit_router
)

app.include_router(
    analytics_router
)

app.include_router(
    auth_router
)


# =========================================
# SYSTEM ENDPOINTS
# =========================================

@app.get("/")
def root():
    return {
        "name": "NOVA",
        "status": "online",
        "service": "sovereign-ai-backend",
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
    }