import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader

from app.config.supabase_client import get_supabase_client_safe as get_db
from app.config.settings import settings
from app.core.exceptions import AIIntegrationError, AuthenticationError, DatabaseError, ExternalServiceError
from app.integrations.github_integration import GitHubIntegration
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService
from supabase import Client

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/integrations/github", tags=["Integrations - GitHub"])

api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)


async def get_api_key(request: Request, api_key_header: str = Security(api_key_header)):
    """Validate incoming API key from an external system."""
    actual_header_name = settings.api_key_header
    received_value = request.headers.get(actual_header_name)
    logger.info(f"Attempting API key authentication for header '{actual_header_name}'")

    if not settings.enable_api_auth or not received_value:
        if not settings.enable_api_auth:
            logger.warning("API Auth is disabled globally. Allowing request without key.")
            return None
        logger.error(f"API key header '{actual_header_name}' is missing")
        raise AuthenticationError(message=f"API key header '{actual_header_name}' is missing")

    if received_value == settings.make_integration_api_key:
        logger.info("API Key validation successful")
        return received_value
    else:
        logger.error("Invalid API key received")
        raise AuthenticationError(message="Invalid API Key")


@router.post("/commit", status_code=status.HTTP_202_ACCEPTED)
async def handle_commit_event(
    payload: CommitPayload,
    request: Request,
    scan_docs: bool = None,
    api_key: str = Depends(get_api_key),
    db_session: Client = Depends(get_db),
):
    """
    Receives commit information posted by an external system.
    Validates the payload, finds the user, triggers AI analysis,
    optionally fetches diff content from GitHub if needed,
    and saves the commit record.
    Returns 202 Accepted immediately as AI analysis might take time.

    Args:
        payload: The commit payload
        request: The HTTP request
        scan_docs: Whether to scan documentation (None = use global setting)
        api_key: API key for authentication
        db_session: Database session
    """
    logger.info(f"Received commit webhook for hash: {payload.commit_hash}")

    if settings.enable_api_auth and api_key is None:
        raise AuthenticationError(message="Unauthorized")

    try:
        if db_session is None:
            logger.error("DB session is None from dependency.")
            raise DatabaseError(message="Database session unavailable")

        commit_analysis_service = CommitAnalysisService(db_session)

        result_commit = await commit_analysis_service.process_commit(payload, scan_docs=scan_docs)

        if result_commit:
            logger.info(f"Successfully processed commit {payload.commit_hash}. AI analysis scheduled/completed.")
            return {"message": "Commit received and processing started/completed", "commit_hash": payload.commit_hash}
        else:
            logger.error(
                f"process_commit returned falsy for commit {payload.commit_hash}. Indicates failure in service."
            )
            raise AIIntegrationError(message="Failed to process commit due to an issue in the analysis service.")

    except HTTPException as http_exc:
        raise http_exc
    except AuthenticationError as auth_exc:
        raise auth_exc
    except (DatabaseError, AIIntegrationError, ExternalServiceError) as app_exc:
        raise app_exc
    except Exception as e:
        logger.error(f"Unhandled exception processing commit {payload.commit_hash}: {e}", exc_info=True)
        raise AIIntegrationError(message=f"An unexpected error occurred while processing commit: {str(e)}")


@router.get("/compare/{repository}/{base}/{head}", status_code=status.HTTP_200_OK)
async def compare_commits(
    repository: str,
    base: str,
    head: str,
    api_key: str = Depends(get_api_key),  # Apply API key security
    db_session: Client = Depends(get_db),  # Get DB session as a dependency directly
):
    """
    Compare two commits in a repository using the GitHub API.

    Args:
        repository: Repository name (format: "owner/repo")
        base: Base commit SHA to compare from
        head: Head commit SHA to compare to

    Returns:
        JSON response with the comparison data
    """
    logger.info(f"Comparing commits {base}...{head} in repository {repository}")

    # Check API key (already done by dependency, but ensures it was valid if required)
    if settings.enable_api_auth and api_key is None:
        raise AuthenticationError(message="Unauthorized")

    try:
        # Initialize GitHub integration
        github_integration = GitHubIntegration()

        # Call the compare_commits method to get the comparison data
        comparison_data = github_integration.compare_commits(repository, base, head)

        if comparison_data:
            logger.info(f"Successfully compared commits {base}...{head}")
            return comparison_data
        else:
            raise ExternalServiceError(
                service_name="GitHub",
                original_message="Failed to compare commits, the GitHub integration returned no data.",
            )

    except HTTPException as http_exc:  # Re-raise HTTP exceptions
        raise http_exc
    except AuthenticationError as auth_exc:  # Re-raise our custom auth errors
        raise auth_exc
    except ExternalServiceError as ext_exc:  # Re-raise our custom external service errors
        raise ext_exc
    except Exception as e:
        logger.error(f"Error comparing commits {base}...{head}: {e}", exc_info=True)
        raise ExternalServiceError(service_name="GitHub", original_message=f"Error comparing commits: {str(e)}")
