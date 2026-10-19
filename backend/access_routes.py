"""Administrator RBAC endpoints. All authorization is expressed as dependencies."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictStr

import auth
import auth_store
from auth_routes import RegisterBody, ok

router = APIRouter(prefix="/api/access-control", tags=["访问控制"])
PositiveId = Annotated[int, Field(strict=True, gt=0)]
ResourceId = Annotated[int, Path(gt=0)]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CreateUserBody(RegisterBody):
    role_ids: list[PositiveId] = Field(min_length=1, max_length=100)


class UserRolesBody(StrictBody):
    role_ids: list[PositiveId] = Field(max_length=100)


class ActiveBody(StrictBody):
    is_active: StrictBool


class RoleBody(StrictBody):
    code: StrictStr = Field(min_length=3, max_length=64, pattern=r"^[a-z][a-z0-9_-]+$")
    name: StrictStr = Field(min_length=1, max_length=100, pattern=r".*\S.*")


class RolePermissionsBody(StrictBody):
    permission_ids: list[PositiveId] = Field(max_length=100)


def call(operation, *args):
    try:
        return operation(*args)
    except LookupError as exc:
        raise HTTPException(404, str(exc))
    except ValueError as exc:
        raise HTTPException(422, str(exc))
    except sqlite3.IntegrityError:
        raise HTTPException(409, "名称已存在或关联数据冲突；未保存任何变更")


@router.get("/users")
def users(limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0),
          user: dict = Depends(auth.permission("users:read"))):
    return ok(auth_store.list_users(limit, offset))


@router.post("/users")
def create_user(body: CreateUserBody, user: dict = Depends(auth.administration_permission("users:write"))):
    return ok(call(auth_store.create_user_with_roles, body.username, body.password, body.role_ids))


@router.put("/users/{user_id}/roles")
def user_roles(user_id: ResourceId, body: UserRolesBody,
               user: dict = Depends(auth.administration_permission("users:write"))):
    return ok(call(auth_store.set_user_roles, user_id, body.role_ids))


@router.patch("/users/{user_id}")
def user_active(user_id: ResourceId, body: ActiveBody,
                user: dict = Depends(auth.administration_permission("users:write"))):
    return ok(call(auth_store.set_user_active, user_id, body.is_active))


@router.get("/roles")
def roles(user: dict = Depends(auth.permission("roles:read"))):
    return ok(auth_store.list_roles())


@router.post("/roles")
def create_role(body: RoleBody, user: dict = Depends(auth.administration_permission("roles:write"))):
    return ok(call(auth_store.create_role, body.code, body.name))


@router.put("/roles/{role_id}/permissions")
def role_permissions(role_id: ResourceId, body: RolePermissionsBody,
                     user: dict = Depends(auth.administration_permission("roles:write"))):
    return ok(call(auth_store.set_role_permissions, role_id, body.permission_ids))


@router.get("/permissions")
def permissions(user: dict = Depends(auth.permission("permissions:read"))):
    return ok(auth_store.list_permissions())
