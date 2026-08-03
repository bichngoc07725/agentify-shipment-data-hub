from fastapi import APIRouter, Depends

from api.deps.permissions import CurrentUser, get_current_user
from api.models import ExtractionStatusResponse
from services.extraction_status_service import get_extraction_status

router = APIRouter(prefix="/api/v1/system", tags=["system"])


@router.get("/extraction-status", response_model=ExtractionStatusResponse)
async def get_extraction_status_endpoint(
    _current_user: CurrentUser = Depends(get_current_user),
) -> ExtractionStatusResponse:
    """Cho biết OCR ảnh / trích văn bản hiện có chạy được không.

    Chỉ cần đăng nhập, không giới hạn theo vai trò: Ops và Tài xế là người
    upload ảnh nên họ phải biết ảnh có được đọc hay không — đây là thông tin
    vận hành, không phải bí mật cấu hình (không trả về giá trị key nào).
    """
    return ExtractionStatusResponse(**get_extraction_status())
