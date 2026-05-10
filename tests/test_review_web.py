import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.agents.review_agent import ReviewReport
from app.config import Settings
from app.web.review import (
    format_size,
    read_review_file,
    render_history_list,
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
        report = ReviewReport("Daily Review", "# Daily Review\n\n内容", None)

        html = render_report_panel(report, message="done")

        self.assertIn("Daily Review", html)
        self.assertIn("done", html)
        self.assertIn("markdown-preview", html)

    def test_render_selected_review_panel(self):
        html = render_selected_review_panel("today.md", "# Today")

        self.assertIn("today.md", html)
        self.assertIn("# Today", html)

    def test_render_review_page_includes_history_and_form(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            knowledge_dir = root / "knowledge"
            reviews_dir = knowledge_dir / "reviews"
            reviews_dir.mkdir(parents=True)
            (reviews_dir / "today.md").write_text("# Today", encoding="utf-8")
            template_path = root / "review.html"
            template_path.write_text(
                "{{ app_name }} {{ limit }} {{ write_file_checked }} {{ reviews_dir }} "
                "{{ review_count }} {{ latest_review }} {{ report_panel }} {{ history_list }} {{ selected_review_panel }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root, knowledge_dir=knowledge_dir)

            html = render_review(settings, template_path, selected_review="today.md", selected_body="# Today")

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("today.md", html)
        self.assertIn("checked", html)
        self.assertIn("# Today", html)


if __name__ == "__main__":
    unittest.main()
