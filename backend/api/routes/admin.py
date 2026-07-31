from fastapi import APIRouter, Depends

from api.deps.permissions import CurrentUser, require_permission
from api.models import PermissionMatrixResponse
from config.permissions import PERMISSIONS

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.get("/permissions", response_model=PermissionMatrixResponse)
async def get_permission_matrix_endpoint(
    _current_user: CurrentUser = Depends(require_permission("system_config", "view")),
) -> PermissionMatrixResponse:
    matrix = {
        resource: {
            action: sorted(role.value for role in roles)
            for action, roles in actions.items()
        }
        for resource, actions in PERMISSIONS.items()
    }
    return PermissionMatrixResponse(matrix=matrix)
