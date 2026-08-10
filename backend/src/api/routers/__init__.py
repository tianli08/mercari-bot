"""Versioned API router collection."""

from fastapi import APIRouter

from .alerts import router as alerts_router
from .auth import router as auth_router
from .destinations import router as destinations_router
from .health import router as health_router
from .presets import router as presets_router
from .watchlists import router as watchlists_router

router = APIRouter()
router.include_router(health_router)
router.include_router(auth_router)
router.include_router(watchlists_router)
router.include_router(presets_router)
router.include_router(destinations_router)
router.include_router(alerts_router)
