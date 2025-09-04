from typing import Dict, Optional
from uuid import UUID

from fastapi import APIRouter, Body, Depends, HTTPException
from app.api.v1.endpoints import kpi, users
from app.api import raci_matrix
from app.config.settings import settings

api_v1_router = APIRouter()

# Include user routes
api_v1_router.include_router(users.router, prefix="/users", tags=["Users"])

# Include KPI routes
api_v1_router.include_router(kpi.router, prefix="/kpi", tags=["KPIs"])

# Include RACI matrices routes
api_v1_router.include_router(raci_matrix.router)
