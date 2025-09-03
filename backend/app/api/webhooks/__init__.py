# Make webhooks a package (Slack interactions removed)
from fastapi import APIRouter

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
