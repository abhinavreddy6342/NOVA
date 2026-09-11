from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.history import router as history_router
from app.api.knowledge import router as knowledge_router
from app.api.knowledge_search import (
    router as knowledge_search_router,
)

from app.core.database import Base, engine
from app.core import models


# =========================================
# DATABASE INITIALIZATION
# =========================================

Base.metadata.create_all(
    bind=engine
)


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