import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings, get_openai_api_key, read_env_file, remove_env_keys, write_env_values
from app.web.server import parse_openai_settings_form
from app.web.settings import (
    render_environment_keys,
    render_openai_form,
    render_openai_settings,
    render_path_settings,
    render_retrieval_settings,
    render_settings,
    render_settings_rows,
)


class SettingsWebTests(unittest.TestCase):
    def test_render_settings_rows_escapes_values(self):
        html = render_settings_rows([("Key", "<secret>")])

        self.assertIn("&lt;secret&gt;", html)

    def test_render_path_settings_includes_resolved_paths(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            settings = Settings(workspace_dir=root)

            html = render_path_settings(settings)

        self.assertIn("Workspace", html)
        self.assertIn(str(root), html)

    def test_render_openai_settings_hides_api_key(self):
        settings = Settings(openai_api_key="secret-key")

        html = render_openai_settings(settings)

        self.assertIn("已配置", html)
        self.assertNotIn("secret-key", html)

    def test_render_retrieval_settings_mentions_vector(self):
        html = render_retrieval_settings(Settings())

        self.assertIn("向量检索", html)
        self.assertIn("cosine", html)

    def test_render_environment_keys_lists_openai_key(self):
        html = render_environment_keys()

        self.assertIn("OPENAI_API_KEY", html)

    def test_write_env_values_round_trips_config(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            write_env_values(env_path, {"OPENAI_API_KEY": "secret", "KB_OPENAI_MODEL": "model-x"})

            values = read_env_file(env_path)

        self.assertEqual(values["OPENAI_API_KEY"], "secret")
        self.assertEqual(values["KB_OPENAI_MODEL"], "model-x")

    def test_render_openai_form_hides_existing_api_key(self):
        html = render_openai_form(Settings(openai_api_key="secret-key"))

        self.assertIn("保留当前 API Key", html)
        self.assertNotIn("secret-key", html)
        self.assertIn("settings-form", html)
        self.assertIn("测试连接", html)

    def test_remove_env_keys_removes_sensitive_keys(self):
        with TemporaryDirectory() as temporary_directory:
            env_path = Path(temporary_directory) / ".env"
            write_env_values(env_path, {"OPENAI_API_KEY": "secret", "KB_OPENAI_MODEL": "model-x"})

            remove_env_keys(env_path, {"OPENAI_API_KEY"})
            values = read_env_file(env_path)

        self.assertNotIn("OPENAI_API_KEY", values)
        self.assertEqual(values["KB_OPENAI_MODEL"], "model-x")

    def test_get_openai_api_key_prefers_environment_values(self):
        values = {"OPENAI_API_KEY": "from-env-file"}

        self.assertEqual(get_openai_api_key(values), "from-env-file")

    def test_parse_openai_settings_form_clamps_timeout(self):
        parsed = parse_openai_settings_form(
            {
                "openai_api_key": ["secret"],
                "openai_model": ["model-a"],
                "openai_embedding_model": ["embedding-a"],
                "openai_base_url": ["https://example.test/v1"],
                "openai_timeout_seconds": ["999"],
            },
            Settings(),
        )

        self.assertEqual(parsed["api_key"], "secret")
        self.assertEqual(parsed["updates"]["KB_OPENAI_TIMEOUT_SECONDS"], "600")

    def test_render_settings_page(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            template_path = root / "settings.html"
            template_path.write_text(
                "{{ app_name }} {{ openai_status }} {{ openai_status_class }} {{ message_panel }} {{ path_settings }} "
                "{{ openai_settings }} {{ openai_form }} {{ retrieval_settings }} {{ environment_keys }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root)

            html = render_settings(settings, template_path)

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("未配置", html)
        self.assertIn("KB_DATABASE_PATH", html)
        self.assertIn("保存配置", html)


if __name__ == "__main__":
    unittest.main()
