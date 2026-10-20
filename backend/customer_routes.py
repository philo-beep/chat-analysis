"""Read-only customer pages, always scoped to the signed-in account."""

from fastapi import APIRouter, Depends, HTTPException, Path, Query

import profile_store as store
from auth import permission

router = APIRouter(prefix="/api/customers", tags=["customers"])


def call(operation, *args, **kwargs):
    try:
        data = operation(*args, **kwargs)
    except store.ProfileError as exc:
        raise HTTPException(exc.status, exc.message) from exc
    return {"code": 0, "message": "ok", "data": data}


@router.get("")
def listing(q: str = Query("", max_length=300), limit: int = Query(50, ge=1, le=100),
            offset: int = Query(0, ge=0), user=Depends(permission("records:read"))):
    return call(store.list_customers, user["id"], q=q, limit=limit, offset=offset)


@router.get("/{profile_id}")
def detail(profile_id: int = Path(gt=0), user=Depends(permission("records:read"))):
    return call(store.get_customer, user["id"], profile_id)


@router.get("/{profile_id}/snapshots")
def timeline(profile_id: int = Path(gt=0), limit: int = Query(50, ge=1, le=100),
             offset: int = Query(0, ge=0), user=Depends(permission("records:read"))):
    return call(store.list_snapshots, user["id"], profile_id, limit=limit, offset=offset)


@router.get("/{profile_id}/snapshots/{snapshot_id}")
def snapshot(profile_id: int = Path(gt=0), snapshot_id: int = Path(gt=0),
             user=Depends(permission("records:read"))):
    return call(store.get_snapshot, user["id"], profile_id, snapshot_id)
