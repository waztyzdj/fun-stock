from fastapi import APIRouter

from app.api.routes import backtests, health, stocks, strategies, sync

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(backtests.router)
api_router.include_router(stocks.router)
api_router.include_router(strategies.router)
api_router.include_router(sync.router)
