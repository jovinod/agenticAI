import os
import unittest
from unittest.mock import MagicMock, patch


@unittest.skipUnless(
    os.environ.get("KEY_VAULT_URI"), "no KEY_VAULT_URI exported -- skipping the live call"
)
class TestGetTavilyKeyLive(unittest.TestCase):
    def test_retrieves_the_real_secret_from_key_vault(self) -> None:
        import secret_client

        secret_client._cached_key = None
        value = secret_client.get_tavily_key()

        self.assertTrue(value)


class TestGetTavilyKeyCaching(unittest.TestCase):
    def test_the_vault_is_called_at_most_once_across_repeated_reads(self) -> None:
        import secret_client

        secret_client._cached_key = None

        fake_secret = MagicMock()
        fake_secret.value = "fake-tavily-key"
        fake_client = MagicMock()
        fake_client.get_secret.return_value = fake_secret

        with patch.object(secret_client, "SecretClient", return_value=fake_client):
            first = secret_client.get_tavily_key()
            second = secret_client.get_tavily_key()

        self.assertEqual(first, "fake-tavily-key")
        self.assertEqual(second, "fake-tavily-key")
        fake_client.get_secret.assert_called_once_with("tavily-api-key")


if __name__ == "__main__":
    unittest.main()
