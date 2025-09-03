"""
Health check endpoints for monitoring documentation automation services.

Provides comprehensive health monitoring for external dependencies,
circuit breakers, rate limiters, and overall system status.
"""

import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.config.settings import settings
from app.config.supabase_client import get_supabase_client
from app.core.circuit_breaker import circuit_manager
from app.core.rate_limiter import rate_limiter_manager
from supabase import Client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/health", tags=["health"])


class HealthChecker:
    """Centralized health checking for all system components."""

    def __init__(self):
        self.timeout = getattr(settings, "HEALTH_CHECK_TIMEOUT", 10)
        self.detailed_checks = getattr(settings, "ENABLE_DETAILED_HEALTH_CHECKS", True)

    async def check_database(self, supabase: Client) -> Dict[str, Any]:
        """Check database connectivity and performance."""
        start_time = time.time()
        try:
            # Simple query to test connectivity
            response = supabase.table("users").select("id").limit(1).execute()
            duration = time.time() - start_time

            return {
                "status": "healthy",
                "response_time_ms": round(duration * 1000, 2),
                "details": "Database connection successful",
            }
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "unhealthy",
                "response_time_ms": round(duration * 1000, 2),
                "details": f"Database connection failed: {str(e)}",
            }

    async def check_github_api(self) -> Dict[str, Any]:
        """Check GitHub API availability and rate limits."""
        start_time = time.time()
        try:
            # Check if we have GitHub token configured
            if not hasattr(settings, "GITHUB_TOKEN") or not settings.GITHUB_TOKEN:
                return {"status": "disabled", "response_time_ms": 0, "details": "GitHub token not configured"}

            from github import Github

            github_client = Github(settings.GITHUB_TOKEN)

            # Simple API call to check connectivity
            rate_limit = github_client.get_rate_limit()
            duration = time.time() - start_time

            # Check remaining rate limit
            core_remaining = rate_limit.core.remaining
            core_limit = rate_limit.core.limit
            reset_time = rate_limit.core.reset

            status = "healthy"
            if core_remaining < 100:  # Less than 100 requests remaining
                status = "degraded"
            elif core_remaining == 0:
                status = "unhealthy"

            return {
                "status": status,
                "response_time_ms": round(duration * 1000, 2),
                "details": {
                    "rate_limit_remaining": core_remaining,
                    "rate_limit_total": core_limit,
                    "rate_limit_reset": reset_time.isoformat(),
                    "requests_used_percent": round((1 - core_remaining / core_limit) * 100, 1),
                },
            }
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"GitHub API health check failed: {e}")
            return {
                "status": "unhealthy",
                "response_time_ms": round(duration * 1000, 2),
                "details": f"GitHub API check failed: {str(e)}",
            }

    async def check_openai_api(self) -> Dict[str, Any]:
        """Check OpenAI API availability."""
        start_time = time.time()
        try:
            # Check if we have OpenAI API key configured
            if not hasattr(settings, "OPENAI_API_KEY") or not settings.OPENAI_API_KEY:
                return {"status": "disabled", "response_time_ms": 0, "details": "OpenAI API key not configured"}

            from openai import OpenAI

            openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)

            # Simple API call to check connectivity (list models)
            models = openai_client.models.list()
            duration = time.time() - start_time

            model_count = len(models.data) if models.data else 0

            return {
                "status": "healthy",
                "response_time_ms": round(duration * 1000, 2),
                "details": {"available_models": model_count, "connection": "successful"},
            }
        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"OpenAI API health check failed: {e}")
            return {
                "status": "unhealthy",
                "response_time_ms": round(duration * 1000, 2),
                "details": f"OpenAI API check failed: {str(e)}",
            }

    def check_circuit_breakers(self) -> Dict[str, Any]:
        """Check status of all circuit breakers."""
        try:
            breaker_status = circuit_manager.get_status()

            if not breaker_status:
                return {"status": "healthy", "details": "No circuit breakers configured"}

            # Determine overall status
            open_breakers = [name for name, status in breaker_status.items() if status["state"] == "open"]
            half_open_breakers = [name for name, status in breaker_status.items() if status["state"] == "half_open"]

            if open_breakers:
                status = "unhealthy"
                details = f"Circuit breakers OPEN: {', '.join(open_breakers)}"
            elif half_open_breakers:
                status = "degraded"
                details = f"Circuit breakers testing recovery: {', '.join(half_open_breakers)}"
            else:
                status = "healthy"
                details = "All circuit breakers operational"

            return {"status": status, "details": details, "breakers": breaker_status}
        except Exception as e:
            logger.error(f"Circuit breaker health check failed: {e}")
            return {"status": "unhealthy", "details": f"Circuit breaker check failed: {str(e)}"}

    def check_rate_limiters(self) -> Dict[str, Any]:
        """Check status of all rate limiters."""
        try:
            limiter_status = rate_limiter_manager.get_status()

            if not limiter_status:
                return {"status": "healthy", "details": "No rate limiters configured"}

            # Check if any limiters are near capacity
            degraded_limiters = []
            for name, status in limiter_status.items():
                if "available_tokens" in status and "capacity" in status:
                    utilization = 1 - (status["available_tokens"] / status["capacity"])
                    if utilization > 0.8:  # 80% utilization
                        degraded_limiters.append(name)

            if degraded_limiters:
                status = "degraded"
                details = f"High utilization rate limiters: {', '.join(degraded_limiters)}"
            else:
                status = "healthy"
                details = "All rate limiters operational"

            return {"status": status, "details": details, "limiters": limiter_status}
        except Exception as e:
            logger.error(f"Rate limiter health check failed: {e}")
            return {"status": "unhealthy", "details": f"Rate limiter check failed: {str(e)}"}

    # Documentation config checks removed with documentation agent cleanup


