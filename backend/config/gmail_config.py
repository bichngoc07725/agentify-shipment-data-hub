from pydantic import BaseModel

from config import root_config

gmail_service = root_config.gmail_service
gmail_oauth = gmail_service.oauth
extraction = gmail_service.extraction
azure = extraction.azure


def _azure_ready() -> bool:
    return bool(azure.endpoint and azure.api_key and azure.deployment)


def _resolve_provider() -> str:
    """Turn `auto` into the provider that is actually configured."""
    if extraction.provider != "auto":
        return extraction.provider
    if _azure_ready():
        return "azure_openai"
    if extraction.api_key:
        return "gemini"
    return "none"


def _resolve_vision_provider() -> str:
    """Nhà cung cấp cho OCR ảnh hiện trường.

    Tách riêng khỏi `_resolve_provider()` vì hai đường có thể lệch nhau: một
    cấu hình chỉ có Azure vẫn đọc được ảnh, còn cấu hình chỉ có Gemini thì
    trước đây không đọc được ảnh chút nào (nhánh vision chưa tồn tại).

    Khi người dùng chỉ định tường minh một provider thì tôn trọng lựa chọn đó,
    nhưng vẫn phải kiểm tra provider ấy có đủ khoá hay không — nếu không thì
    trả `none` để `image_extract` báo "skipped" thay vì ném lỗi giữa chừng.
    """
    provider = extraction.provider
    if provider == "azure_openai":
        return "azure_openai" if _azure_ready() else "none"
    if provider == "gemini":
        return "gemini" if extraction.api_key else "none"
    if provider == "none":
        return "none"
    # auto
    if _azure_ready():
        return "azure_openai"
    if extraction.api_key:
        return "gemini"
    return "none"


class GmailServiceConfig(BaseModel):
    QUERY: str = gmail_service.query
    GMAIL_CREDENTIALS_FILE: str = gmail_oauth.credentials_file
    GMAIL_REDIRECT_URI: str = gmail_oauth.redirect_uri
    GMAIL_FRONTEND_RETURN_URL: str = gmail_oauth.frontend_return_url

    EXTRACTION_PROVIDER: str = _resolve_provider()
    VISION_PROVIDER: str = _resolve_vision_provider()

    GEMINI_API_KEY: str = extraction.api_key
    GEMINI_MODEL: str = extraction.model
    GEMINI_TIMEOUT_SECONDS: int = extraction.timeout_seconds

    AZURE_OPENAI_ENDPOINT: str = azure.endpoint
    AZURE_OPENAI_API_KEY: str = azure.api_key
    AZURE_OPENAI_DEPLOYMENT: str = azure.deployment
    AZURE_OPENAI_REASONING_EFFORT: str = azure.reasoning_effort
    AZURE_OPENAI_TIMEOUT_SECONDS: int = azure.timeout_seconds
    AZURE_OPENAI_MAX_INPUT_CHARS: int = azure.max_input_chars
