from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


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


class BranchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_id: int
    branch_code: str
    name: str
    is_head_office: bool
    status: str


class OrganizationSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    organization_code: str
    legal_name: str
    display_name: str | None
    default_currency_code: str
    timezone: str
    status: str


class AuthUser(BaseModel):
    id: int
    name: str
    email: str
    role: str
    avatar: str | None = None
    permissions: list[str] = []
    pageAccess: list[str] = []
    organizationId: int | None = None
    organizationCode: str | None = None
    organizationName: str | None = None
    branchId: int | None = None
    branchName: str | None = None
    assignedBranchIds: list[int] = []
    permissionScope: str = "BRANCH"
    sourcePermissions: list[str] = []


class LoginResponse(BaseModel):
    user: AuthUser
    access_token: str | None = None
    refresh_token: str | None = None
    token_type: str = "Bearer"
    expires_in: int = 3600


class UserCreate(BaseModel):
    user_code: str | None = None
    username: str
    email: EmailStr
    display_name: str
    password: str | None = Field(default=None, min_length=6)
    phone: str | None = None
    role_code: str | None = None
    organization_id: int | None = None
    branch_id: int | None = None
    status: str = "ACTIVE"


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    display_name: str | None = None
    phone: str | None = None
    status: str | None = None
    locale: str | None = None
    timezone: str | None = None


class RoleAssignmentCreate(BaseModel):
    role_id: int | None = None
    role_code: str | None = None
    organization_id: int | None = None
    branch_id: int | None = None
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
