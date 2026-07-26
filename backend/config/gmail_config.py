from pydantic import BaseModel

from config import root_config

gmail_service = root_config.gmail_service
gmail_oauth = gmail_service.oauth
extraction = gmail_service.extraction
azure = extraction.azure


def _resolve_provider() -> str:
    """Turn `auto` into the provider that is actually configured."""
    if extraction.provider != "auto":
        return extraction.provider
    if azure.endpoint and azure.api_key and azure.deployment:
        return "azure_openai"
    if extraction.api_key:
        return "gemini"
    return "none"


class GmailServiceConfig(BaseModel):
    QUERY: str = gmail_service.query
    STATE_FILE: str = gmail_service.state_file
    GMAIL_CREDENTIALS_FILE: str = gmail_oauth.credentials_file
    GMAIL_REDIRECT_URI: str = gmail_oauth.redirect_uri
    GMAIL_FRONTEND_RETURN_URL: str = gmail_oauth.frontend_return_url

    EXTRACTION_PROVIDER: str = _resolve_provider()

    GEMINI_API_KEY: str = extraction.api_key
    GEMINI_MODEL: str = extraction.model

    AZURE_OPENAI_ENDPOINT: str = azure.endpoint
    AZURE_OPENAI_API_KEY: str = azure.api_key
    AZURE_OPENAI_DEPLOYMENT: str = azure.deployment
    AZURE_OPENAI_REASONING_EFFORT: str = azure.reasoning_effort
    AZURE_OPENAI_TIMEOUT_SECONDS: int = azure.timeout_seconds
    AZURE_OPENAI_MAX_INPUT_CHARS: int = azure.max_input_chars
