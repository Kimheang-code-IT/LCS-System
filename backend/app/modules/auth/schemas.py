from __future__ import annotations

from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: str | None = None
    email: str | None = None
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class VerifyCodeRequest(BaseModel):
    email: EmailStr
    code: str


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    code: str
    password: str = Field(min_length=6)
    password_confirmation: str | None = None


class ChangePasswordRequest(BaseModel):
    current_password: str
    password: str = Field(min_length=6)
    password_confirmation: str | None = None


class AuthUser(BaseModel):
    id: int
    name: str
    email: str
    role: str
    avatar: str | None = None
    permissions: list[str] = []
    pageAccess: list[str] = []
    sourcePermissions: list[str] = []


class LoginResponse(BaseModel):
    user: AuthUser
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int = 3600


class UserCreate(BaseModel):
    # Accept both the API snake_case form and the frontend camelCase form.
    model_config = ConfigDict(populate_by_name=True)

    user_code: str | None = Field(default=None, validation_alias=AliasChoices("user_code", "userCode"))
    username: str
    email: EmailStr
    display_name: str = Field(validation_alias=AliasChoices("display_name", "displayName", "name"))
    password: str | None = Field(default=None, min_length=6)
    phone: str | None = None
    role_code: str | None = Field(default=None, validation_alias=AliasChoices("role_code", "roleCode", "role"))
    status: str = "ACTIVE"


class UserUpdate(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: EmailStr | None = None
    display_name: str | None = Field(default=None, validation_alias=AliasChoices("display_name", "displayName"))
    phone: str | None = None
    status: str | None = None
    locale: str | None = None
    timezone: str | None = None
    role_code: str | None = Field(default=None, validation_alias=AliasChoices("role_code", "roleCode", "role"))


class RoleAssignmentCreate(BaseModel):
    role_id: int | None = None
    role_code: str | None = None
    starts_at: datetime | None = None
    expires_at: datetime | None = None


class RoleCreate(BaseModel):
    code: str
    name: str
    description: str | None = None
    permissions: list[str] = []


class RoleUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    permissions: list[str] | None = None
