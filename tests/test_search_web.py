import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.ingest.pipeline import ingest_file
from app.tools.search_tool import SearchTool
from app.web.search import build_follow_up_prompt, build_snippet, render_results_panel, render_search


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

            html = render_results_panel(results, "RAG", message="done", filters={"category": "rag"})

        self.assertIn("RAG 搜索", html)
        self.assertIn("keyword", html)
        self.assertIn("done", html)
        self.assertIn("#chunk-0", html)
        self.assertIn("分类", html)
        self.assertIn("围绕这条继续问", html)
        self.assertIn("查看原文片段", html)

    def test_build_follow_up_prompt_contains_title_and_excerpt(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            database_path = root / "metadata.sqlite"
            note = root / "rag.md"
            note.write_text("# RAG 搜索\n\n关键词和向量检索。", encoding="utf-8")
            ingest_file(note, database_path)
            result = SearchTool(database_path).search("RAG")[0]

        prompt = build_follow_up_prompt(result)

        self.assertIn("RAG 搜索", prompt)
        self.assertIn("参考内容", prompt)

    def test_render_search_page_includes_form_options(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            template_path = root / "search.html"
            template_path.write_text(
                "{{ app_name }} {{ query }} {{ limit }} {{ mode_options }} {{ mode_description }} "
                "{{ openai_status }} {{ openai_status_class }} {{ result_count }} {{ category_filter }} {{ tag_filter }} "
                "{{ person_filter }} {{ date_from_filter }} {{ date_to_filter }} {{ results_panel }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root)

            html = render_search(
                settings,
                template_path,
                query="Agent",
                mode="vector",
                limit=3,
                filters={
                    "category": "agent",
                    "tag": "rag",
                    "person": "张三",
                    "date_from": "2026-05-01",
                    "date_to": "2026-05-31",
                },
            )

        self.assertIn("Personal AI Knowledge Butler", html)
        self.assertIn("Agent", html)
        self.assertIn("selected", html)
        self.assertIn("语义搜索", html)
        self.assertIn("未配置", html)
        self.assertIn("agent", html)
        self.assertIn("张三", html)


if __name__ == "__main__":
    unittest.main()
