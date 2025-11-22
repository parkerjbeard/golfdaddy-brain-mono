from typing import Optional, Union

from fastapi import HTTPException, status


class AppExceptionBase(Exception):
    """Base class for application-specific exceptions."""

    def __init__(
        self,
        message: str,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        code: str = "INTERNAL_SERVER_ERROR",
    ):
        self.message = message
        self.status_code = status_code
        self.code = code
        super().__init__(message)


class ResourceNotFoundError(AppExceptionBase):
    """Raised when a requested resource is not found."""

    def __init__(self, resource_name: str, resource_id: Union[str, int]):
        message = f"The {resource_name} with ID '{resource_id}' was not found."
        super().__init__(message=message, status_code=status.HTTP_404_NOT_FOUND, code="RESOURCE_NOT_FOUND")


class DuplicateResourceError(AppExceptionBase):
    """Raised when attempting to create a duplicate resource."""

    def __init__(self, resource_name: str, identifier: Optional[str] = None):
        message = f"A {resource_name} with the same identifier already exists"
        if identifier:
            message += f": {identifier}"
        super().__init__(message=message, status_code=status.HTTP_409_CONFLICT, code="DUPLICATE_RESOURCE")


class PermissionDeniedError(AppExceptionBase):
    """Raised when an action is attempted without sufficient permissions."""

    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(message=message, status_code=status.HTTP_403_FORBIDDEN, code="PERMISSION_DENIED")


class AIIntegrationError(AppExceptionBase):
    """Raised when there's an error integrating with an AI service."""

    def __init__(self, message: str = "An error occurred while integrating with the AI service."):
        super().__init__(
            message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, code="AI_INTEGRATION_ERROR"
        )


class DatabaseError(AppExceptionBase):
    """Raised when a database operation fails."""

    def __init__(self, message: str = "A database error occurred."):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, code="DATABASE_ERROR")


class ConfigurationError(AppExceptionBase):
    """Raised when there's an issue with the application's configuration."""

    def __init__(self, message: str = "A configuration error occurred."):
        super().__init__(message=message, status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, code="CONFIGURATION_ERROR")


class ExternalServiceError(AppExceptionBase):
    """Raised when an external service call fails."""

    def __init__(self, service_name: str, original_message: Optional[str] = None):
        message = f"An error occurred while communicating with {service_name}."
        if original_message:
            message += f" Details: {original_message}"
        super().__init__(message=message, status_code=status.HTTP_502_BAD_GATEWAY, code="EXTERNAL_SERVICE_ERROR")


class AuthenticationError(AppExceptionBase):
    """Raised for authentication failures."""

    def __init__(self, message: str = "Authentication failed."):
        super().__init__(message=message, status_code=status.HTTP_401_UNAUTHORIZED, code="AUTHENTICATION_ERROR")


class RateLimitExceededError(AppExceptionBase):
    """Raised when a rate limit is exceeded.

    Optionally includes `retry_after` seconds and `service_name` for callers
    to present more helpful messaging or headers.
    """

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        *,
        retry_after: Optional[float] = None,
        service_name: Optional[str] = None,
    ):
        super().__init__(message=message, status_code=status.HTTP_429_TOO_MANY_REQUESTS, code="RATE_LIMIT_EXCEEDED")
        self.retry_after = retry_after
        self.service_name = service_name


class BadRequestError(AppExceptionBase):
    """Raised for malformed requests or invalid input."""

    def __init__(self, message: str = "Bad request. Please check your input."):
        super().__init__(message=message, status_code=status.HTTP_400_BAD_REQUEST, code="BAD_REQUEST")


class ValidationError(AppExceptionBase):
    """Raised when input validation fails."""

    def __init__(self, message: str = "Validation failed. Please check your input."):
        super().__init__(message=message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, code="VALIDATION_ERROR")
