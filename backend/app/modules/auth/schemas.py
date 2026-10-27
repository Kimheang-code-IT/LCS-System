from __future__ import annotations

from datetime import datetime

from email_validator import EmailNotValidError, validate_email
from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field, field_validator


class SetupInitializeRequest(BaseModel):
    """First-run administrator bootstrap.

    Unknown keys are refused: the endpoint is public until the first user
    exists, so accepting arbitrary fields would also store them in the audit
    trail of the installation.
    """

    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    password: str = Field(max_length=128)
    name: str | None = Field(default=None, max_length=255)
    username: str | None = Field(default=None, max_length=255)

    @field_validator("email")
    @classmethod
    def _validate_email(cls, value: str) -> str:
        """Validate the address without rejecting reserved test domains.

        ``EmailStr`` refuses ``.test``/``.invalid`` as special-use. Those are
        exactly the domains a first-run or integration test uses, and the setup
        endpoint is the public bootstrap path, so it accepts a syntactically
        valid address without a deliverability claim.
        """
        try:
            return validate_email(
                value,
                check_deliverability=False,
                test_environment=True,
            ).normalized
        except EmailNotValidError as exc:
            raise ValueError("Enter a valid email address.") from exc


class AvatarUpdate(BaseModel):
    """The avatar is a URL or an inline image data URL."""

    model_config = ConfigDict(extra="forbid")

    avatar: str | None = Field(default=None, max_length=500_000)


class LoginRequest(BaseModel):
    username: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    password: str = Field(max_length=128)
    remember_me: bool = False


class RefreshRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ForgotPasswordRequest(BaseModel):
    email: str = Field(min_length=1, max_length=255, validation_alias=AliasChoices("email", "username", "identifier"))


class VerifyCodeRequest(BaseModel):
    email: str = Field(default="", max_length=255)
    code: str = Field(min_length=40, max_length=128, validation_alias=AliasChoices("token", "code"))


class ResetPasswordRequest(BaseModel):
    email: str = Field(default="", max_length=255)
    code: str = Field(min_length=40, max_length=128, validation_alias=AliasChoices("token", "code"))
    password: str = Field(max_length=128)
    password_confirmation: str | None = Field(default=None, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    password: str = Field(max_length=128)
    password_confirmation: str | None = Field(default=None, max_length=128)


class SetPasswordRequest(BaseModel):
    """An administrator setting another account's password.

    ``must_change_password`` defaults to true: the account owner did not choose
    this password, so a temporary one should not be able to stay in use indefinitely.
    """

    model_config = ConfigDict(populate_by_name=True)

    password: str = Field(max_length=128)
    password_confirmation: str | None = Field(default=None, max_length=128)
    must_change_password: bool = Field(
        default=True,
        validation_alias=AliasChoices("must_change_password", "mustChangePassword"),
    )


class UserCreate(BaseModel):
    # Accept both the API snake_case form and the frontend camelCase form.
    model_config = ConfigDict(populate_by_name=True)

    user_code: str | None = Field(default=None, max_length=50, validation_alias=AliasChoices("user_code", "userCode"))
    username: str = Field(min_length=1, max_length=255)
    email: EmailStr
    display_name: str = Field(
        min_length=1, max_length=255, validation_alias=AliasChoices("display_name", "displayName", "name")
    )
    password: str | None = Field(default=None, max_length=128)
    roles: list[str] | None = None
    role_code: str | None = Field(
        default=None, max_length=64, validation_alias=AliasChoices("role_code", "roleCode", "role")
    )
    status: str = Field(default="ACTIVE", max_length=20)


class UserUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_code: str | None = Field(default=None, max_length=50, validation_alias=AliasChoices("user_code", "userCode"))
    email: EmailStr | None = None
    display_name: str | None = Field(
        default=None, max_length=255, validation_alias=AliasChoices("display_name", "displayName")
    )
    status: str | None = Field(default=None, max_length=20)
    locale: str | None = Field(default=None, max_length=16)
    timezone: str | None = Field(default=None, max_length=64)
    roles: list[str] | None = None
    role_code: str | None = Field(
        default=None, max_length=64, validation_alias=AliasChoices("role_code", "roleCode", "role")
    )


class RoleAssignmentCreate(BaseModel):
    role_id: int | None = None
    role_code: str | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None


class RoleCreate(BaseModel):
    # `code` is optional: when omitted the service derives a stable code from
    # the role name, so the UI only needs to collect a name.
    code: str | None = Field(default=None, max_length=64)
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    status: str | None = Field(default=None, max_length=20)
    permissions: list[str] | None = None


class RoleDuplicate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=64)
