from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from api.deps.permissions import CurrentUser, require_permission
from db.database import get_db
from services.audit_service import record_audit
from services.erp_export_service import build_export_filename, build_reconciliation_csv
from services.reconciliation_service import get_reconciliation

router = APIRouter(prefix="/api/v1/erp-export", tags=["erp-export"])


@router.get("/reconciliation/{reconciliation_id}")
async def export_reconciliation_endpoint(
    reconciliation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(require_permission("erp_export", "export")),
) -> Response:
    reconciliation = await get_reconciliation(db, reconciliation_id)
    if reconciliation is None:
        raise HTTPException(status_code=404, detail="Reconciliation not found")

    csv_bytes = build_reconciliation_csv(reconciliation)
    filename = build_export_filename(reconciliation)

    await record_audit(
        db,
        user_id=UUID(current_user.user_id),
        role_used=current_user.role,
        action="export",
        resource_type="reconciliation",
        resource_id=reconciliation.id,
        detail={"filename": filename, "line_count": len(reconciliation.lines)},
    )

    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
