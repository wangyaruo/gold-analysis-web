from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import router


app = FastAPI(
    title="Gold Analysis API",
    version="1.0.0",
    description="Realtime gold market data, indicators, recommendations, and PnL APIs.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
