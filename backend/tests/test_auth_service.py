import unittest
from uuid import uuid4

from db.models import UserRole
from services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)


class FakeUser:
    def __init__(self, role: UserRole = UserRole.ADMIN) -> None:
        self.id = uuid4()
        self.username = "admin"
        self.role = role


class PasswordHashingTest(unittest.TestCase):
    def test_correct_password_verifies(self) -> None:
        hashed = hash_password("admin@123")

        self.assertTrue(verify_password("admin@123", hashed))

    def test_wrong_password_does_not_verify(self) -> None:
        hashed = hash_password("admin@123")

        self.assertFalse(verify_password("not-the-password", hashed))

    def test_hash_is_not_the_plaintext(self) -> None:
        hashed = hash_password("admin@123")

        self.assertNotEqual(hashed, "admin@123")


class AccessTokenTest(unittest.TestCase):
    def test_token_carries_exactly_one_role_and_the_user_id(self) -> None:
        user = FakeUser(role=UserRole.OPS)

        token = create_access_token(user)
        payload = decode_access_token(token)

        self.assertEqual(payload["role"], "ops")
        self.assertEqual(payload["sub"], str(user.id))
        self.assertEqual(payload["username"], "admin")

    def test_each_role_round_trips_through_the_token(self) -> None:
        for role in UserRole:
            with self.subTest(role=role):
                token = create_access_token(FakeUser(role=role))
                payload = decode_access_token(token)
                self.assertEqual(payload["role"], role.value)


if __name__ == "__main__":
    unittest.main()
