import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from app.config import Settings
from app.memory.database import merge_tags, upsert_document
from app.web.tags import render_tags_page


class TagsWebTests(unittest.TestCase):
    def test_render_tags_page_contains_counts_and_candidate_panel(self):
        with TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            template_path = root / "tags.html"
            template_path.write_text(
                "{{ tag_count }} {{ group_count }} {{ alias_count }} {{ candidate_groups_panel }} {{ alias_history_panel }}",
                encoding="utf-8",
            )
            settings = Settings(workspace_dir=root, database_path=root / "metadata.sqlite")
            upsert_document(
                settings.resolved_database_path,
                source_path=root / "one.md",
                file_hash="hash-1",
                content_hash="content-1",
                title="One",
                summary="",
                tags=["RAG", "rag", "memory"],
                category="",
                chunks=["a"],
            )
            upsert_document(
                settings.resolved_database_path,
                source_path=root / "two.md",
                file_hash="hash-2",
                content_hash="content-2",
                title="Two",
                summary="",
                tags=["Rag", "memo"],
                category="",
                chunks=["b"],
            )
            merge_tags(settings.resolved_database_path, canonical="memory", aliases=["memo"])

            html = render_tags_page(settings, template_path)

        self.assertIn("2", html)
        self.assertIn("1", html)
        self.assertIn("候选合并组", html)
        self.assertIn("RAG", html)


if __name__ == "__main__":
    unittest.main()
