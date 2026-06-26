from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api import router
from backend.app.core.config import load_config


app = FastAPI(
    title="黄金分析 API",
    version="1.0.0",
    description="实时黄金行情、技术指标、交易建议与盈亏计算接口。",
)
config = load_config()

app.add_middleware(
    CORSMiddleware,
allow_origins=config.get("cors", {}).get(
        "allowed_origins",
        ["http://localhost:5178", "http://127.0.0.1:5178"],
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")
