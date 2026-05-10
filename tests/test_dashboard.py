import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.ingest.pipeline import ingest_file
from app.memory.database import get_dashboard_stats
from app.web.dashboard import render_dashboard, render_recent_review


class DashboardTests(unittest.TestCase):
    def test_dashboard_stats_counts_documents_chunks_tags(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "note.md"
            note.write_text("# Dashboard 笔记\n\nAgent Dashboard 展示统计。", encoding="utf-8")
            ingest_file(note, database_path)

            stats = get_dashboard_stats(database_path)

        self.assertEqual(stats["document_count"], 1)
        self.assertEqual(stats["chunk_count"], 1)
        self.assertGreaterEqual(stats["tag_count"], 1)
        self.assertEqual(stats["recent_documents"][0].title, "Dashboard 笔记")

    def test_render_recent_review_returns_latest_markdown(self):
        with TemporaryDirectory() as temporary_directory:
            reviews_dir = Path(temporary_directory)
            older = reviews_dir / "older.md"
            newer = reviews_dir / "newer.md"
            older.write_text("old", encoding="utf-8")
            newer.write_text("new", encoding="utf-8")

            recent_review = render_recent_review(reviews_dir)

        self.assertIn(recent_review, {"older.md", "newer.md"})

    def test_render_dashboard_includes_current_sections(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "data" / "metadata.sqlite"
            knowledge_dir = root / "knowledge"
            template_path = root / "dashboard.html"
            template_path.write_text(
                "{{ app_name }} {{ document_count }} {{ chunk_count }} {{ embedding_count }} "
                "{{ tag_count }} {{ recent_documents }} {{ recent_review }} {{ openai_status }} "
                "{{ openai_status_class }} {{ search_status }} {{ placeholder_cards }}",
                encoding="utf-8",
            )
            note = root / "note.md"
            note.write_text("# 首页\n\nDashboard", encoding="utf-8")
            ingest_file(note, database_path)
            settings = Settings(workspace_dir=root, database_path=database_path, knowledge_dir=knowledge_dir)

            html = render_dashboard(settings, template_path)

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("首页", html)
        self.assertIn("未配置", html)
        self.assertIn("知识增长趋势图", html)


if __name__ == "__main__":
    unittest.main()
