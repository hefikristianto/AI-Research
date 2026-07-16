from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.analysis import (
    router as analysis_router,
)
from app.api.decisions import (
    router as decisions_router,
)
from app.api.detection import (
    router as detection_router,
)
from app.api.full_analysis import (
    router as full_analysis_router,
)


app = FastAPI(
    title="AI-TDSS API",
    description=(
        "AI Trading Decision "
        "Support System API"
    ),
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(decisions_router)
app.include_router(analysis_router)
app.include_router(detection_router)
app.include_router(full_analysis_router)


@app.get("/")
def root():
    return {
        "name": "AI-TDSS API",
        "version": "1.2.0",
        "status": "running",
        "modules": {
            "decision_results": True,
            "cnn_regime": True,
            "yolo_detection": True,
            "full_analysis": True,
        },
    }


@app.get("/health")
def health():
    return {
        "status": "healthy",
        "service": "AI-TDSS",
        "version": "1.2.0",
    }
