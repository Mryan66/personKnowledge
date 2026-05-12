import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import FRONTEND_DIST_DIR, Settings, get_openai_api_key, read_env_file, remove_env_keys, resolve_frontend_assets_enabled, write_env_values
from app.ui.rendering import build_static_css_href, render_asset_tags, reset_rendering_caches
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
    def tearDown(self):
        reset_rendering_caches()

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

    def test_render_asset_tags_disabled_by_default(self):
        self.assertEqual("", render_asset_tags(False))

    def test_render_settings_page_skips_frontend_assets_by_default(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            template_path = root / "settings.html"
            template_path.write_text("{{ asset_tags }} {{ app_name }}", encoding="utf-8")
            settings = Settings(workspace_dir=root)

            html = render_settings(settings, template_path)

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertNotIn("/assets/", html)

    def test_frontend_assets_auto_enable_when_manifest_exists(self):
        self.assertEqual(resolve_frontend_assets_enabled({}), (FRONTEND_DIST_DIR / ".vite" / "manifest.json").exists())

    def test_build_static_css_href_uses_version_query(self):
        href = build_static_css_href()

        self.assertTrue(href.startswith("/static/app.css"))
        self.assertIn("?v=", href)

    def test_settings_template_uses_unified_sidebar_labels(self):
        settings_template = Path("/Library/temp/personKnowledge/app/ui/templates/settings.html").read_text(encoding="utf-8")
        base_template = Path("/Library/temp/personKnowledge/app/ui/templates/layouts/base.html").read_text(encoding="utf-8")

        self.assertIn('{% extends "layouts/base.html" %}', settings_template)
        self.assertIn(">首页<", base_template)
        self.assertIn(">导入资料<", base_template)
        self.assertIn(">AI 问答<", base_template)
        self.assertIn(">设置<", base_template)


if __name__ == "__main__":
    unittest.main()