health_checker = HealthChecker()


@router.get("/")
async def basic_health():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "golfdaddy-brain",
        "version": "1.0.0",
    }


@router.get("/detailed")
async def detailed_health(supabase: Client = Depends(get_supabase_client)):
    """Detailed health check with all dependencies."""
    if not health_checker.detailed_checks:
        return {
            "status": "healthy",
            "message": "Detailed health checks disabled",
            "timestamp": datetime.now().isoformat(),
        }

    # Run all health checks in parallel
    health_checks = await asyncio.gather(
        health_checker.check_database(supabase),
        health_checker.check_github_api(),
        health_checker.check_openai_api(),
        return_exceptions=True,
    )

    # Get synchronous checks
    circuit_breaker_status = health_checker.check_circuit_breakers()
    rate_limiter_status = health_checker.check_rate_limiters()
    # Documentation agent checks removed

    # Compile results
    results = {
        "database": (
            health_checks[0]
            if not isinstance(health_checks[0], Exception)
            else {"status": "error", "details": str(health_checks[0])}
        ),
        "github_api": (
            health_checks[1]
            if not isinstance(health_checks[1], Exception)
            else {"status": "error", "details": str(health_checks[1])}
        ),
        "openai_api": (
            health_checks[2]
            if not isinstance(health_checks[2], Exception)
            else {"status": "error", "details": str(health_checks[2])}
        ),
        "circuit_breakers": circuit_breaker_status,
        "rate_limiters": rate_limiter_status,
        # Documentation config removed
    }

    # Determine overall status
    all_statuses = [check["status"] for check in results.values()]

    if "unhealthy" in all_statuses:
        overall_status = "unhealthy"
    elif "degraded" in all_statuses:
        overall_status = "degraded"
    elif "error" in all_statuses:
        overall_status = "error"
    else:
        overall_status = "healthy"

    return {"status": overall_status, "timestamp": datetime.now().isoformat(), "checks": results}

    # Removed: Documentation-specific health endpoint


@router.get("/metrics")
async def performance_metrics():
    """Get performance metrics and statistics."""
    try:
        circuit_breaker_status = circuit_manager.get_status()
        rate_limiter_status = rate_limiter_manager.get_status()

        # Calculate some basic metrics
        total_breakers = len(circuit_breaker_status)
        open_breakers = sum(1 for status in circuit_breaker_status.values() if status["state"] == "open")

        total_limiters = len(rate_limiter_status)
        average_utilization = 0
        if rate_limiter_status:
            utilizations = []
            for status in rate_limiter_status.values():
                if "available_tokens" in status and "capacity" in status:
                    utilization = 1 - (status["available_tokens"] / status["capacity"])
                    utilizations.append(utilization)
            if utilizations:
                average_utilization = sum(utilizations) / len(utilizations)

        return {
            "timestamp": datetime.now().isoformat(),
            "circuit_breakers": {
                "total": total_breakers,
                "open": open_breakers,
                "closed": total_breakers - open_breakers,
                "details": circuit_breaker_status,
            },
            "rate_limiters": {
                "total": total_limiters,
                "average_utilization": round(average_utilization * 100, 2),
                "details": rate_limiter_status,
            },
        }

    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get metrics: {str(e)}")


@router.post("/circuit-breakers/{breaker_name}/reset")
async def reset_circuit_breaker(breaker_name: str):
    """Manually reset a circuit breaker."""
    try:
        success = circuit_manager.reset_breaker(breaker_name)
        if success:
            return {
                "status": "success",
                "message": f"Circuit breaker '{breaker_name}' reset successfully",
                "timestamp": datetime.now().isoformat(),
            }
        else:
            raise HTTPException(status_code=404, detail=f"Circuit breaker '{breaker_name}' not found")

    except Exception as e:
        logger.error(f"Failed to reset circuit breaker {breaker_name}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to reset circuit breaker: {str(e)}")
