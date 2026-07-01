import asyncio
import contextlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.alert_worker import start_alert_worker
from backend.app.api import _alert_store, _kline_store, _provider, router
from backend.app.core.config import load_config


config = load_config()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = start_alert_worker(config, _provider, _alert_store, _kline_store)
    try:
        yield
    finally:
        if task:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title="黄金分析 API",
    version="1.0.0",
    description="实时黄金行情、技术指标、交易建议与盈亏计算接口。",
    lifespan=lifespan,
)

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
