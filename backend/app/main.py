from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import router
from backend.app.core.config import load_config


app = FastAPI(
    title="Gold Analysis API",
    version="1.0.0",
    description="Realtime gold market data, indicators, recommendations, and PnL APIs.",
)
config = load_config()

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.get("cors", {}).get(
        "allowed_origins",
        ["http://localhost:5173", "http://127.0.0.1:5173"],
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
