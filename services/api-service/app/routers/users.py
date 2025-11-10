"""User role management endpoints."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.auth import get_current_user, invalidate_role_cache, require_role
from app.core.firestore_client import firestore_client
from app.models import CreateRoleRequest, RoleAssignment, RoleListResponse, UserInfo, UserRole

router = APIRouter()


@router.get("/me", response_model=UserInfo)
async def get_current_user_info(user: UserInfo = Depends(get_current_user)):
    """Get current user information and role."""
    return user


@router.get("/roles", response_model=RoleListResponse)
@require_role(UserRole.ADMIN)
async def list_role_assignments(
    user: UserInfo = Depends(get_current_user),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """
    List all role assignments (admin only).

    Args:
        limit: Maximum results to return
        offset: Number of results to skip
        user: Current user (injected by dependency)

    Returns:
        List of role assignments
    """
    try:
        role_collection = firestore_client.db.collection("user_roles")

        # Count total assignments
        all_docs = list(role_collection.stream())
        total = len(all_docs)

        # Apply pagination manually (Firestore doesn't have built-in offset)
        paginated_docs = all_docs[offset : offset + limit]

        assignments = []
        for doc in paginated_docs:
            data = doc.to_dict()
            assignments.append(
                RoleAssignment(
                    email=data.get("email"),
                    domain=data.get("domain"),
                    role=UserRole(data["role"]),
                    assigned_by=data["assigned_by"],
                    assigned_at=data["assigned_at"],
                    notes=data.get("notes"),
                )
            )

        return RoleListResponse(assignments=assignments, total=total)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list role assignments: {str(e)}")


@router.post("/roles", response_model=RoleAssignment)
@require_role(UserRole.ADMIN)
async def create_role_assignment(
    request: CreateRoleRequest,
    user: UserInfo = Depends(get_current_user),
):
    """
    Create a new role assignment (admin only).

    Args:
        request: Role assignment details
        user: Current user (injected by dependency)

    Returns:
        Created role assignment
    """
    try:
        role_collection = firestore_client.db.collection("user_roles")

        # Check if assignment already exists
        if request.email:
            existing = list(role_collection.where("email", "==", request.email.lower()).limit(1).stream())
            identifier = request.email.lower()
        else:
            existing = list(role_collection.where("domain", "==", request.domain.lower()).limit(1).stream())
            identifier = request.domain.lower()

        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Role assignment already exists for {request.email or request.domain}",
            )

        # Create assignment
        now = datetime.now(timezone.utc)
        assignment = RoleAssignment(
            email=request.email.lower() if request.email else None,
            domain=request.domain.lower() if request.domain else None,
            role=request.role,
            assigned_by=user.email,
            assigned_at=now,
            notes=request.notes,
        )

        # Store in Firestore
        doc_id = identifier.replace("@", "_at_").replace(".", "_")
        role_collection.document(doc_id).set(assignment.model_dump(mode="json"))

        # Invalidate cache for this user/domain
        if request.email:
            invalidate_role_cache(request.email)
        else:
            # Invalidate entire cache since domain rule affects multiple users
            invalidate_role_cache()

        return assignment

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create role assignment: {str(e)}")


@router.put("/roles/{identifier}", response_model=RoleAssignment)
@require_role(UserRole.ADMIN)
async def update_role_assignment(
    identifier: str,  # Email or domain (with @ and . replaced)
    role: UserRole,
    notes: str | None = None,
    user: UserInfo = Depends(get_current_user),
):
    """
    Update an existing role assignment (admin only).

    Args:
        identifier: Document ID (email or domain with special chars replaced)
        role: New role to assign
        notes: Optional notes
        user: Current user (injected by dependency)

    Returns:
        Updated role assignment
    """
    try:
        role_collection = firestore_client.db.collection("user_roles")
        doc_ref = role_collection.document(identifier)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Role assignment {identifier} not found")

        # Update the role and notes
        data = doc.to_dict()
        data["role"] = role.value
        data["notes"] = notes
        data["assigned_by"] = user.email
        data["assigned_at"] = datetime.now(timezone.utc)

        doc_ref.set(data)

        # Invalidate cache
        if data.get("email"):
            invalidate_role_cache(data["email"])
        else:
            invalidate_role_cache()

        return RoleAssignment(
            email=data.get("email"),
            domain=data.get("domain"),
            role=role,
            assigned_by=user.email,
            assigned_at=data["assigned_at"],
            notes=notes,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update role assignment: {str(e)}")


@router.delete("/roles/{identifier}")
@require_role(UserRole.ADMIN)
async def delete_role_assignment(
    identifier: str,
    user: UserInfo = Depends(get_current_user),
):
    """
    Delete a role assignment (admin only).

    Args:
        identifier: Document ID (email or domain with special chars replaced)
        user: Current user (injected by dependency)

    Returns:
        Success message
    """
    try:
        role_collection = firestore_client.db.collection("user_roles")
        doc_ref = role_collection.document(identifier)
        doc = doc_ref.get()

        if not doc.exists:
            raise HTTPException(status_code=404, detail=f"Role assignment {identifier} not found")

        # Get email/domain before deleting for cache invalidation
        data = doc.to_dict()

        # Delete the document
        doc_ref.delete()

        # Invalidate cache
        if data.get("email"):
            invalidate_role_cache(data["email"])
        else:
            invalidate_role_cache()

        return {"success": True, "message": f"Role assignment {identifier} deleted"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete role assignment: {str(e)}")
