import asyncio
import unittest
from unittest.mock import patch

from fastapi import HTTPException

import auth


class FakeUser:
    def __init__(self, preferred_username=None, email=None):
        self.preferred_username = preferred_username
        self.email = email


class TestRequireUser(unittest.TestCase):
    @patch.object(auth, "ALLOWED_USERS", {"josh.vinod@hotmail.com"})
    def test_a_valid_token_for_an_allowed_user_passes_through(self) -> None:
        user = FakeUser(preferred_username="josh.vinod@hotmail.com")

        result = asyncio.run(auth.require_user(user))

        self.assertIs(result, user)

    @patch.object(auth, "ALLOWED_USERS", {"josh.vinod@hotmail.com"})
    def test_a_valid_token_for_a_user_outside_the_allow_list_is_403(self) -> None:
        user = FakeUser(preferred_username="someone.else@example.com")

        with self.assertRaises(HTTPException) as ctx:
            asyncio.run(auth.require_user(user))

        self.assertEqual(ctx.exception.status_code, 403)

    @patch.object(auth, "ALLOWED_USERS", {"josh.vinod@hotmail.com"})
    def test_the_allow_list_check_is_case_insensitive(self) -> None:
        user = FakeUser(preferred_username="Josh.Vinod@Hotmail.com")

        result = asyncio.run(auth.require_user(user))

        self.assertIs(result, user)

    @patch.object(auth, "ALLOWED_USERS", {"josh.vinod@hotmail.com"})
    def test_falls_back_to_email_when_preferred_username_is_absent(self) -> None:
        user = FakeUser(preferred_username=None, email="josh.vinod@hotmail.com")

        result = asyncio.run(auth.require_user(user))

        self.assertIs(result, user)


if __name__ == "__main__":
    unittest.main()
