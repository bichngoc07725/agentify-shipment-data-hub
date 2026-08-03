import os

from pydantic import BaseModel, ConfigDict, field_validator

from config import root_config

# Giá trị mẫu công khai trong repo/template. Bất kỳ ai đọc source đều biết,
# nên nếu app chạy thật với một trong số này thì kẻ tấn công tự ký được token
# `role=admin` mà không cần đăng nhập — toàn bộ RBAC mất tác dụng.
WEAK_JWT_SECRETS = frozenset(
    {
        "",
        "dev-secret-key",
        "secret",
        "changeme",
        "change-me",
        "your-secret-key",
        "string",
    }
)

MIN_JWT_SECRET_LENGTH = 32

# Chỉ nới lỏng khi chạy test/dev cục bộ. Production KHÔNG được set biến này.
ALLOW_WEAK_SECRET_ENV = "AGENTIFY_ALLOW_WEAK_JWT_SECRET"


def jwt_secret_is_weak(secret: str) -> bool:
    return secret.strip().lower() in WEAK_JWT_SECRETS or len(secret) < MIN_JWT_SECRET_LENGTH


class AuthConfig(BaseModel):
    # `auth_config = AuthConfig()` dựng từ toàn bộ default, mà Pydantic v2 KHÔNG
    # validate default trừ khi bật cờ này — thiếu nó thì validator bên dưới
    # không bao giờ chạy và guard trở thành vô dụng.
    model_config = ConfigDict(validate_default=True)

    API_KEY_NAME: str = root_config.authentication.api_key.name
    API_KEY_VALUE: str = root_config.authentication.api_key.value
    ALLOW_ORIGINS: list[str] = root_config.authentication.cors.allow_origins or []
    ALLOW_ORIGINS_REGEX: str | None = (
        root_config.authentication.cors.allow_origins_regex
    )
    JWT_SECRET_KEY: str = root_config.authentication.jwt.secret_key
    JWT_ALGORITHM: str = root_config.authentication.jwt.algorithm
    JWT_EXPIRE_MINUTES: int = root_config.authentication.jwt.expire_minutes

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _reject_weak_secret(cls, value: str) -> str:
        """Fail fast tại thời điểm import, không phải lúc request đầu tiên.

        Một secret yếu không gây lỗi nhìn thấy được — hệ thống vẫn chạy bình
        thường trong khi ai cũng giả mạo được token. Vì vậy phải chặn ngay khi
        khởi động, chứ không cảnh báo rồi cho qua.
        """
        if not jwt_secret_is_weak(value):
            return value
        if os.getenv(ALLOW_WEAK_SECRET_ENV) == "1":
            return value
        raise ValueError(
            "SECRET_KEY không an toàn: phải đặt chuỗi ngẫu nhiên >= "
            f"{MIN_JWT_SECRET_LENGTH} ký tự và không dùng giá trị mẫu.\n"
            "  Sinh nhanh:  python -c \"import secrets; print(secrets.token_urlsafe(48))\"\n"
            "  Rồi đặt vào backend/.env:  SECRET_KEY=<giá trị vừa sinh>\n"
            f"  (Chỉ khi chạy test cục bộ mới đặt {ALLOW_WEAK_SECRET_ENV}=1 để bỏ qua.)"
        )
