import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.review_agent import ReviewAgent, render_review_markdown
from app.ingest.pipeline import ingest_file
from app.memory.database import list_documents


class ReviewAgentTests(unittest.TestCase):
    def test_list_documents_returns_recent_documents(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            first = root / "first.md"
            second = root / "second.md"
            first.write_text("# 第一篇\n\nAgent 知识整理。", encoding="utf-8")
            second.write_text("# 第二篇\n\nRAG 问答。", encoding="utf-8")
            ingest_file(first, database_path)
            ingest_file(second, database_path)

            documents = list_documents(database_path, limit=2)

        self.assertEqual(len(documents), 2)
        self.assertEqual(documents[0].title, "第二篇")

    def test_render_review_markdown_handles_empty_documents(self):
        body = render_review_markdown("Daily Review - 2026-05-05", [])

        self.assertIn("# Daily Review - 2026-05-05", body)
        self.assertIn("暂无已入库文档", body)
        self.assertIn("先把 Markdown 或 TXT 文件放入", body)

    def test_review_agent_writes_markdown_report(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            reviews_dir = root / "reviews"
            note = root / "note.md"
            note.write_text("# Agent 复盘\n\n每日复盘可以帮助维护个人知识。", encoding="utf-8")
            ingest_file(note, database_path)

            report = ReviewAgent(database_path, reviews_dir).generate_daily_review(
                target_date=date(2026, 5, 5),
                limit=10,
                write_file=True,
            )

            self.assertIsNotNone(report.path)
            self.assertTrue(report.path.exists())
            self.assertIn("Agent 复盘", report.body)
            self.assertEqual(report.path.name, "2026-05-05-daily-review.md")

    def test_review_agent_can_print_without_writing(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            reviews_dir = root / "reviews"

            report = ReviewAgent(database_path, reviews_dir).generate_daily_review(write_file=False)

            self.assertIsNone(report.path)
            self.assertFalse(reviews_dir.exists())


if __name__ == "__main__":
    unittest.main()
