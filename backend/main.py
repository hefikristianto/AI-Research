from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers.auth import router as auth_router
from routers.storage import router as storage_router
from routers.upload import router as upload_router

app = FastAPI(
    title="AI-TDSS Backend API",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(storage_router)
app.include_router(upload_router)


@app.get("/")
def root():
    return {
        "message": "AI-TDSS Backend Running"
    }


@app.get("/health")
def health():
    return {
        "status": "healthy"
    }


@app.get("/supabase")
def test_supabase():
    return {
        "status": "connected",
        "message": "Supabase client created successfully"
    }
