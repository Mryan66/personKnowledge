import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.review_agent import ReviewReport
from app.config import Settings
from app.memory.database import record_review_run
from app.web.review import (
    extract_review_insights,
    format_size,
    read_review_file,
    render_history_list,
    render_review_runs_panel,
    render_review_action_panel,
    render_report_panel,
    render_review,
    render_selected_review_panel,
)


class ReviewWebTests(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(format_size(42), "42 B")
        self.assertEqual(format_size(2048), "2.0 KB")

    def test_read_review_file_rejects_path_traversal(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            reviews_dir = root / "reviews"
            reviews_dir.mkdir()
            outside = root / "outside.md"
            outside.write_text("secret", encoding="utf-8")

            body = read_review_file(reviews_dir, "../outside.md")

        self.assertEqual(body, "")

    def test_render_history_list_empty_state(self):
        with TemporaryDirectory() as temporary_directory:
            html = render_history_list(Path(temporary_directory) / "missing")

        self.assertIn("暂无历史 Review", html)

    def test_render_report_panel_shows_report_body(self):
        report = ReviewReport("Daily Review", "# Daily Review\n\n## 总览\n- 高频标签：rag, agent\n- 主要分类：notes\n\n## 文档摘要\n- **第一篇**", None)

        html = render_report_panel(report, message="done")

        self.assertIn("Daily Review", html)
        self.assertIn("done", html)
        self.assertIn("markdown-preview", html)
        self.assertIn("复盘已生成", html)
        self.assertIn("基于这份复盘", html)
        self.assertIn("搜索标签：rag", html)

    def test_render_selected_review_panel(self):
        html = render_selected_review_panel("today.md", "# Today\n\n## 总览\n- 高频标签：rag")

        self.assertIn("today.md", html)
        self.assertIn("# Today", html)
        self.assertIn("搜索标签：rag", html)

    def test_render_review_runs_panel(self):
        html = render_review_runs_panel(
            [
                {
                    "id": 1,
                    "period": "daily",
                    "triggered_by": "auto",
                    "started_at": "2026-05-14T08:30:00+00:00",
                    "finished_at": "2026-05-14T08:30:05+00:00",
                    "status": "success",
                    "document_count": 8,
                    "output_path": "/tmp/2026-05-14-daily-review.md",
                    "error_message": "",
                }
            ]
        )

        self.assertIn("运行历史", html)
        self.assertIn("每日复盘", html)
        self.assertIn("自动", html)
        self.assertIn("2026-05-14-daily-review.md", html)

    def test_extract_review_insights(self):
        insights = extract_review_insights(
            "# Review\n\n## 总览\n- 高频标签：rag, agent\n- 主要分类：notes, project\n\n## 文档摘要\n- **第一篇**\n- **第二篇**"
        )

        self.assertEqual(insights["top_tags"], ["rag", "agent"])
        self.assertEqual(insights["top_categories"], ["notes", "project"])
        self.assertEqual(insights["document_titles"], ["第一篇", "第二篇"])

    def test_render_review_action_panel_empty_for_no_insights(self):
        html = render_review_action_panel("# Review\n\n内容")

        self.assertEqual(html, "")

    def test_render_review_page_includes_history_and_form(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            knowledge_dir = root / "knowledge"
            reviews_dir = knowledge_dir / "reviews"
            reviews_dir.mkdir(parents=True)
            (reviews_dir / "today.md").write_text("# Today", encoding="utf-8")
            database_path = root / "metadata.sqlite"
            record_review_run(
                database_path,
                period="daily",
                triggered_by="auto",
                started_at="2026-05-14T08:30:00+00:00",
                finished_at="2026-05-14T08:30:05+00:00",
                status="success",
                document_count=4,
                output_path=str(reviews_dir / "today.md"),
                error_message="",
            )
            template_path = root / "review.html"
            template_path.write_text(
                "{{ app_name }} {{ limit }} {{ write_file_checked }} {{ reviews_dir }} "
                "{{ review_count }} {{ latest_review }} {{ hero_status_items }} {{ report_panel }} {{ review_runs_panel }} {{ history_list }} {{ selected_review_panel }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root, knowledge_dir=knowledge_dir, database_path=database_path)

            html = render_review(settings, template_path, selected_review="today.md", selected_body="# Today")

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("today.md", html)
        self.assertIn("checked", html)
        self.assertIn("# Today", html)
        self.assertIn("每日复盘上次成功", html)
        self.assertIn("运行历史", html)


if __name__ == "__main__":
    unittest.main()
