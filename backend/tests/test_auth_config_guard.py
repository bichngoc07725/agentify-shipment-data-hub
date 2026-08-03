"""Guard chặn JWT secret yếu (P0-1).

Bối cảnh: hệ thống từng chạy với `SECRET_KEY="dev-secret-key"` — giá trị nằm
sẵn trong template công khai. Với secret đoán được, kẻ tấn công tự ký token
`role=admin` và đi qua toàn bộ `require_permission`, tức là mọi lớp RBAC dựng
qua 9 giai đoạn đều vô hiệu. Guard phải fail-fast lúc khởi động.
"""

import os
import unittest
from unittest.mock import patch

import jwt
import pytest
from pydantic import ValidationError

from config.auth import (
    ALLOW_WEAK_SECRET_ENV,
    MIN_JWT_SECRET_LENGTH,
    AuthConfig,
    jwt_secret_is_weak,
)
from config.settings import auth_config
from services.auth_service import decode_access_token


class WeakSecretDetectionTest(unittest.TestCase):
    def test_known_template_values_are_weak(self) -> None:
        for value in ["dev-secret-key", "change-me", "changeme", "secret", "", "string"]:
            with self.subTest(value=value):
                self.assertTrue(jwt_secret_is_weak(value))

    def test_case_and_whitespace_do_not_disguise_a_template_value(self) -> None:
        self.assertTrue(jwt_secret_is_weak("  Dev-Secret-Key  "))

    def test_short_secret_is_weak_even_if_random(self) -> None:
        self.assertTrue(jwt_secret_is_weak("aB3" * 9))  # 27 ký tự < 32

    def test_long_random_secret_is_accepted(self) -> None:
        self.assertFalse(jwt_secret_is_weak("x7Qm" * 12))  # 48 ký tự


class AuthConfigStartupGuardTest(unittest.TestCase):
    def test_construction_fails_on_a_weak_secret(self) -> None:
        with patch.dict(os.environ, {ALLOW_WEAK_SECRET_ENV: ""}, clear=False):
            with pytest.raises(ValidationError):
                AuthConfig(JWT_SECRET_KEY="dev-secret-key")

    def test_the_guard_also_runs_on_DEFAULT_values(self) -> None:
        """Hồi quy: Pydantic v2 không validate default trừ khi bật
        `validate_default=True`. Thiếu cờ đó thì `AuthConfig()` — đúng cách
        `config/settings.py` khởi tạo — bỏ qua validator và guard thành vô dụng
        dù logic phát hiện vẫn đúng."""
        self.assertIs(AuthConfig.model_config.get("validate_default"), True)

    def test_escape_hatch_allows_weak_secret_only_when_explicitly_set(self) -> None:
        with patch.dict(os.environ, {ALLOW_WEAK_SECRET_ENV: "1"}, clear=False):
            cfg = AuthConfig(JWT_SECRET_KEY="dev-secret-key")
        self.assertEqual(cfg.JWT_SECRET_KEY, "dev-secret-key")

    def test_running_config_uses_a_strong_secret(self) -> None:
        self.assertFalse(jwt_secret_is_weak(auth_config.JWT_SECRET_KEY))
        self.assertGreaterEqual(len(auth_config.JWT_SECRET_KEY), MIN_JWT_SECRET_LENGTH)


class ForgedTokenIsRejectedTest(unittest.TestCase):
    def test_token_signed_with_the_old_dev_secret_no_longer_decodes(self) -> None:
        """Đây là lỗ hổng đã tái hiện được: token tự ký bằng 'dev-secret-key'
        từng vào thẳng `/api/v1/users` và `/api/v1/audit` với HTTP 200."""
        forged = jwt.encode(
            {"sub": "00000000-0000-0000-0000-000000000000",
             "username": "hacker", "role": "admin"},
            "dev-secret-key",
            algorithm="HS256",
        )
        with pytest.raises(jwt.InvalidTokenError):
            decode_access_token(forged)


if __name__ == "__main__":
    unittest.main()
