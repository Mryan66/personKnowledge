import unittest
from unittest.mock import patch

from app.tools.secret_store import load_openai_api_key, save_openai_api_key


class SecretStoreTests(unittest.TestCase):
    def test_load_openai_api_key_returns_empty_when_keychain_unavailable(self):
        with patch("app.tools.secret_store.is_keychain_available", return_value=False):
            self.assertEqual(load_openai_api_key(), "")

    def test_save_openai_api_key_skips_empty_value(self):
        with patch("app.tools.secret_store.subprocess.run") as run:
            save_openai_api_key("")

        run.assert_not_called()

    def test_load_openai_api_key_reads_security_output(self):
        class Result:
            returncode = 0
            stdout = "secret\n"
            stderr = ""

        with patch("app.tools.secret_store.is_keychain_available", return_value=True):
            with patch("app.tools.secret_store.subprocess.run", return_value=Result()):
                self.assertEqual(load_openai_api_key(), "secret")


if __name__ == "__main__":
    unittest.main()
