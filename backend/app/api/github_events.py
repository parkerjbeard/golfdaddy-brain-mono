from fastapi import APIRouter, Depends, HTTPException, status, Request, Security
from fastapi.security import APIKeyHeader
import logging
import base64

from app.config.database import get_db
from app.config.settings import settings
from app.schemas.github_event import CommitPayload
from app.services.commit_analysis_service import CommitAnalysisService
from app.integrations.github_integration import GitHubIntegration
from supabase import Client
from app.core.exceptions import AuthenticationError, DatabaseError, ExternalServiceError, AIIntegrationError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/integrations/github", tags=["Integrations - GitHub"])

# Define API Key Security
api_key_header = APIKeyHeader(name=settings.api_key_header, auto_error=False)

async def get_api_key(request: Request, api_key_header: str = Security(api_key_header)):
    """Dependency to validate the incoming API key from Make.com."""
    # Log the received key header for debugging
    actual_header_name = settings.api_key_header
    received_value = request.headers.get(actual_header_name)
    logger.info(f"Attempting API key authentication. Header '{actual_header_name}': Received value '{received_value}' (Type: {type(received_value)})")
    
    # Enhanced debugging
    # Log all request headers to see what's being sent
    logger.info(f"All request headers: {dict(request.headers)}")
    
    # Check both uppercase and lowercase header names
    for header_name in [actual_header_name, actual_header_name.upper(), actual_header_name.lower()]:
        value = request.headers.get(header_name)
        if value:
            logger.info(f"Found header '{header_name}' with value '{value[:5]}...'")
    
    # Log the key comparison target
    logger.info(f"Comparing against expected MAKE_INTEGRATION_API_KEY: '{settings.make_integration_api_key[:5]}...' (Length: {len(settings.make_integration_api_key) if settings.make_integration_api_key else 0})")

    # Check if API auth is enabled and a key was provided
    # Note: The `api_key_header` variable here is the *parsed* value by FastAPI/Security, 
    # which might be None if the header is missing. `received_value` above gets the raw header.
    if not settings.enable_api_auth or not received_value: # Check raw received_value first
         # If auth is disabled globally, allow access (or handle as needed)
         if not settings.enable_api_auth:
              logger.warning("API Auth is disabled globally. Allowing request without key.")
              return None # Indicate no key was validated but processing can continue
         else:
              logger.error(f"API key header '{actual_header_name}' is missing")
              raise AuthenticationError(message=f"API key header '{actual_header_name}' is missing")

    # Debug - encode both values for comparison
    received_encoded = base64.b64encode(received_value.encode()).decode() if received_value else None
    expected_encoded = base64.b64encode(settings.make_integration_api_key.encode()).decode() if settings.make_integration_api_key else None
    logger.info(f"Received key (base64): {received_encoded}")
    logger.info(f"Expected key (base64): {expected_encoded}")

    # Now use the raw received_value for comparison
    if received_value == settings.make_integration_api_key: 
        logger.info(f"API Key validation successful for key starting with: {received_value[:5]}...")
        return received_value # Return the validated key
    else:
        # Log safely - show only a few chars of the received incorrect key
        safe_received = received_value[:5] + '...' if received_value else 'None'
        logger.error(f"Invalid API key received. Value starting with: {safe_received}")
        raise AuthenticationError(message="Invalid API Key")

@router.post("/commit", status_code=status.HTTP_202_ACCEPTED)
async def handle_commit_event(
    payload: CommitPayload,
    request: Request, 
    scan_docs: bool = None,
    api_key: str = Depends(get_api_key), # Apply API key security
    db_session: Client = Depends(get_db)  # Get DB session as a dependency directly
):
    """
    Receives commit information (likely forwarded by Make.com).
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

    # Check API key (already done by dependency, but ensures it was valid if required)
    if settings.enable_api_auth and api_key is None:
         # This case should ideally be caught by the dependency, but double-check
         raise AuthenticationError(message="Unauthorized")

    try:
        # Check if we got a valid session
        if db_session is None:
            logger.error("DB session is None from dependency.")
            raise DatabaseError(message="Database session unavailable")

        # Initialize service with the obtained session
        commit_analysis_service = CommitAnalysisService(db_session)
        
        # The 'payload' object is already a validated CommitPayload instance.
        # We can pass it directly to the service.
        # The service's process_commit method is designed to handle CommitPayload objects.

        # Process the commit (which includes finding user, fetching diff if needed, calling AI, saving)
        result_commit = await commit_analysis_service.process_commit(payload, scan_docs=scan_docs) # Pass payload directly
        
        if result_commit:
            logger.info(f"Successfully processed commit {payload.commit_hash}. AI analysis scheduled/completed.")
            return {"message": "Commit received and processing started/completed", "commit_hash": payload.commit_hash}
        else:
            # Logged within the service, return a more specific error
            logger.error(f"process_commit returned falsy for commit {payload.commit_hash}. Indicates failure in service.")
            raise AIIntegrationError(message="Failed to process commit due to an issue in the analysis service.")
    
    except HTTPException as http_exc: # Re-raise HTTP exceptions from FastAPI/dependencies
        raise http_exc
    except AuthenticationError as auth_exc: # Re-raise our custom auth errors
        raise auth_exc
    except (DatabaseError, AIIntegrationError, ExternalServiceError) as app_exc: # Re-raise other known app errors
        raise app_exc
    except Exception as e:
        logger.error(f"Unhandled exception processing commit {payload.commit_hash}: {e}", exc_info=True)
        raise AIIntegrationError(message=f"An unexpected error occurred while processing commit: {str(e)}")

@router.get("/compare/{repository}/{base}/{head}", status_code=status.HTTP_200_OK)
async def compare_commits(
    repository: str,
    base: str,
    head: str,
    api_key: str = Depends(get_api_key), # Apply API key security
    db_session: Client = Depends(get_db)  # Get DB session as a dependency directly
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
            raise ExternalServiceError(service_name="GitHub", original_message="Failed to compare commits, the GitHub integration returned no data.")
    
    except HTTPException as http_exc: # Re-raise HTTP exceptions
        raise http_exc
    except AuthenticationError as auth_exc: # Re-raise our custom auth errors
        raise auth_exc
    except ExternalServiceError as ext_exc: # Re-raise our custom external service errors
        raise ext_exc        
    except Exception as e:
        logger.error(f"Error comparing commits {base}...{head}: {e}", exc_info=True)
        raise ExternalServiceError(service_name="GitHub", original_message=f"Error comparing commits: {str(e)}") 