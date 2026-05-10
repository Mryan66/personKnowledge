import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.ingest.pipeline import ingest_path
from app.web.inbox import (
    build_batch_summary,
    format_size,
    render_getting_started_panel,
    render_inbox,
    render_inbox_files,
    render_result_panel,
)


class InboxWebTests(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(format_size(10), "10 B")
        self.assertEqual(format_size(2048), "2.0 KB")

    def test_render_inbox_files_empty_state(self):
        html = render_inbox_files([])

        self.assertIn("还没有可导入的文件", html)

    def test_render_inbox_lists_supported_files(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            note = root / "note.md"
            note.write_text("# Note", encoding="utf-8")

            html = render_inbox_files([note])

        self.assertIn("note.md", html)
        self.assertIn("导入", html)

    def test_render_result_panel_shows_successes(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# Inbox 测试", encoding="utf-8")
            batch = ingest_path(note, database_path)

            html = render_result_panel(batch, message="done")

        self.assertIn("导入结果", html)
        self.assertIn("Inbox 测试", html)
        self.assertIn("done", html)
        self.assertIn("导入完成", html)

    def test_render_getting_started_panel_with_empty_inbox(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inbox_dir = root / "inbox"
            inbox_dir.mkdir()
            settings = Settings(workspace_dir=root, inbox_dir=inbox_dir)

            html = render_getting_started_panel(settings, [])

        self.assertIn("第一步：先放一点资料进来", html)
        self.assertIn("导入示例文件", html)

    def test_build_batch_summary_with_failures(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# Inbox 测试", encoding="utf-8")
            batch = ingest_path(note, database_path)

        summary = build_batch_summary(batch)

        self.assertIn("已新增 1 篇知识", summary)

    def test_render_inbox_page_includes_form_and_table(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            inbox_dir = root / "inbox"
            inbox_dir.mkdir()
            (inbox_dir / "note.txt").write_text("hello", encoding="utf-8")
            template_path = root / "inbox.html"
            template_path.write_text(
                "{{ app_name }} {{ inbox_path }} {{ openai_status }} {{ openai_status_class }} "
                "{{ file_count }} {{ inbox_files }} {{ result_panel }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root, inbox_dir=inbox_dir)

            html = render_inbox(settings, template_path)

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("note.txt", html)
        self.assertIn("未配置", html)


if __name__ == "__main__":
    unittest.main()
