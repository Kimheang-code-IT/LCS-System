from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: str | None = Field(default=None, max_length=255)
    email: str | None = Field(default=None, max_length=255)
    password: str = Field(max_length=128)
    remember_me: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str = Field(pattern=r"^\d{6}$")
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str | None = Field(default=None, max_length=128)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(max_length=128)
    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str | None = Field(default=None, max_length=128)


class SetPasswordRequest(BaseModel):
    """An administrator setting another account's password.

    ``must_change_password`` defaults to true: the account owner did not choose
    this password, so a temporary one should not be able to stay in use indefinitely.
    """

    model_config = ConfigDict(populate_by_name=True)

    password: str = Field(min_length=8, max_length=128)
    password_confirmation: str | None = Field(default=None, max_length=128)
    must_change_password: bool = Field(
        default=True,
        validation_alias=AliasChoices("must_change_password", "mustChangePassword"),
    )


class UserCreate(BaseModel):
    # Accept both the API snake_case form and the frontend camelCase form.
    model_config = ConfigDict(populate_by_name=True)

    user_code: str | None = Field(default=None, validation_alias=AliasChoices("user_code", "userCode"))
    username: str
    email: EmailStr
    display_name: str = Field(validation_alias=AliasChoices("display_name", "displayName", "name"))
    password: str | None = Field(default=None, min_length=8, max_length=128)
    roles: list[str] | None = None
    role_code: str | None = Field(default=None, validation_alias=AliasChoices("role_code", "roleCode", "role"))
    status: str = "ACTIVE"


class UserUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_code: str | None = Field(default=None, validation_alias=AliasChoices("user_code", "userCode"))
    email: EmailStr | None = None
    display_name: str | None = Field(default=None, validation_alias=AliasChoices("display_name", "displayName"))
    status: str | None = None
    locale: str | None = None
    timezone: str | None = None
    roles: list[str] | None = None
    role_code: str | None = Field(default=None, validation_alias=AliasChoices("role_code", "roleCode", "role"))


class RoleAssignmentCreate(BaseModel):
    role_id: int | None = None
    role_code: str | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None


class RoleCreate(BaseModel):
    # `code` is optional: when omitted the service derives a stable code from
    # the role name, so the UI only needs to collect a name.
    code: str | None = None
    name: str
    description: str | None = None
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    permissions: list[str] | None = None


class RoleDuplicate(BaseModel):
    name: str | None = None
    code: str | None = None
