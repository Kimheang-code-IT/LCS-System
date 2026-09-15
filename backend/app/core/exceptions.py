from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status


class DomainError(HTTPException):
    """Business-rule error with a stable machine-readable code."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        field_errors: dict[str, str] | None = None,
    ) -> None:
        super().__init__(status_code=status_code, detail={"code": code, "message": message, "field_errors": field_errors})
        self.code = code
        self.message = message
        self.field_errors = field_errors


class AuthRequired(DomainError):
    def __init__(self, message: str = "Authentication required.") -> None:
        super().__init__("AUTH_REQUIRED", message, status_code=status.HTTP_401_UNAUTHORIZED)


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
    def __init__(self, message: str, field_errors: dict[str, str] | None = None) -> None:
        super().__init__("VALIDATION_ERROR", message, status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, field_errors=field_errors)


def error_payload(code: str, message: str, request_id: str | None, field_errors: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "request_id": request_id or "", "field_errors": field_errors or {}}
