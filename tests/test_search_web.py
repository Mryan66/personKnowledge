import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.ingest.pipeline import ingest_file
from app.tools.search_tool import SearchTool
from app.web.search import build_snippet, render_results_panel, render_search


class SearchWebTests(unittest.TestCase):
    def test_build_snippet_truncates_content(self):
        snippet = build_snippet("a" * 20, max_length=10)

        self.assertEqual(snippet, "aaaaaaaaa…")

    def test_render_results_panel_empty_before_query(self):
        html = render_results_panel([], "")

        self.assertEqual(html, "")

    def test_render_results_panel_shows_result_metadata(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "rag.md"
            note.write_text("# RAG 搜索\n\n关键词和向量检索。", encoding="utf-8")
            ingest_file(note, database_path)
            results = SearchTool(database_path).search("RAG")

            html = render_results_panel(results, "RAG", message="done")

        self.assertIn("RAG 搜索", html)
        self.assertIn("keyword", html)
        self.assertIn("done", html)
        self.assertIn("#chunk-0", html)

    def test_render_search_page_includes_form_options(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            template_path = root / "search.html"
            template_path.write_text(
                "{{ app_name }} {{ query }} {{ limit }} {{ mode_options }} {{ mode_description }} "
                "{{ openai_status }} {{ openai_status_class }} {{ result_count }} {{ results_panel }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root)

            html = render_search(settings, template_path, query="Agent", mode="vector", limit=3)

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("Agent", html)
        self.assertIn("selected", html)
        self.assertIn("Vector", html)
        self.assertIn("未配置", html)


if __name__ == "__main__":
    unittest.main()
