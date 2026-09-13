import importlib
import os
import unittest


class TestGetTavilyKeyLocal(unittest.TestCase):
    def test_an_env_var_key_is_used_without_key_vault(self) -> None:
        os.environ["TAVILY_API_KEY"] = "local-test-key"

        import search_server

        search_server._cached_key = None
        importlib.reload(search_server)
        search_server._cached_key = None

        self.assertEqual(search_server._get_tavily_key(), "local-test-key")


@unittest.skipUnless(
    os.environ.get("KEY_VAULT_URI"), "no KEY_VAULT_URI exported -- skipping the live call"
)
class TestGetTavilyKeyFromVault(unittest.TestCase):
    def test_retrieves_the_real_secret_when_no_env_var_is_set(self) -> None:
        os.environ.pop("TAVILY_API_KEY", None)

        import search_server

        search_server._cached_key = None

        value = search_server._get_tavily_key()
        self.assertTrue(value)


if __name__ == "__main__":
    unittest.main()
