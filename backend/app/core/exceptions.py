from __future__ import annotations

from fastapi import HTTPException, status


class DomainError(HTTPException):
    """Business-rule error with a stable machine-readable code.

    ``field_errors`` is the legacy ``{field: message}`` map every existing form
    reads. ``errors`` is the ordered, coded list newer clients consume; when it
    is omitted the exception handler derives it from ``field_errors`` so every
    refusal has the same shape regardless of which call site raised it.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        field_errors: dict[str, str] | None = None,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(
            status_code=status_code,
            detail={
                "code": code,
                "message": message,
                "field_errors": field_errors,
                "errors": errors,
            },
        )
        self.code = code
        self.message = message
        self.field_errors = field_errors
        self.errors = errors


class AuthRequired(DomainError):
    def __init__(self, message: str = "Authentication required.", *, code: str = "AUTH_REQUIRED") -> None:
        super().__init__(code, message, status_code=status.HTTP_401_UNAUTHORIZED)


class AccessDenied(DomainError):
    def __init__(self, message: str = "You do not have permission to perform this action.") -> None:
        super().__init__("ACCESS_DENIED", message, status_code=status.HTTP_403_FORBIDDEN)


class NotFound(DomainError):
    def __init__(self, message: str = "Record not found.") -> None:
        super().__init__("REFERENCE_NOT_FOUND", message, status_code=status.HTTP_404_NOT_FOUND)


class Conflict(DomainError):
    def __init__(self, code: str, message: str, field_errors: dict[str, str] | None = None) -> None:
        super().__init__(code, message, status_code=status.HTTP_409_CONFLICT, field_errors=field_errors)


class InvalidState(DomainError):
    def __init__(self, message: str) -> None:
        super().__init__("INVALID_STATE_TRANSITION", message, status_code=status.HTTP_409_CONFLICT)


class ValidationFailed(DomainError):
    def __init__(
        self,
        message: str,
        field_errors: dict[str, str] | None = None,
        errors: list[dict[str, str]] | None = None,
    ) -> None:
        super().__init__(
            "VALIDATION_ERROR",
            message,
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            field_errors=field_errors,
            errors=errors,
        )
