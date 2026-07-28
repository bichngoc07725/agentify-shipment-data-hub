import re

from pydantic import BaseModel, Field, field_validator

# `os.path.expandvars` leaves `${VAR}` untouched when the variable is not set,
# so an unconfigured secret reaches the app as the literal placeholder string.
UNEXPANDED_PLACEHOLDER = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$")


def blank_if_unexpanded(value: str) -> str:
    return "" if UNEXPANDED_PLACEHOLDER.match(value.strip()) else value


class CORSConfig(BaseModel):
    allow_ips: list[str] | None
    allow_origins: list[str] | None
    allow_origins_regex: str | None


class APIKeyConfig(BaseModel):
    name: str
    value: str


class AuthenticationConfig(BaseModel):
    api_key: APIKeyConfig
    cors: CORSConfig


class DatabasePoolConfig(BaseModel):
    size: int
    max_overflow: int
    timeout: int
    recycle: int


class PostgresConfig(BaseModel):
    url: str
    pool: DatabasePoolConfig


class DatabaseConfig(BaseModel):
    postgres: PostgresConfig


class AppConfig(BaseModel):
    name: str
    title: str
    description: str
    proxy_root_path: str = ""
    uvicorn_logging_format: str


class GmailOAuthConfig(BaseModel):
    credentials_file: str = "credentials.json"
    redirect_uri: str = "http://localhost:8766/api/v1/gmail-connections/oauth/callback"
    frontend_return_url: str = "http://localhost:5174/setup"


class AzureOpenAIConfig(BaseModel):
    """Azure AI Foundry deployment used for structured document extraction.

    `endpoint` is the full Responses API URL, e.g.
    `https://<resource>.services.ai.azure.com/openai/v1/responses`.
    `deployment` is the deployment name, not the base model name.
    """

    endpoint: str = ""
    api_key: str = ""
    deployment: str = "gpt-5-nano-file"
    reasoning_effort: str = "low"
    timeout_seconds: int = 120
    max_input_chars: int = 12000

    _blank_placeholders = field_validator(
        "endpoint", "api_key", "deployment", "reasoning_effort", mode="before"
    )(lambda value: blank_if_unexpanded(value) if isinstance(value, str) else value)


class ExtractionConfig(BaseModel):
    """`provider` selects the LLM backend.

    `auto` prefers Azure when it is fully configured, falls back to Gemini, and
    finally to `none` (deterministic regex extraction only).
    """

    provider: str = "auto"
    api_key: str = ""
    model: str = "gemini-2.0-flash"
    azure: AzureOpenAIConfig = Field(default_factory=AzureOpenAIConfig)

    _blank_placeholders = field_validator(
        "provider", "api_key", "model", mode="before"
    )(lambda value: blank_if_unexpanded(value) if isinstance(value, str) else value)

    @field_validator("provider")
    @classmethod
    def _default_provider(cls, value: str) -> str:
        return value.strip().lower() or "auto"


class GmailServiceConfig(BaseModel):
    query: str = "has:attachment newer_than:7d"
    state_file: str = "processed.json"
    oauth: GmailOAuthConfig = Field(default_factory=GmailOAuthConfig)
    extraction: ExtractionConfig = Field(default_factory=ExtractionConfig)


class RootConfig(BaseModel):
    authentication: AuthenticationConfig
    databases: DatabaseConfig
    app: AppConfig
    gmail_service: GmailServiceConfig = Field(default_factory=GmailServiceConfig)
